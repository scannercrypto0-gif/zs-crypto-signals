"""Stage06A versioned evidence-bound, offline-only outcome adapter.

Do not treat content hashes as independent exchange authentication.
No signals, orders, network activity, or outcome-derived qualification.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
import re

from .stage03_r0_identity import EvaluationIdentity
from .stage03_research_handoff import verify_handoff
from .stage05_contracts import ContractError, SHA, canonical, digest, ensure_event, parse_utc
from .stage06a_outcomes import ClosedBar, TradeLevels, evaluate_outcome

VERSION = "zs.stage06a.evidence-bound-outcome.v1"
BAR_SCHEMA = "zs.stage06a.closed-bars.v1"
RESEARCH_RECEIPT = "zs.stage06a.research-availability.v1"
DELIVERY_RECEIPT = "zs.stage06a.delivery-availability.v1"
MAX_RAW_BYTES = 8 * 1024 * 1024
MAX_BARS = 20000
SYMBOL = re.compile(r"[A-Z0-9]{3,20}USDT\Z")


def _id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value):
        raise ContractError("STAGE06A_ID_INVALID")
    return value


def _sha(value: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ContractError("STAGE06A_SHA_INVALID")
    return value


def _stamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds" if value.microsecond else "seconds").replace("+00:00", "Z")


def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ContractError("STAGE06A_NUMERIC_SCALAR_REQUIRED")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ContractError("STAGE06A_NUMERIC_INVALID") from None
    if not number.is_finite() or number <= 0:
        raise ContractError("STAGE06A_NUMERIC_INVALID")
    return number


def _receipt(row, schema, identifiers):
    if not isinstance(row, dict) or row.get("schema") != schema:
        raise ContractError("STAGE06A_RECEIPT_SCHEMA_INVALID")
    if set(row) != set(identifiers) | {"schema", "available_at", "payload_sha256"}:
        raise ContractError("STAGE06A_RECEIPT_FIELDS_INVALID")
    for name, expected in identifiers.items():
        if row.get(name) != expected:
            raise ContractError("STAGE06A_RECEIPT_IDENTITY_MISMATCH")
    available = parse_utc(row["available_at"])
    sha = _sha(row["payload_sha256"])
    if digest(canonical({k: v for k, v in row.items() if k != "payload_sha256"})) != sha:
        raise ContractError("STAGE06A_RECEIPT_HASH_INVALID")
    return available, sha


def _bars(raw: bytes, expected_sha: str, *, symbol: str, source_manifest_sha: str,
          as_of: datetime):
    _sha(expected_sha)
    if not isinstance(raw, bytes) or len(raw) > MAX_RAW_BYTES or not raw:
        raise ContractError("STAGE06A_BAR_CAPTURE_INVALID")
    if digest(raw) != expected_sha:
        raise ContractError("STAGE06A_BAR_CAPTURE_SHA_MISMATCH")
    try:
        record = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ContractError("STAGE06A_BAR_JSON_INVALID") from None
    if not isinstance(record, dict) or canonical(record) != raw:
        raise ContractError("STAGE06A_BAR_NOT_CANONICAL")
    if (set(record) != {"schema", "venue", "symbol", "source_manifest_sha256",
                        "timeframe", "candles"}
            or record["schema"] != BAR_SCHEMA or record["venue"] != "BINANCE_SPOT"
            or record["symbol"] != symbol
            or record["source_manifest_sha256"] != source_manifest_sha
            or record["timeframe"] not in ("5m", "15m", "30m", "1h", "4h")
            or not isinstance(record["candles"], list)
            or len(record["candles"]) > MAX_BARS):
        raise ContractError("STAGE06A_BAR_SOURCE_IDENTITY_INVALID")
    checked = []
    for item in record["candles"]:
        if not isinstance(item, dict) or set(item) != {
                "open_at", "close_at", "available_at", "open", "high", "low", "close", "closed"}:
            raise ContractError("STAGE06A_BAR_FIELDS_INVALID")
        bar = ClosedBar(
            parse_utc(item["open_at"]), parse_utc(item["close_at"]),
            parse_utc(item["available_at"]),
            _decimal(item["open"]), _decimal(item["high"]),
            _decimal(item["low"]), _decimal(item["close"]), item["closed"])
        if type(item["closed"]) is not bool:
            raise ContractError("STAGE06A_BAR_CLOSED_BOOL_REQUIRED")
        try:
            bar.validate()
        except ValueError:
            raise ContractError("STAGE06A_BAR_NOT_FINALIZED") from None
        if bar.close_at > as_of or bar.available_at > as_of:
            raise ContractError("STAGE06A_FUTURE_BAR_FORBIDDEN")
        if checked and bar.open_at != checked[-1].close_at:
            raise ContractError("STAGE06A_BAR_GAP_OR_OVERLAP")
        checked.append(bar)
    return checked, record["timeframe"]


def _plan(data, direction):
    if not isinstance(data, dict) or data.get("approved") is not True:
        return None
    if not all(k in data for k in ("entry_zone", "stop_loss", "tp1")):
        return None
    try:
        plan = TradeLevels(direction,
                           _decimal(data["entry_zone"]),
                           _decimal(data["stop_loss"]),
                           _decimal(data["tp1"]))
        plan.validate()
    except (ContractError, ValueError):
        return None
    return plan


def evaluate_source_bound(*, record: dict, record_kind: str,
                          bars_raw: bytes, bars_sha256: str, as_of: str,
                          receipt: dict | None = None,
                          research_identity: dict | None = None,
                          research_plan: dict | None = None) -> dict:
    """Evaluate provably pinned evidence, not market truth or executed fills.

    A genuine Stage05 QUALIFIED event requires a separate hash-bound accepted
    delivery receipt; human-read time is not inferred. Research POLICY_HOLD
    requires a distinct research availability receipt and explicit scenario
    levels, never an implied qualification. Always no orders.
    """
    now = parse_utc(as_of)
    if not isinstance(record, dict):
        raise ContractError("STAGE06A_RECORD_INVALID")

    if record_kind == "STAGE05_EVENT":
        ensure_event(record)
        symbol = record["symbol"]
        candidate_id, signal_id = record["candidate_id"], record["signal_id"]
        manifest_sha = _sha(record["source_manifest_sha256"])
        record_sha = digest(canonical(record))
        if record.get("qualification_status") == "QUALIFIED":
            if record.get("source_scope") != "APPROVED_REAL_SOURCE":
                raise ContractError("STAGE06A_REAL_SOURCE_REQUIRED")
            if receipt is None:
                raise ContractError("STAGE06A_DELIVERY_RECEIPT_REQUIRED")
            available, availability_sha = _receipt(
                receipt, DELIVERY_RECEIPT,
                {"candidate_id": candidate_id, "signal_id": signal_id,
                 "event_sha256": record_sha})
            if available < parse_utc(record["timestamps"]["available_at"]):
                raise ContractError("STAGE06A_DELIVERY_BEFORE_SOURCE")
            plan = _plan(record.get("trade_plan"), "LONG" if record["direction"] == "UP" else "SHORT")
        else:
            if receipt is not None or research_plan is not None:
                raise ContractError("STAGE06A_REJECTED_NO_SIGNAL_PLAN")
            available = parse_utc(record["timestamps"]["available_at"])
            availability_sha = None
            plan = None
        mode = "QUALIFIED_EVENT_RESEARCH_OUTCOME" if signal_id else "REJECTED_NO_SIGNAL"
    elif record_kind == "R0_RESEARCH_HANDOFF":
        verify_handoff(record)
        if not isinstance(research_identity, dict) or set(research_identity) != {
                "symbol", "discriminator"}:
            raise ContractError("STAGE06A_RESEARCH_IDENTITY_REQUIRED")
        symbol = research_identity["symbol"]
        identity = EvaluationIdentity(
            symbol, parse_utc(record["parent_close_at"]),
            discriminator=research_identity["discriminator"])
        native = identity.as_dict()
        if (native["event_id"] != record["event_id"]
                or native["candidate_id"] != record["candidate_id"]
                or record["signal_id"] is not None):
            raise ContractError("STAGE06A_RESEARCH_IDENTITY_MISMATCH")
        if receipt is None:
            raise ContractError("STAGE06A_RESEARCH_RECEIPT_REQUIRED")
        manifest_sha = _sha(record["source_manifest_sha256"])
        available, availability_sha = _receipt(
            receipt, RESEARCH_RECEIPT,
            {"candidate_id": record["candidate_id"],
             "event_id": record["event_id"],
             "source_manifest_sha256": manifest_sha})
        if available < parse_utc(record["parent_close_at"]):
            raise ContractError("STAGE06A_RESEARCH_BEFORE_CLOSE")
        candidate_id, signal_id = record["candidate_id"], None
        record_sha = digest(canonical(record))
        if research_plan is not None:
            if not isinstance(research_plan, dict) or set(research_plan) != {
                    "direction", "entry", "stop", "target", "scenario_only"}:
                raise ContractError("STAGE06A_SCENARIO_FIELDS_INVALID")
            if research_plan["scenario_only"] is not True:
                raise ContractError("STAGE06A_SCENARIO_ONLY_REQUIRED")
            plan = TradeLevels(research_plan["direction"],
                               _decimal(research_plan["entry"]),
                               _decimal(research_plan["stop"]),
                               _decimal(research_plan["target"]))
            try:
                plan.validate()
            except ValueError:
                raise ContractError("STAGE06A_SCENARIO_PLAN_INVALID") from None
        else:
            plan = None
        mode = "POLICY_HOLD_RESEARCH_SCENARIO"
    else:
        raise ContractError("STAGE06A_RECORD_KIND_INVALID")

    if now < available:
        raise ContractError("STAGE06A_ASOF_PRECEDES_AVAILABILITY")
    if not SYMBOL.fullmatch(symbol):
        raise ContractError("STAGE06A_SYMBOL_INVALID")
    bars, timeframe = _bars(bars_raw, bars_sha256, symbol=symbol,
                            source_manifest_sha=manifest_sha, as_of=now)
    evaluated = evaluate_outcome(plan, available, now, bars) if plan else None
    result = {
        "schema": VERSION, "record_kind": record_kind, "mode": mode,
        "candidate_id": candidate_id, "signal_id": signal_id,
        "symbol": symbol, "source_manifest_sha256": manifest_sha,
        "source_record_sha256": record_sha, "closed_bars_sha256": bars_sha256,
        "availability_receipt_sha256": availability_sha,
        "available_at": _stamp(available), "as_of": _stamp(now),
        "bar_timeframe": timeframe, "bar_count": len(bars),
        "status": evaluated.status if evaluated else "NO_APPROVED_OR_EXPLICIT_PLAN",
        "examined_bars": evaluated.examined_bars if evaluated else 0,
        "entry_bar_open_at": _stamp(evaluated.entry_bar_open_at) if evaluated and evaluated.entry_bar_open_at else None,
        "exit_bar_open_at": _stamp(evaluated.exit_bar_open_at) if evaluated and evaluated.exit_bar_open_at else None,
        "interpretation": "LEVEL_TOUCH_NOT_EXECUTED_FILL",
        "source_trust": "HASH_BOUND_CAPTURE_NOT_INDEPENDENT_AUTHENTICATION",
        "is_executed_trade": False, "is_production_signal": False,
        "note": evaluated.note if evaluated else "No numeric approved trade plan or explicitly marked research scenario",
    }
    result["result_sha256"] = digest(canonical(result))
    return result
