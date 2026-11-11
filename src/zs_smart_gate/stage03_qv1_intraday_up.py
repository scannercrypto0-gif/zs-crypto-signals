"""Intraday UP qualification preparation using the existing Setup detector."""
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

from . import setup021
from .binance_live import to_candles
from .core import MarketSnapshot
from .mtf_contracts import CandleWindow, ReconciliationTolerance, reconcile
from .stage03_qv1_boundary import evaluate_boundary
from .stage05_contracts import ContractError, canonical, digest, parse_utc
from .stage05_custody import LocalOutbox

VERSION = "QV1-B-INTRADAY-UP-POLICY-DRAFT-v1"
RULES = MappingProxyType({"SETUP_UP": setup021.evaluate})
RULE_SHA256 = digest(canonical({"SETUP_UP": setup021.VERSION, "parameters": setup021.CONFIG_SHA256,
                               "implementation_sha256": digest(Path(setup021.__file__).read_bytes().replace(b"\r\n", b"\n"))}))
POLICY_SHA256 = digest(canonical({"version": VERSION, "rule_sha256": RULE_SHA256,
                                  "scope_authority": "ISSUE51#6792337804",
                                  "qualification_authority": None}))


@dataclass(frozen=True)
class Inputs:
    evidence: dict
    klines: list
    market: MarketSnapshot
    parent: CandleWindow
    context: tuple[CandleWindow, ...]
    tolerance: ReconciliationTolerance
    received_at: datetime


def _json_value(value):
    if isinstance(value, dict):
        return {k: _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    if isinstance(value, (Decimal, datetime)):
        return str(value)
    return value


def inputs_sha256(data):
    return digest(canonical(_json_value({
        "klines": data.klines, "market": asdict(data.market), "parent": asdict(data.parent),
        "context": [asdict(bar) for bar in data.context], "tolerance": asdict(data.tolerance),
        "received_at": data.received_at,
    })))


def evaluate_up(data: Inputs, *, policy_sha256: str):
    """Recompute detection on the exact joined input. Real promotion stays off."""
    if policy_sha256 != POLICY_SHA256:
        raise ContractError("QV1_UP_POLICY_FINGERPRINT_MISMATCH")
    row = data.evidence
    if (row["horizon"], row["direction"]) != ("INTRADAY", "UP"):
        raise ContractError("QV1_UP_PATH_DISABLED")
    if row["source"].get("joined_inputs_sha256") != inputs_sha256(data):
        raise ContractError("QV1_UP_JOINED_INPUT_HASH_MISMATCH")
    intake = evaluate_boundary(row)
    decision = parse_utc(row["decision_at"])
    if data.market.observed_at > decision:
        raise ContractError("QV1_UP_FUTURE_MARKET")
    if data.parent.timeframe != "30m" or data.parent.close_at != parse_utc(row["event_close_at"]):
        raise ContractError("QV1_UP_PARENT_IDENTITY_MISMATCH")
    feed = row["source"]["feed"]
    if any(bar.source_id != feed for bar in (data.parent, *data.context)):
        raise ContractError("QV1_UP_MIXED_JOINED_FEED")
    if any(bar.timeframe not in ("1h", "4h") or bar.errors_at(decision) for bar in data.context):
        raise ContractError("QV1_UP_INVALID_CONTEXT")
    for bar in (data.parent, *data.context):
        frame = row["candles"].get(bar.timeframe)
        if frame is None or any(parse_utc(frame[key]) != getattr(bar, key)
                                for key in ("open_at", "close_at", "received_at", "available_at")):
            raise ContractError("QV1_UP_FRAME_METADATA_MISMATCH")
    context_complete = sorted(bar.timeframe for bar in data.context) == ["1h", "4h"]
    result = RULES["SETUP_UP"](symbol=row["symbol"], klines=data.klines, market=data.market,
                               received_at=data.received_at, decision_at=decision, partition="DEV")
    reason = result["reason_codes"][0]
    detection = "UNKNOWN"
    join_status = "NOT_VERIFIED"
    if reason in ("CLOSED_CAUSAL_TRIGGER", "NO_BREAKOUT", "NO_FALSE_TO_TRUE_TRANSITION"):
        children = [CandleWindow.from_five_minute(bar, source_id=feed)
                    for bar in to_candles(data.klines, data.received_at)[-6:]]
        trigger = row["candles"].get("5m")
        if trigger is None or any(parse_utc(trigger[key]) != getattr(children[-1], key)
                                  for key in ("open_at", "close_at", "received_at", "available_at")):
            raise ContractError("QV1_UP_TRIGGER_METADATA_MISMATCH")
        joined = reconcile(data.parent, children, decision, tolerance=data.tolerance)
        join_status = joined.status
        if joined.status == "PASS":
            detection = ("DETECTED_SIGNAL" if reason == "CLOSED_CAUSAL_TRIGGER"
                         else "RESEARCH_CANDIDATE")
    return {**intake, "setup_state": detection,
            "state": "UNKNOWN" if intake["state"] == "UNKNOWN" or not context_complete else detection,
            "policy_version": VERSION, "policy_sha256": POLICY_SHA256, "rule_sha256": RULE_SHA256,
            "setup_reason": reason, "context_complete": context_complete, "reconciliation": join_status,
            "setup_input_sha256": result["input_sha256"],
            "qualification_state": "UNKNOWN", "signal_id": None,
            "clock_qualification": "INDEPENDENT_WITNESS_POLICY_PENDING",
            "liquidity_qualification": "QUALIFICATION_CUTOFFS_PENDING"}


def persist_up(data: Inputs, store: LocalOutbox, *, policy_sha256: str):
    if type(store) is not LocalOutbox:
        raise ContractError("QV1_UP_LOCAL_CUSTODY_REQUIRED")
    result = evaluate_up(data, policy_sha256=policy_sha256)
    payload = canonical(result)
    key = "qualification-up/" + result["event_id"]
    store.create_if_absent(key, payload)
    if store.read(key) != payload:
        raise ContractError("QV1_UP_READBACK_CONFLICT")
    return {**result, "readback_sha256": digest(payload)}
