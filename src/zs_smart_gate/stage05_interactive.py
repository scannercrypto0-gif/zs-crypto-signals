"""Independent Stage05C interactive bot; no scanner promotion or auto-poll.

Authorized raw-symbol query -> bounded read-only snapshot lookup. Real reply
and polling are separate actions, both default disabled and owner-gated.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import hashlib
import re

from .stage05_contracts import ContractError, canonical, parse_utc, utc_now
from .stage05_delivery import GithubOutbox, _claim, _key
from .stage05_telegram_http import (
    RuntimeFlags, TelegramHTTP, require_live_permission,
)

SYMBOL = re.compile(r"[A-Z0-9]{3,20}USDT\Z")


def parse_symbol(text, supported):
    if not isinstance(text, str):
        raise ContractError("INTERACTIVE_QUERY_NOT_TEXT")
    value = text.strip()
    if value.lower().startswith("/analyze "):
        value = value[9:].strip()
    normalized = value.upper()
    if not SYMBOL.fullmatch(normalized):
        raise ContractError("INVALID_SPOT_USDT_SYMBOL")
    if normalized not in supported:
        raise ContractError("SPOT_USDT_SYMBOL_NOT_IN_APPROVED_REGISTRY")
    return normalized


def _authorized(config, user_id, chat_id):
    # 05C serves exactly two OWNER-APPROVED PRIVATE accounts. A private
    # Telegram chat ID must equal its sender's user ID; accepting each
    # allowlist independently would permit a cross-account (A user, B chat)
    # request. Missing/partial/extra allowlists must fail closed.
    uid, cid = str(user_id), str(chat_id)
    accounts = frozenset((config.signals_chat_a, config.signals_chat_b))
    return bool(
        uid == cid
        and uid in accounts
        and config.interactive_users == accounts
        and config.interactive_chats == accounts
    )


def analysis_request_id(user_id, chat_id, message_id):
    if not isinstance(message_id, int) or message_id < 0:
        raise ContractError("INTERACTIVE_MESSAGE_ID_REQUIRED")
    return hashlib.sha256(canonical({
        "bot": "INTERACTIVE", "user": str(user_id), "chat": str(chat_id),
        "telegram_message_id": message_id,
    })).hexdigest()


class InteractiveService:
    """No auto-run, no network during queue processing, no market-data fetch.

    snapshots is a caller-supplied READ ONLY lookup; the service never claims
    realtime freshness unless the source contains valid explicit times.
    """

    def __init__(self, *, config, supported_symbols, lookup, clock=None, max_queue=32):
        config.validate()
        if not isinstance(supported_symbols, (set, frozenset, tuple, list)):
            raise ContractError("APPROVED_SYMBOL_REGISTRY_REQUIRED")
        self.config = config
        self.supported = frozenset(supported_symbols)
        if not self.supported or not all(SYMBOL.fullmatch(s) for s in self.supported):
            raise ContractError("INVALID_SPOT_USDT_REGISTRY")
        if not callable(lookup) or not 1 <= max_queue <= 64:
            raise ContractError("READ_ONLY_LOOKUP_OR_QUEUE_INVALID")
        self.lookup = lookup
        self.clock = clock if clock is not None else (lambda: datetime.now(timezone.utc))
        self.queue = deque(maxlen=max_queue)
        self._seen = set()
        self._last_user = {}

    def accept(self, *, text, user_id, chat_id, message_id):
        if not _authorized(self.config, user_id, chat_id):
            return {"status": "UNAUTHORIZED", "signal_id": None}
        try:
            symbol = parse_symbol(text, self.supported)
            key = analysis_request_id(user_id, chat_id, message_id)
        except ContractError as exc:
            return {"status": "REJECTED", "reason": str(exc), "signal_id": None}
        if key in self._seen:
            return {"status": "DUPLICATE", "analysis_request_id": key, "signal_id": None}
        now = utc_now(self.clock)
        previous = self._last_user.get(str(user_id))
        if previous and (parse_utc(now) - parse_utc(previous)).total_seconds() < 2:
            return {"status": "LOCAL_RATE_LIMITED", "signal_id": None}
        if len(self.queue) >= self.queue.maxlen:
            return {"status": "QUEUE_FULL", "signal_id": None}
        self._seen.add(key)
        self._last_user[str(user_id)] = now
        request = {"analysis_request_id": key, "symbol": symbol,
                   "requested_at": now, "status": "QUEUED", "signal_id": None,
                   "reply_chat_id": str(chat_id), "sender_user_id": str(user_id)}
        self.queue.append(request)
        return request

    def process_one(self):
        if not self.queue:
            return {"status": "EMPTY"}
        request = self.queue.popleft()
        try:
            data = self.lookup(request["symbol"])
        except Exception:
            data = None
        if data is None:
            return {**request, "status": "NO_APPROVED_SNAPSHOT",
                    "reason_codes": ["NO_IMPLEMENTED_DATA_AVAILABLE"],
                    "indicators": [], "score": None}
        if not isinstance(data, dict) or data.get("symbol") != request["symbol"]:
            return {**request, "status": "INVALID_SNAPSHOT",
                    "reason_codes": ["SOURCE_IDENTITY_MISMATCH"],
                    "indicators": [], "score": None}
        try:
            as_of = parse_utc(data.get("as_of"), "INTERACTIVE_SNAPSHOT_AS_OF")
            if as_of > parse_utc(request["requested_at"]):
                raise ContractError("FUTURE_INTERACTIVE_SNAPSHOT")
        except ContractError:
            return {**request, "status": "INVALID_SNAPSHOT",
                    "reason_codes": ["SNAPSHOT_TIME_UNAVAILABLE"],
                    "indicators": [], "score": None}
        if not isinstance(data.get("indicators"), list):
            return {**request, "status": "INVALID_SNAPSHOT",
                    "reason_codes": ["INDICATOR_LIST_UNAVAILABLE"],
                    "indicators": [], "score": None}
        fields = ("indicator_id", "raw_value", "value", "availability",
                  "evaluation", "threshold", "unit", "timeframe", "source",
                  "as_of", "version", "reason_codes")
        for row in data["indicators"]:
            if (not isinstance(row, dict) or any(x not in row for x in fields)
                    or row.get("evaluation") not in ("PASS", "FAIL", "UNKNOWN")
                    or not isinstance(row.get("reason_codes"), list)):
                return {**request, "status": "INVALID_SNAPSHOT",
                        "reason_codes": ["INDICATOR_METADATA_INCOMPLETE"],
                        "indicators": [], "score": None}
            try:
                if parse_utc(row["as_of"]) > as_of:
                    raise ContractError("FUTURE_INDICATOR")
            except ContractError:
                return {**request, "status": "INVALID_SNAPSHOT",
                        "reason_codes": ["INDICATOR_TIME_INVALID"],
                        "indicators": [], "score": None}
        return {**request, "status": "READ_ONLY_ANALYSIS",
                "source_scope": data.get("source_scope", "UNKNOWN"),
                "as_of": data["as_of"], "indicators": data["indicators"],
                "score": data.get("score"), "decision": data.get("decision"),
                "reason_codes": data.get("reason_codes", []),
                "no_new_signal_generated": True}

    def poll_once(self, *, offset=0, flags=None, permit=None,
                  head_sha=None, transport=None):
        """One explicit bounded poll, NEVER auto-scheduled or sent as signal."""
        http = transport if transport is not None else TelegramHTTP(self.config.interactive_token)
        result = http.get_updates(offset=offset, flags=flags, permit=permit,
                                  head_sha=head_sha)
        if result.status != "ACCEPTED":
            return {"status": result.status, "accepted": [], "next_offset": offset}
        accepted = []
        next_offset = offset
        for update in result.updates:
            if not isinstance(update, dict):
                continue
            uid = update.get("update_id")
            if not isinstance(uid, int) or isinstance(uid, bool):
                continue
            next_offset = max(next_offset, uid + 1)
            message = update.get("message")
            if not isinstance(message, dict):
                continue
            sender, chat = message.get("from"), message.get("chat")
            if not isinstance(sender, dict) or not isinstance(chat, dict):
                continue
            if not isinstance(message.get("text"), str):
                continue
            accepted.append(self.accept(
                text=message["text"], user_id=sender.get("id"),
                chat_id=chat.get("id"), message_id=message.get("message_id")))
        return {"status": "ACCEPTED", "accepted": accepted,
                "next_offset": next_offset, "no_auto_reply": True}

    def format_reply(self, response):
        if not isinstance(response, dict) or not response.get("analysis_request_id"):
            raise ContractError("INTERACTIVE_REPLY_REQUEST_REQUIRED")
        text = ("ZS05 INTERACTIVE\nRequest: " + response["analysis_request_id"][:16] +
                "\nSymbol: " + response["symbol"] +
                "\nStatus: " + response["status"])
        if response["status"] == "READ_ONLY_ANALYSIS":
            if not isinstance(response.get("indicators"), list):
                raise ContractError("INTERACTIVE_INDICATORS_REQUIRED")
            age_s = (parse_utc(response["requested_at"]) -
                     parse_utc(response["as_of"])).total_seconds()
            if age_s < 0:
                raise ContractError("FUTURE_INTERACTIVE_SNAPSHOT")
            text += ("\nAs-of UTC: " + response["as_of"] +
                     "\nSnapshot age seconds: " + str(age_s) +
                     "\nFreshness: NOT_REALTIME_VERIFIED" +
                     "\nSource scope: " + str(response.get("source_scope", "UNKNOWN")))
            for row in response["indicators"]:
                reasons = ",".join(map(str, row["reason_codes"])) or "NONE"
                text += ("\n" + str(row["indicator_id"]) + ": value=" +
                         str(row["value"]) + "; raw=" + str(row["raw_value"]) +
                         "; availability=" + str(row["availability"]) +
                         "; evaluation=" + str(row["evaluation"]) +
                         "; timeframe=" + str(row["timeframe"]) +
                         "; unit=" + str(row["unit"]) +
                         "; threshold=" + str(row["threshold"]) +
                         "; version=" + str(row["version"]) +
                         "; source=" + str(row["source"]) +
                         "; as-of=" + str(row["as_of"]) +
                         "; reasons=" + reasons)
            score = response.get("score")
            if isinstance(score, dict) and score.get("approved") is True and score.get("value") is not None:
                text += "\nScore: " + str(score["value"])
            else:
                text += "\nScore: SCORE_UNAVAILABLE (NO_APPROVED_SCORE)"
            text += "\nDecision: " + str(response.get("decision") or "UNAVAILABLE")
            text += "\nDecision reasons: " + (",".join(map(str, response.get("reason_codes") or [])) or "NONE")
        else:
            text += "\nReasons: " + ",".join(map(str, response.get("reason_codes") or []))
        if len(text) > 3900:
            raise ContractError("INTERACTIVE_REPLY_TOO_LONG")
        return text

def respond_once(*, response, chat_id, user_id, config, store, flags=None,
                 permit=None, head_sha=None, transport=None,
                 clock=None, simulation=False):
    """Optional one-reply action with preclaim; no automatic polling or send."""
    if not isinstance(response, dict) or response.get("signal_id") is not None:
        raise ContractError("INTERACTIVE_IS_NOT_A_SCANNER_SIGNAL")
    if not response.get("analysis_request_id"):
        raise ContractError("INTERACTIVE_ID_REQUIRED")
    if not simulation:
        if not isinstance(store, GithubOutbox) or not store.verified_backend:
            raise ContractError("APPROVED_GITHUB_OUTBOX_REQUIRED")
        require_live_permission(flags=flags if flags is not None else RuntimeFlags(),
                                permit=permit, head_sha=head_sha, action="INTERACTIVE_REPLY")
    if (not _authorized(config, user_id, chat_id)
            or response.get("reply_chat_id") != str(chat_id)
            or response.get("sender_user_id") != str(user_id)):
        raise ContractError("INTERACTIVE_REPLY_RECIPIENT_NOT_AUTHORIZED")
    reply = response.get("reply_text")
    if not isinstance(reply, str) or not reply or len(reply) > 3900:
        raise ContractError("INTERACTIVE_REPLY_TEXT_INVALID")
    stamp = utc_now(clock if clock is not None else lambda: datetime.now(timezone.utc))
    delivery_id = hashlib.sha256(canonical({
        "analysis_request_id": response["analysis_request_id"], "bot": "INTERACTIVE",
        "destination_label": "INTERACTIVE_REQUEST_CHAT",
    })).hexdigest()
    key = _key("interactive-attempt", delivery_id)
    old = store.read(key)
    if old is not None:
        return {"status": "UNKNOWN_DELIVERY", "reason": "PRIOR_INTERACTIVE_ATTEMPT",
                "delivery_id": delivery_id}
    _claim(store, key, {"schema": "zs05.interactive-attempt.v1",
                        "delivery_id": delivery_id, "started_at": stamp})
    http = transport if transport is not None else TelegramHTTP(config.interactive_token)
    # Request identity and chat are validated BEFORE preclaim.
    try:
        outcome = http.send_text(
            chat_id, reply, flags=flags, permit=permit,
            head_sha=head_sha, action="INTERACTIVE_REPLY")
        state = outcome.status
    except Exception:
        state = "UNKNOWN_DELIVERY"
    receipt = {"schema": "zs05.interactive-receipt.v1",
               "delivery_id": delivery_id, "status": state,
               "attempt_at": stamp, "bot_id": "INTERACTIVE",
               "destination_label": "INTERACTIVE_REQUEST_CHAT",
               "telegram_accepted_at": utc_now(clock if clock is not None else lambda: datetime.now(timezone.utc))
                   if state == "ACCEPTED" else None,
               "telegram_message_id": (outcome.message_id if state == "ACCEPTED" else None),
               "telegram_message_date_at": (outcome.message_date_at if state == "ACCEPTED" else None)}
    try:
        _claim(store, _key("interactive-outcome", delivery_id), receipt)
    except Exception:
        return {"status": "UNKNOWN_DELIVERY", "delivery_id": delivery_id}
    return receipt
