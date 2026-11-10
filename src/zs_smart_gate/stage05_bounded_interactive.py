"""Bounded 05C TEST ONLY orchestration over actual private Telegram updates."""
from collections import Counter
from datetime import datetime, timezone
import time

from .stage05_contracts import ContractError, canonical, digest
from .stage05_custody import LocalOutbox, VerifiedUpstream
from .stage05_interactive import InteractiveService, respond_once
from .stage05_telegram_http import TelegramHTTP, require_live_permission


def bounded_interactive(*, config, transport, store, upstream, source_ref, started_at,
                        session_id, flags=None, permit=None, head_sha=None,
                        clock=None, simulation=False, ready=None, guard=lambda: None, on_attempt=None, account_a_only=False):
    """At most 12 Bot API calls and two replies; never acknowledges updates."""
    config.validate()
    if type(store) is not LocalOutbox or type(upstream) is not VerifiedUpstream:
        raise ContractError("LOCAL_VERIFIED_CUSTODY_REQUIRED")
    if type(started_at) is not int or started_at <= 0:
        raise ContractError("SESSION_START_REQUIRED")
    if not simulation:
        if ready is None:
            raise ContractError("HUMAN_READY_CALLBACK_REQUIRED")
        if transport is not None:
            raise ContractError("LIVE_TRANSPORT_INJECTION_FORBIDDEN")
        transport = TelegramHTTP(config.interactive_token, on_attempt=on_attempt)
        for action in ("INTERACTIVE_POLL", "INTERACTIVE_REPLY"):
            require_live_permission(flags=flags, permit=permit, head_sha=head_sha, action=action)
    clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
    now = int(clock().timestamp())
    if not 0 <= now-started_at <= 180:
        raise ContractError("INTERACTIVE_SESSION_EXPIRED")
    snapshot = upstream.snapshot(*source_ref, "BTCUSDT") if source_ref else None
    reply_service = InteractiveService(config=config, supported_symbols=["BTCUSDT"],
                                       lookup=lambda _: snapshot, clock=clock)
    opts = dict(flags=flags, permit=permit, head_sha=head_sha)
    key = "interactive-session/" + digest(canonical(session_id))
    if store.read(key) is not None:
        raise ContractError("INTERACTIVE_SESSION_ALREADY_CONSUMED")
    calls = []
    pair = {"A": config.signals_chat_a}
    if not account_a_only:
        pair["B"] = config.signals_chat_b
    pending = {}
    diagnostics = Counter()

    def call(label, method, **kwargs):
        guard()
        calls.append({"method": label, "at": clock().isoformat()})
        return method(**opts, **kwargs)

    def result(status, replies=None):
        return {"status": status, "replies": replies or {}, "calls": calls,
                "claimed": store.read(key) is not None, "ingress_counts": dict(diagnostics)}

    def poll():
        return call("getUpdates", transport.get_updates, offset=0)

    high_water = -1
    if not simulation:
        for name, check in (("getMe", transport.verify_interactive_identity),
                            ("getWebhookInfo", transport.verify_no_webhook)):
            if call(name, check).status != "ACCEPTED":
                return result("INTERACTIVE_IDENTITY_OR_WEBHOOK_BLOCKED")
        baseline = poll()
        if (baseline.status != "ACCEPTED" or len(baseline.updates) >= 18
                or any(not isinstance(row, dict) or type(row.get("update_id")) is not int
                       for row in baseline.updates)):
            return result("INTERACTIVE_BASELINE_OR_BACKLOG_BLOCKED")
        high_water = max((row["update_id"] for row in baseline.updates), default=-1)
        started_at = int(clock().timestamp())
    if not store.create_if_absent(key, canonical({"started_at": started_at, "head_sha": head_sha,
                                                 "baseline_high_water": high_water})):
        raise ContractError("INTERACTIVE_SESSION_ALREADY_CONSUMED")
    if not simulation:
        ready()
    for _ in range(1 if simulation else 7):
        if not simulation:
            for _ in range(15):
                guard()
                time.sleep(1)
        if not 0 <= int(clock().timestamp())-started_at <= 180:
            return result("INTERACTIVE_SESSION_EXPIRED")
        updates = poll()
        if updates.status != "ACCEPTED" or len(updates.updates) > 20:
            return result("INTERACTIVE_POLL_FAILED_OR_UNKNOWN")
        for update in updates.updates:
            diagnostics["updates_examined"] += 1
            if not isinstance(update, dict):
                diagnostics["invalid_update"] += 1
                continue
            if not simulation and (type(update.get("update_id")) is not int
                                   or update["update_id"] <= high_water):
                diagnostics["baseline_or_invalid_update_id"] += 1
                continue
            msg = update.get("message")
            if not isinstance(msg, dict):
                diagnostics["no_message"] += 1
                continue
            sender, chat = msg.get("from"), msg.get("chat")
            if not isinstance(sender, dict) or not isinstance(chat, dict):
                diagnostics["invalid_sender_or_chat"] += 1
                continue
            uid, cid = sender.get("id"), chat.get("id")
            if (type(uid) is not int or type(cid) is not int or uid != cid
                    or sender.get("is_bot") is not False or chat.get("type") != "private"):
                diagnostics["not_private_human"] += 1
                continue
            if str(uid) not in pair.values():
                diagnostics["account_not_allowed"] += 1
                continue
            if not isinstance(msg.get("text"), str) or msg["text"].strip().upper() != "BTCUSDT":
                diagnostics["symbol_mismatch"] += 1
                continue
            if type(msg.get("date")) is not int or not started_at <= msg["date"] <= int(clock().timestamp()):
                diagnostics["outside_session_time"] += 1
                continue
            if type(msg.get("message_id")) is not int or msg["message_id"] <= 0:
                diagnostics["invalid_message_id"] += 1
                continue
            for role, account in pair.items():
                if str(uid) == account:
                    pending.setdefault(role, msg["message_id"])
                    diagnostics["matched_" + role] += 1
        if set(pending) == set(pair):
            break
    if set(pending) != set(pair):
        return result("ACCOUNT_A_REQUEST_NOT_OBSERVED" if account_a_only else "TWO_HUMAN_REQUESTS_NOT_OBSERVED")
    results = {}
    for role, account in pair.items():
        if not 0 <= int(clock().timestamp())-started_at <= 180:
            return result("INTERACTIVE_SESSION_EXPIRED", results)
        request = reply_service.accept(text="BTCUSDT", user_id=account, chat_id=account,
                                       message_id=pending[role])
        if request["status"] != "QUEUED":
            raise ContractError("INTERACTIVE_REQUEST_NOT_QUEUED")
        answer = reply_service.process_one()
        answer["reply_text"] = "ZS 05C TEST ONLY / NOT A TRADING SIGNAL\n" + reply_service.format_reply(answer)
        guard()
        receipt = respond_once(response=answer, chat_id=account, user_id=account, config=config,
                              store=store, transport=transport, clock=clock, simulation=simulation,
                              reply_to=pending[role], **opts)
        results[role] = {k: receipt[k] for k in ("status", "telegram_message_date_at") if k in receipt}
        if receipt.get("replayed"):
            return result("INTERACTIVE_PRIOR_REPLY_NO_NEW_SEND", results)
        if receipt.get("status") not in ("LOCAL_RATE_LIMITED",):
            calls.append({"method": "sendMessage", "role": role, "at": receipt.get("attempt_at")})
        if receipt["status"] != "ACCEPTED":
            return result("INTERACTIVE_PARTIAL_STOP", results)
        results[role]["reply_binding_verified"] = not simulation
    return result("ACCOUNT_A_API_ACCEPTED_REPLY" if account_a_only else "TWO_API_ACCEPTED_REPLIES", results)
