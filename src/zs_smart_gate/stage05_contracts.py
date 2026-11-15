"""Stage05 candidate/Signal/export wire contract. No qualification inference.

An upstream APPROVED qualification event is a separate authority. Existing
Stage03/PRE05 research results cannot be promoted into a Signal by this module.
No secrets, network, trading, timers, databases or Telegram calls.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re

SCHEMA = "zs.stage05.event.v1"
ARCHIVE_SCHEMA = "zs.stage05.analytics.v1"
UTC_PATTERN = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z\Z")
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_STATES = frozenset(("MISSING", "INVALID", "NOT_IMPLEMENTED", "PRESENT"))
EVENT_TIMES = (
    "decision_candle_open_at", "decision_candle_close_at", "received_at",
    "available_at", "decision_at", "record_created_at",
)
MAX_ARCHIVE_BYTES = 256 * 1024
SECRET_FIELD = re.compile(r"(token|secret|password|private_key|api_key|chat_id|access_key)", re.I)
BOT_TOKEN_VALUE = re.compile(r"(?<![A-Za-z0-9_])[0-9]{5,15}:[A-Za-z0-9_-]{20,80}(?![A-Za-z0-9_])")
EVENT_FIELDS = frozenset((
    "schema", "event_type", "candidate_id", "signal_id",
    "detection_event_key", "qualification_status", "qualification_authority",
    "qualification_evidence_sha256", "source_scope", "source_manifest_id",
    "source_manifest_sha256", "scan_cycle_id", "candle_window_sha256",
    "quality_policy_version", "candidate_origin", "source_quality",
    "symbol", "direction", "horizon", "setup_version", "timestamps", "clock",
    "gates", "reject_reason_codes", "indicators", "score", "trade_plan",
    "source_metadata", "candle_metadata", "scan_metadata", "quality_metadata",
    "outcome_links",
))


class ContractError(ValueError):
    """Sanitized, never contains user values or credentials."""


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise ContractError("CANONICAL_JSON_INVALID") from None


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_id(value, label="ID"):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ContractError("INVALID_" + label)
    return value


def parse_utc(value, label="UTC"):
    if not isinstance(value, str) or not UTC_PATTERN.fullmatch(value):
        raise ContractError("EXPLICIT_UTC_Z_REQUIRED:" + label)
    try:
        value_dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ContractError("INVALID_UTC:" + label) from None
    return value_dt


def utc_now(clock):
    value = clock()
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ContractError("MEASURED_UTC_CLOCK_REQUIRED")
    value = value.astimezone(timezone.utc)
    # Preserve measured fractional precision; never add fake milliseconds.
    return value.isoformat(timespec=("microseconds" if value.microsecond else "seconds")).replace("+00:00", "Z")


def _deny_secret_fields(value, depth=0):
    if depth > 10:
        raise ContractError("ARCHIVE_NESTING_EXCESSIVE")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or SECRET_FIELD.search(key):
                raise ContractError("SENSITIVE_ARCHIVE_FIELD_FORBIDDEN")
            _deny_secret_fields(item, depth+1)
    elif isinstance(value, list):
        for item in value:
            _deny_secret_fields(item, depth+1)
    elif isinstance(value, str) and BOT_TOKEN_VALUE.search(value):
        raise ContractError("BOT_TOKEN_VALUE_IN_ARCHIVE_FORBIDDEN")


def ensure_event(event):
    if not isinstance(event, dict) or event.get("schema") != SCHEMA:
        raise ContractError("EVENT_SCHEMA_UNSUPPORTED")
    if set(event) - EVENT_FIELDS:
        raise ContractError("UNRECOGNIZED_ARCHIVE_FIELDS")
    _deny_secret_fields(event)
    for meta in ("source_metadata", "candle_metadata", "scan_metadata", "quality_metadata"):
        if not isinstance(event.get(meta), dict) or not event[meta]:
            raise ContractError("SOURCE_CANDLE_SCAN_QUALITY_METADATA_REQUIRED")
    if event.get("outcome_links") is not None and not isinstance(event["outcome_links"], list):
        raise ContractError("OUTCOME_LINKS_INVALID")
    candidate = safe_id(event.get("candidate_id"), "CANDIDATE_ID")
    key = safe_id(event.get("detection_event_key"), "DETECTION_EVENT_KEY")
    signal = event.get("signal_id")
    state = event.get("qualification_status")
    if state not in ("QUALIFIED", "REJECTED"):
        raise ContractError("QUALIFICATION_STATUS_INVALID")
    if state == "QUALIFIED":
        safe_id(signal, "SIGNAL_ID")
        if (event.get("qualification_authority") != "EXPLICIT_APPROVED_UPSTREAM"
                or event.get("qualification_evidence_sha256") is None
                or not isinstance(event.get("qualification_evidence_sha256"), str)
                or not SHA.fullmatch(event["qualification_evidence_sha256"])):
            raise ContractError("APPROVED_UPSTREAM_QUALIFICATION_REQUIRED")
        if event.get("event_type") != "QUALIFIED_SIGNAL":
            raise ContractError("QUALIFIED_EVENT_TYPE_MISMATCH")
    elif signal is not None or event.get("event_type") != "REJECTED_CANDIDATE":
        raise ContractError("REJECTED_MUST_NOT_HAVE_SIGNAL_ID")
    if (event.get("candidate_origin") != "QUALIFICATION_CANDIDATE"
            or event.get("source_quality") != "VALIDATED"):
        raise ContractError("INVALID_RAW_TELEMETRY_NOT_AN_ANALYTICS_CANDIDATE")
    if event.get("source_scope") not in ("SYNTHETIC_TEST_ONLY", "APPROVED_REAL_SOURCE"):
        raise ContractError("SOURCE_SCOPE_NOT_AUTHORIZED")
    if event.get("source_scope") == "APPROVED_REAL_SOURCE":
        safe_id(event.get("source_manifest_id"), "SOURCE_MANIFEST_ID")
        safe_id(event.get("scan_cycle_id"), "SCAN_CYCLE_ID")
        h = event.get("source_manifest_sha256")
        w = event.get("candle_window_sha256")
        if (not isinstance(h, str) or not SHA.fullmatch(h)
                or not isinstance(w, str) or not SHA.fullmatch(w)
                or not isinstance(event.get("quality_policy_version"), str)
                or not event["quality_policy_version"]):
            raise ContractError("REAL_SOURCE_MANIFEST_AND_CANDLE_QUALITY_REQUIRED")
    if event.get("candidate_id") == event.get("signal_id"):
        raise ContractError("SEPARATE_CANDIDATE_SIGNAL_KEYS_REQUIRED")
    times = event.get("timestamps")
    if not isinstance(times, dict):
        raise ContractError("TIMESTAMPS_REQUIRED")
    for name in EVENT_TIMES:
        parse_utc(times.get(name), name)
    for optional in ("first_watch_at", "candidate_created_at"):
        if times.get(optional) is not None:
            parse_utc(times[optional], optional)
    if not (
        parse_utc(times["decision_candle_open_at"]) <
        parse_utc(times["decision_candle_close_at"]) <=
        parse_utc(times["received_at"]) <=
        parse_utc(times["available_at"]) <=
        parse_utc(times["decision_at"]) <=
        parse_utc(times["record_created_at"])
    ):
        raise ContractError("CAUSAL_EVENT_TIMELINE_INVALID")
    clock = event.get("clock")
    if (not isinstance(clock, dict) or clock.get("source") not in ("SYNTHETIC_CLOCK", "MEASURED_CLOCK")
            or clock.get("precision") not in ("SECONDS", "MILLISECONDS", "MICROSECONDS")
            or isinstance(clock.get("offset_ms"), bool)
            or not isinstance(clock.get("offset_ms"), (int, float))
            or isinstance(clock.get("uncertainty_ms"), bool)
            or not isinstance(clock.get("uncertainty_ms"), (int, float))
            or clock["uncertainty_ms"] < 0):
        raise ContractError("CLOCK_PROVENANCE_REQUIRED")
    if event["source_scope"] == "APPROVED_REAL_SOURCE" and clock["source"] != "MEASURED_CLOCK":
        raise ContractError("REAL_MEASURED_CLOCK_REQUIRED")
    if not isinstance(event.get("gates"), list) or not event["gates"]:
        raise ContractError("GATE_DECISIONS_REQUIRED")
    for gate in event["gates"]:
        if (not isinstance(gate, dict) or not isinstance(gate.get("gate_id"), str)
                or gate.get("state") not in ("PASS", "FAIL", "UNKNOWN")
                or not isinstance(gate.get("reason_codes"), list)):
            raise ContractError("GATE_DECISION_INVALID")
    if state == "QUALIFIED" and any(x["state"] != "PASS" for x in event["gates"]):
        raise ContractError("QUALIFICATION_HAS_NONPASS_GATE")
    if state == "REJECTED" and not any(x["state"] == "FAIL" for x in event["gates"]):
        raise ContractError("REJECTED_REQUIRES_FAILED_GATE")
    indicators = event.get("indicators")
    if not isinstance(indicators, list):
        raise ContractError("INDICATORS_REQUIRED")
    for row in indicators:
        if (not isinstance(row, dict) or not isinstance(row.get("indicator_id"), str)
                or row.get("availability") not in SOURCE_STATES
                or "raw_value" not in row or "threshold" not in row
                or row.get("evaluation") not in ("PASS", "FAIL", "UNKNOWN")
                or not isinstance(row.get("reason_codes"), list)
                or (row["availability"] != "PRESENT" and row.get("value") is not None)):
            raise ContractError("INDICATOR_AVAILABILITY_INVALID")
        if row["availability"] == "PRESENT":
            for k in ("unit", "timeframe", "source", "as_of", "version"):
                if not isinstance(row.get(k), str) or not row[k]:
                    raise ContractError("PRESENT_INDICATOR_METADATA_REQUIRED")
            parse_utc(row["as_of"], "INDICATOR_AS_OF")
            if parse_utc(row["as_of"]) > parse_utc(times["decision_at"]):
                raise ContractError("FUTURE_INDICATOR_FORBIDDEN")
    for field in ("symbol", "direction", "horizon", "setup_version"):
        if not isinstance(event.get(field), str) or not event[field]:
            raise ContractError("EVENT_FIELD_REQUIRED:" + field)
    if event["direction"] not in ("UP", "DOWN"):
        raise ContractError("DIRECTION_INVALID")
    if not isinstance(event.get("reject_reason_codes"), list):
        raise ContractError("REASONS_REQUIRED")
    if state == "REJECTED" and not event["reject_reason_codes"]:
        raise ContractError("REJECTED_REASON_REQUIRED")
    if event.get("score") is not None:
        if not isinstance(event.get("score"), dict) or not event["score"].get("approved"):
            raise ContractError("UNAPPROVED_SCORE_FORBIDDEN")
    if event.get("trade_plan") is not None:
        if not isinstance(event["trade_plan"], dict) or event["trade_plan"].get("approved") is not True:
            raise ContractError("UNAPPROVED_TRADE_PLAN_FORBIDDEN")
    return candidate, key


def research_only_block(source):
    """Explicitly reject Stage03/PRE05 as qualified, even with an injected ID."""
    if not isinstance(source, dict):
        raise ContractError("RESEARCH_SOURCE_INVALID")
    if (source.get("source_scope") != "APPROVED_REAL_SOURCE"
            or source.get("qualified") is not True
            or source.get("score_status") == "SCORE_UNAVAILABLE"
            or source.get("status") in ("RESEARCH_CANDIDATE", "REJECTED",
                                        "RESEARCH_ONLY_READY_FOR_LOCAL_APPLICATION_JOURNAL")):
        raise ContractError("RESEARCH_ONLY_CANNOT_BECOME_SIGNAL")
    raise ContractError("UPSTREAM_QUALIFICATION_ADAPTER_NOT_APPROVED")


def make_document(event):
    ensure_event(event)
    # Do not embed bot tokens/chat ids/private owner identifiers in analytics.
    raw = canonical({"schema": ARCHIVE_SCHEMA, "event": event})
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise ContractError("ARCHIVE_DOCUMENT_EXCEEDS_CONTRACT_LIMIT")
    sha = digest(raw)
    head = {
        "schema": ARCHIVE_SCHEMA, "candidate_id": event["candidate_id"],
        "signal_id": event["signal_id"], "qualification_status": event["qualification_status"],
        "sha256": sha, "size_bytes": len(raw),
        "file_name": "zs05-" + sha[:24] + ".json",
    }
    # Telegram Desktop message text is a WRAPPER, not native standalone JSON.
    reasons = ",".join(event["reject_reason_codes"])
    summary = (reasons[:240] + ("...(see attached JSON)" if len(reasons) > 240 else "")
               if reasons else "NONE")
    caption = ("ZS05_ARCHIVE_V1 sha256=" + sha + " candidate_id=" +
               event["candidate_id"] + " state=" + event["qualification_status"] +
               " reject_reasons=" + summary)
    if len(caption.encode("utf-8")) > 1024:
        raise ContractError("ARCHIVE_CAPTION_TOO_LARGE")
    return {"manifest": head, "document": raw, "caption": caption}


def sql_projection(event):
    """SQL Server-compatible normalized rows, not an SQL import itself."""
    ensure_event(event)
    candidate = {
        "candidate_id": event["candidate_id"],
        "detection_event_key": event["detection_event_key"],
        "asset_symbol": event["symbol"],
        "qualification_status": event["qualification_status"],
        "decision_at": event["timestamps"]["decision_at"],
        "decision_snapshot_sha256": digest(canonical(event)),
    }
    signals = [] if event["signal_id"] is None else [{
        "signal_id": event["signal_id"], "candidate_id": event["candidate_id"],
    }]
    features = [{
        "candidate_id": event["candidate_id"], "indicator_id": r["indicator_id"],
        "availability": r["availability"], "value": r.get("value"),
        "unit": r.get("unit"), "timeframe": r.get("timeframe"),
        "source": r.get("source"), "as_of": r.get("as_of"),
        "version": r.get("version"), "evaluation": r["evaluation"],
        "raw_value": r["raw_value"], "threshold": r["threshold"],
        "reason_codes": list(r["reason_codes"]),
    } for r in event["indicators"]]
    return {"candidates": [candidate], "signals": signals,
            "indicator_values": features, "candidate_decisions": [
                {"candidate_id": event["candidate_id"], "gate_id": g["gate_id"],
                 "state": g["state"], "reason_codes": g["reason_codes"]}
                for g in event["gates"]
            ]}


def extract_desktop_export(export, documents):
    """Deterministic *bounded* extraction from Telegram Desktop result.json.

    Documents must separately be retained and supplied; missing files
    invalidate extraction. Stage06B retains full real export/import acceptance.
    """
    if not isinstance(export, dict) or not isinstance(export.get("messages"), list):
        raise ContractError("DESKTOP_EXPORT_WRAPPER_INVALID")
    if not isinstance(documents, dict):
        raise ContractError("DOCUMENT_MAP_REQUIRED")
    by_candidate = {}
    receipts = []
    for message in export["messages"]:
        if not isinstance(message, dict):
            raise ContractError("DESKTOP_MESSAGE_INVALID")
        text = message.get("text")
        if isinstance(text, list):
            text = "".join(x if isinstance(x, str) else x.get("text", "")
                           for x in text if isinstance(x, (str, dict)))
        if not isinstance(text, str) or "ZS05_ARCHIVE_V1 sha256=" not in text:
            continue
        match = re.search(r"ZS05_ARCHIVE_V1 sha256=([0-9a-f]{64}) candidate_id=([A-Za-z0-9._:-]+)", text)
        if not match:
            raise ContractError("ARCHIVE_MANIFEST_TEXT_INVALID")
        sha, cid = match.groups()
        file_name = message.get("file")
        if not isinstance(file_name, str) or file_name not in documents:
            raise ContractError("EXPORT_ATTACHMENT_MISSING")
        raw = documents[file_name]
        if not isinstance(raw, bytes) or digest(raw) != sha:
            raise ContractError("EXPORT_ATTACHMENT_SHA_MISMATCH")
        try:
            archive = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise ContractError("EXPORT_DOCUMENT_JSON_INVALID") from None
        if canonical(archive) != raw or archive.get("schema") != ARCHIVE_SCHEMA:
            raise ContractError("EXPORT_DOCUMENT_NOT_CANONICAL")
        event = archive["event"]
        ensure_event(event)
        if event["candidate_id"] != cid:
            raise ContractError("EXPORT_CANDIDATE_LINK_CONFLICT")
        existing = by_candidate.setdefault(cid, raw)
        if existing != raw:
            raise ContractError("EXPORT_DUPLICATE_CONTENT_CONFLICT")
        receipt = {"candidate_id": cid, "archive_sha256": sha,
                   "telegram_export_message_id": message.get("id")}
        if receipt not in receipts:
            receipts.append(receipt)
    return {"schema": "zs.stage05.desktop-extract.v1",
            "archive_count": len(by_candidate),
            "events_ndjson": b"\n".join(by_candidate[k] for k in sorted(by_candidate)) + (b"\n" if by_candidate else b""),
            "receipts": receipts,
            "stage06b_real_roundtrip_verified": False}
