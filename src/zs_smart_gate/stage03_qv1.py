"""Qualification evidence intake. Numeric policy and live promotion remain gated."""
from datetime import timedelta

from .stage05_contracts import ContractError, canonical, digest, parse_utc

VERSION = "QV1-B-PROPOSAL-1"
FRAMES = {"INTRADAY": ("5m", "30m", "1h", "4h"),
          "SWING": ("1h", "4h", "1d", "1w")}
MINUTES = {"5m": 5, "30m": 30, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080}
COMPONENTS = {"INTRADAY": range(1, 7), "SWING": range(7, 13)}


def evaluate(record):
    """Validate provenance and report evidence states, never approve policy."""
    horizon, direction = record["horizon"], record["direction"]
    if (horizon not in FRAMES or direction not in ("UP", "DOWN")
            or record["symbol"] not in ("BTCUSDT", "ETHUSDT")
            or record["source_scope"] not in ("SYNTHETIC_TEST_ONLY", "APPROVED_REAL_SOURCE")
            or record["setup_version"] != "1.1"):
        raise ContractError("QV1_IDENTITY_INVALID")
    decision = parse_utc(record["decision_at"])
    source = record["source"]
    candles = record["candles"]
    manifest = digest(canonical(source))
    if manifest != record["source_sha256"] or source.get("symbol") != record["symbol"]:
        raise ContractError("QV1_SOURCE_IDENTITY_OR_SHA_INVALID")
    if source.get("candles_sha256") != digest(canonical(candles)):
        raise ContractError("QV1_CANDLES_NOT_BOUND_TO_SOURCE")
    if source.get("components_sha256") != digest(canonical(record["components"])):
        raise ContractError("QV1_COMPONENTS_NOT_BOUND_TO_SOURCE")
    if source.get("setup_state") != record["setup_state"]:
        raise ContractError("QV1_SETUP_NOT_BOUND_TO_SOURCE")
    close = parse_utc(record["event_close_at"])
    if close > decision:
        raise ContractError("QV1_FUTURE_EVENT")
    reasons = []
    for frame in FRAMES[horizon]:
        bar = candles.get(frame)
        if bar is None:
            reasons.append("MISSING_FRAME:" + frame)
            continue
        opened, closed, received, available = (
            parse_utc(bar[k]) for k in ("open_at", "close_at", "received_at", "available_at"))
        if (bar.get("closed") is not True or closed-opened != timedelta(minutes=MINUTES[frame])
                or not opened < closed <= received <= available <= decision):
            raise ContractError("QV1_CAUSAL_FRAME_INVALID:" + frame)
        trigger_frame = "30m" if horizon == "INTRADAY" else "4h"
        if frame == trigger_frame and closed != close:
            raise ContractError("QV1_EVENT_FRAME_MISMATCH")
    # Only the provenance fields are checked here. Passing them is not an
    # independent witness or approved liquidity evaluator.
    for name in ("liquidity", "clock"):
        receipt = source.get(name)
        if not isinstance(receipt, dict):
            reasons.append("MISSING_PROVENANCE:" + name)
        elif parse_utc(receipt["available_at"]) > decision:
            raise ContractError("QV1_FUTURE_PROVENANCE:" + name)
    ledger = {}
    for n in COMPONENTS[horizon]:
        component = f"N{n:02}"
        item = record["components"].get(component)
        if item is None:
            ledger[component] = {"status": "UNAVAILABLE", "reason": "INPUT_NOT_PROVIDED"}
        elif item.get("status") in ("PRESENT", "UNAVAILABLE") and item.get("reason"):
            if n == 3 and item["status"] == "PRESENT":
                raise ContractError("QV1_NUMERIC_N03_NOT_APPROVED")
            if item["status"] == "PRESENT" and parse_utc(item["as_of"]) > decision:
                raise ContractError("QV1_FUTURE_COMPONENT")
            ledger[component] = {"status": item["status"], "reason": item["reason"]}
        else:
            raise ContractError("QV1_COMPONENT_STATUS_INVALID")
    identity = [VERSION, record["source_scope"], "BINANCE_SPOT", record["symbol"],
                horizon, direction, record["setup_version"], close.isoformat()]
    event_id = digest(canonical(identity))
    setup = record["setup_state"]
    if setup not in ("RESEARCH_CANDIDATE", "DETECTED_SIGNAL", "REJECTED", "UNKNOWN"):
        raise ContractError("QV1_SETUP_STATE_INVALID")
    state = "UNKNOWN" if reasons else setup
    # Stable identity is distinct from the byte hash of a particular observation.
    return {"policy_version": VERSION, "source_sha256": manifest,
            "event_id": event_id, "candidate_id": "cand-" + event_id,
            "setup_state": setup, "state": state, "qualification": "POLICY_NOT_APPROVED",
            "signal_id": None, "score": None, "trade_plan": None,
            "component_statuses": ledger, "reasons": reasons + ["QV1_B_APPROVAL_REQUIRED"]}
