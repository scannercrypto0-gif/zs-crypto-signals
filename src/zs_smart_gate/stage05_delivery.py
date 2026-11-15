"""Stage05 three independent bots, durable-per-attempt outbox, opt-in only.

Uses the existing GitHub ContentsTransport *interface* for future approved
application-level create-if-absent/readback (NOT WORM or global exactly-once).
Never invokes GitHub or Telegram automatically. Offline tests inject a memory
store and fake transport. Real dispatch additionally demands separate permit,
flags, approved real source, and a verified local decision and attempt journal.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from .stage05_contracts import (
    ContractError, canonical, digest, ensure_event, make_document, parse_utc, utc_now,
)
from .stage05_custody import LocalOutbox, VerifiedUpstream
from .stage05_telegram_http import (
    BotSecrets, RuntimeFlags, TelegramHTTP, require_live_permission,
)

MAX_ATTEMPTS = 3
DESTINATIONS = {"A": "SIGNALS", "B": "SIGNALS", "C": "ANALYTICS"}
KEY = re.compile(r"[0-9a-f]{64}\Z")


class GithubOutbox:
    """Real GitHub Contents readback, but only through an injected transport.

    NOT transactional across messages, protected from privileged rewriting, or
    an already authorized market/Telegram writer. Deployment still needs owner
    approval and backend readiness. Path never contains secret chat ID/token.
    """
    def __init__(self, transport, branch, *, verified_backend=False):
        if not branch or not re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", branch):
            raise ContractError("OUTBOX_BRANCH_INVALID")
        if not re.fullmatch(r"evidence-stage05-[a-z0-9][a-z0-9-]{0,63}", branch):
            raise ContractError("OUTBOX_DEDICATED_STAGE05_BRANCH_REQUIRED")
        self._transport = transport
        self._branch = branch
        # A caller-provided assertion is NOT independent evidence of custody.
        self.verified_backend = verified_backend

    def read(self, key):
        result = self._transport.get_file("stage05/outbox/v1/" + key + ".json", self._branch)
        return result[0] if result is not None else None

    def create_if_absent(self, key, content):
        path = "stage05/outbox/v1/" + key + ".json"
        try:
            inserted = self._transport.put_file(
                path, content, self._branch, None, "stage05-outbox:" + key[:64])
        except Exception:
            raise ContractError("GITHUB_OUTBOX_WRITE_UNCERTAIN") from None
        if not inserted:
            return False
        if self.read(key) != content:
            raise ContractError("GITHUB_OUTBOX_READBACK_MISMATCH")
        return True


class MemoryOutbox:
    """Test-only, not durable; NEVER sufficient for real dispatch."""
    verified_backend = False
    def __init__(self):
        self.records = {}

    def read(self, key):
        return self.records.get(key)

    def create_if_absent(self, key, content):
        if key in self.records:
            return False
        self.records[key] = content
        return True


def _key(kind, identity):
    if not KEY.fullmatch(identity):
        raise ContractError("OUTBOX_IDENTITY_INVALID")
    return kind + "/" + identity


def _claim(store, key, value):
    encoded = canonical(value)
    existing = store.read(key)
    if existing is not None:
        if existing != encoded:
            raise ContractError("OUTBOX_IDENTITY_CONFLICT")
        return False
    if store.create_if_absent(key, encoded):
        if store.read(key) != encoded:
            raise ContractError("OUTBOX_READBACK_MISSING")
        return True
    if store.read(key) != encoded:
        raise ContractError("OUTBOX_IDENTITY_CONFLICT")
    return False


@dataclass(frozen=True)
class DeliveryJob:
    delivery_id: str
    candidate_id: str
    signal_id: str | None
    bot_id: str
    destination: str
    payload_sha256: str
    kind: str
    event_sha256: str


def plan(event):
    """One candidate row; qualified -> A+B+C, rejected -> C only."""
    ensure_event(event)
    report = make_document(event)
    event_sha = digest(canonical(event))
    qualified = event["qualification_status"] == "QUALIFIED"
    dests = ("A", "B", "C") if qualified else ("C",)
    jobs = []
    for destination in dests:
        kind = "ANALYTICS_DOCUMENT" if destination == "C" else "SIGNAL_TEXT"
        payload = report["document"] if destination == "C" else _signal_text(event).encode("utf-8")
        job_identity = {
            "candidate_id": event["candidate_id"], "signal_id": event["signal_id"],
            "bot_id": DESTINATIONS[destination], "destination": destination,
            "kind": kind,
        }
        jobs.append(DeliveryJob(
            digest(canonical(job_identity)), event["candidate_id"],
            event["signal_id"], DESTINATIONS[destination],
            destination, digest(payload), kind, event_sha,
        ))
    return tuple(jobs)


def _signal_text(event):
    """Render only supplied approved values; never invent plan/score terms."""
    if event["qualification_status"] != "QUALIFIED":
        raise ContractError("SIGNAL_TEXT_REQUIRES_QUALIFIED")

    def shown(value):
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            return None
        return str(value).replace("\r", " ").replace("\n", " ")

    score = event.get("score")
    if score is None:
        score_line = "SCORE_UNAVAILABLE (NO_APPROVED_SCORE)"
    elif shown(score.get("value")) is None:
        score_line = "SCORE_UNAVAILABLE (APPROVED_SCORE_VALUE_MISSING)"
    else:
        score_line = shown(score["value"])
        if shown(score.get("version")):
            score_line += "; version=" + shown(score["version"])
        score_line += "; reasons=" + (",".join(map(str, score.get("reason_codes") or [])) or "NONE")

    plan_data = event.get("trade_plan")
    plan_keys = ("entry_zone", "stop_loss", "tp1", "tp2", "tp3")
    if plan_data is None:
        plan_lines = ["Trade plan: RESEARCH_ONLY (NO_APPROVED_TRADE_PLAN)"]
    elif plan_data.get("approved") is True and all(shown(plan_data.get(k)) for k in plan_keys):
        plan_lines = ["Trade plan: APPROVED"]
        if shown(plan_data.get("version")):
            plan_lines.append("Plan version: " + shown(plan_data["version"]))
        plan_lines.extend(("Entry zone: " + shown(plan_data["entry_zone"]),
                           "Stop loss: " + shown(plan_data["stop_loss"]),
                           "TP1: " + shown(plan_data["tp1"]),
                           "TP2: " + shown(plan_data["tp2"]),
                           "TP3: " + shown(plan_data["tp3"])))
    else:
        plan_lines = ["Trade plan: RESEARCH_ONLY (APPROVED_PLAN_TERMS_INCOMPLETE)"]

    gate_lines = ["Gate decisions:"]
    for gate in event["gates"]:
        reasons = ",".join(map(str, gate["reason_codes"])) or "NONE"
        gate_lines.append("  " + gate["gate_id"] + "=" + gate["state"] +
                          " (reasons=" + reasons + ")")
    times = event["timestamps"]
    lines = [
        "ZS05 SIGNAL | " + event["signal_id"],
        "Candidate: " + event["candidate_id"],
        "Source scope: " + event["source_scope"],
        "Symbol: " + event["symbol"],
        "Direction: " + event["direction"],
        "Horizon: " + event["horizon"],
        "Setup: " + event["setup_version"],
        "Decision UTC: " + times["decision_at"],
        "Score: " + score_line,
    ] + gate_lines + plan_lines
    message = "\n".join(lines)
    if len(message) > 3900:
        raise ContractError("SIGNAL_MESSAGE_TEXT_TOO_LONG")
    return message

class DeliveryCoordinator:
    """Synchronous one-attempt step; the caller owns scheduling outside this.

    Must prove durable attempt reservation before HTTP. Crash after reservation
    but before outcome = UNKNOWN_DELIVERY, never an automatic retry. 429 alone
    is retryable after the server interval, maximum 3 attempts per destination.
    """

    def __init__(self, *, store, config, flags=None, permit=None,
                 head_sha=None, clock=None, transports=None, simulation=False):
        config.validate()
        self.store = store
        self.config = config
        self.flags = flags if flags is not None else RuntimeFlags()
        self.permit = permit
        self.head_sha = head_sha
        self.clock = clock if clock is not None else (lambda: datetime.now(timezone.utc))
        self.simulation = simulation
        self.transports = transports if transports is not None else {}
        self._last_attempt = {}

    def _transport(self, bot):
        if bot not in self.transports:
            if self.simulation:
                raise ContractError("OFFLINE_FAKE_TRANSPORT_REQUIRED")
            token = (self.config.signals_token if bot == "SIGNALS"
                     else self.config.analytics_token if bot == "ANALYTICS"
                     else self.config.interactive_token)
            self.transports[bot] = TelegramHTTP(token)
        return self.transports[bot]

    def _action(self, bot):
        return "SIGNALS" if bot == "SIGNALS" else "ANALYTICS"

    def _chat(self, destination):
        return {"A": self.config.signals_chat_a,
                "B": self.config.signals_chat_b,
                "C": self.config.analytics_chat}[destination]

    def step(self, event, destination, *, network_available=True):
        if not self.simulation:
            ensure_event(event)
            if event["source_scope"] != "APPROVED_REAL_SOURCE":
                raise ContractError("SYNTHETIC_EVENT_LIVE_DISPATCH_FORBIDDEN")
            raise ContractError("VERIFIED_UPSTREAM_READBACK_REQUIRED")
        return self._step(event, destination, network_available=network_available)

    def step_verified(self, upstream, identity, expected_sha, destination, *, network_available=True):
        if type(self.store) is not LocalOutbox or type(upstream) is not VerifiedUpstream:
            raise ContractError("LOCAL_VERIFIED_CUSTODY_REQUIRED")
        event = upstream.read(identity, expected_sha)
        return self._step(event, destination, network_available=network_available)

    def _step(self, event, destination, *, network_available):
        ensure_event(event)
        jobs = {job.destination: job for job in plan(event)}
        if destination not in jobs:
            raise ContractError("UNAUTHORIZED_DESTINATION_FOR_CANDIDATE")
        job = jobs[destination]
        if not self.simulation:
            if event["source_scope"] != "APPROVED_REAL_SOURCE":
                raise ContractError("SYNTHETIC_EVENT_LIVE_DISPATCH_FORBIDDEN")
            require_live_permission(flags=self.flags, permit=self.permit,
                                    head_sha=self.head_sha, action=self._action(job.bot_id))
        # Reuse the readback-verified outbox and stable per-event identities.
        event_key = _key("event", digest(event["detection_event_key"].encode("utf-8")))
        _claim(self.store, event_key, {
            "schema": "zs05.event-dedup.v1",
            "detection_event_key": event["detection_event_key"],
            "candidate_id": event["candidate_id"], "event_sha256": job.event_sha256,
        })
        job_key = _key("delivery", job.delivery_id)
        _claim(self.store, job_key, {
            "schema": "zs05.delivery-plan.v1", "candidate_id": job.candidate_id,
            "signal_id": job.signal_id, "bot_id": job.bot_id,
            "destination_label": job.destination,
            "payload_sha256": job.payload_sha256, "kind": job.kind,
            "event_sha256": job.event_sha256,
        })
        now = utc_now(self.clock)
        count = 0
        for attempt_no in range(1, MAX_ATTEMPTS + 1):
            attempt_key = _key("attempt", digest(
                (job.delivery_id + ":" + str(attempt_no)).encode("ascii")))
            started = self.store.read(attempt_key)
            if started is None:
                count = attempt_no
                break
            outcome_key = _key("outcome", digest(
                (job.delivery_id + ":" + str(attempt_no)).encode("ascii")))
            outcome_bytes = self.store.read(outcome_key)
            if outcome_bytes is None:
                return {"status": "UNKNOWN_DELIVERY", "reason": "ATTEMPT_STARTED_WITHOUT_RECEIPT",
                        "delivery_id": job.delivery_id}
            try:
                last = __import__("json").loads(outcome_bytes)
            except (ValueError, TypeError):
                raise ContractError("OUTBOX_RECEIPT_INVALID") from None
            if last.get("status") in ("ACCEPTED", "PERMANENT_FAILURE", "UNKNOWN_DELIVERY"):
                return {"status": last["status"], "delivery_id": job.delivery_id,
                        "receipt": last}
            if last.get("status") != "RATE_LIMITED":
                raise ContractError("OUTBOX_RECEIPT_INVALID")
            retry_after = last.get("retry_after_at")
            if retry_after is None or parse_utc(retry_after, "RETRY_AFTER") > parse_utc(now, "NOW"):
                return {"status": "RATE_LIMITED", "delivery_id": job.delivery_id,
                        "retry_after_at": retry_after}
        if count == 0:
            return {"status": "MAX_ATTEMPTS_EXCEEDED", "delivery_id": job.delivery_id}
        # An offline scheduler can defer before any attempt is reserved. An
        # error after reservation remains ambiguous and must not be replayed.
        if network_available is not True:
            return {"status": "PENDING_OFFLINE", "delivery_id": job.delivery_id}
        # Throttle independently per bot AND per destination; no sleeping/spin.
        moment = parse_utc(now, "DISPATCH_ATTEMPT")
        for identity in ("BOT:" + job.bot_id, "DEST:" + job.destination):
            previous = self._last_attempt.get(identity)
            if previous is not None and (moment - previous).total_seconds() < 1:
                return {"status": "LOCAL_RATE_LIMITED", "delivery_id": job.delivery_id}
        attempt_id = digest((job.delivery_id + ":" + str(count)).encode("ascii"))
        attempt_key = _key("attempt", attempt_id)
        won = _claim(self.store, attempt_key, {
            "schema": "zs05.attempt-start.v1",
            "delivery_attempt_id": attempt_id, "delivery_id": job.delivery_id,
            "candidate_id": job.candidate_id, "bot_id": job.bot_id,
            "destination_label": job.destination, "attempt_no": count,
            "dispatch_attempt_at": now, "payload_sha256": job.payload_sha256,
        })
        if not won:
            return {"status": "UNKNOWN_DELIVERY", "reason": "ATTEMPT_ALREADY_RESERVED",
                    "delivery_id": job.delivery_id}
        for identity in ("BOT:" + job.bot_id, "DEST:" + job.destination):
            self._last_attempt[identity] = moment
        try:
            transport = self._transport(job.bot_id)
            if job.kind == "SIGNAL_TEXT":
                outcome = transport.send_text(
                    self._chat(destination), _signal_text(event),
                    flags=self.flags, permit=self.permit, head_sha=self.head_sha,
                    action="SIGNALS")
            else:
                report = make_document(event)
                outcome = transport.send_document(
                    self._chat(destination), report["caption"],
                    report["manifest"]["file_name"], report["document"],
                    flags=self.flags, permit=self.permit, head_sha=self.head_sha,
                    action="ANALYTICS")
        except Exception:
            # Once an attempt was durably reserved, ANY error is ambiguous.
            # No transport exception text is exposed; token is never logged.
            outcome = None
        recorded_at = utc_now(self.clock)
        status = outcome.status if outcome is not None else "UNKNOWN_DELIVERY"
        receipt = {
            "schema": "zs05.delivery-receipt.v1",
            "delivery_id": job.delivery_id,
            "delivery_attempt_id": attempt_id,
            "bot_id": job.bot_id,
            "destination_label": job.destination,
            "candidate_id": job.candidate_id, "signal_id": job.signal_id,
            "status": status, "dispatch_attempt_at": now,
            "receipt_recorded_at": recorded_at,
            "telegram_accepted_at": recorded_at if status == "ACCEPTED" else None,
            "telegram_message_date_at": (outcome.message_date_at if status == "ACCEPTED" else None),
            "telegram_message_id": (outcome.message_id if status == "ACCEPTED" else None),
            "retry_after_at": (utc_now(lambda: moment + timedelta(
                seconds=outcome.retry_after_s)) if status == "RATE_LIMITED" else None),
            "reason_code": (None if status == "ACCEPTED" else
                            ("RATE_LIMIT_429" if status == "RATE_LIMITED" else
                             "DELIVERY_OUTCOME_UNCERTAIN" if status == "UNKNOWN_DELIVERY"
                             else "API_REJECTED")),
        }
        try:
            _claim(self.store, _key("outcome", attempt_id), receipt)
        except Exception:
            return {"status": "UNKNOWN_DELIVERY", "reason": "OUTCOME_READBACK_FAILED",
                    "delivery_id": job.delivery_id}
        return {"status": status, "delivery_id": job.delivery_id, "receipt": receipt}
