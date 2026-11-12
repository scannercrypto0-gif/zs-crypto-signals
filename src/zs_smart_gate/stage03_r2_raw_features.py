"""R2: decimal-safe raw features for the independent R1 closed-30m path.

Measurements are *not* gates, normalized scores, trade plans or real signals.
No external IO, no clock sampling, no retrieval and no implicit defaults for
missing prior candles/source tolerances, N03 numeric mapping or SEM semantics.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from .core import spread_bps, utc
from .mtf_contracts import available_closed_context
from .stage03_r0_identity import stamp
from .stage03_r1_closed_parent import (
    Closed30mItem, VERSION as EVALUATION_VERSION, evaluate_local_universe,
)
from .stage05_contracts import ContractError, canonical, digest
from .stage05_custody import LocalOutbox

VERSION = "zs.r2.raw-30m-features.v1"
HISTORICAL_WINDOW = 20  # descriptive RVOL_20 lookback; NOT a qualification limit
ZERO = Decimal("0")
HOUR = timedelta(hours=1)


def present(value, *, unit: str, frame: str, at: datetime) -> dict:
    if isinstance(value, (tuple, list)):
        value = [str(x) for x in value]
    else:
        value = str(value)
    return {"availability": "PRESENT", "raw_value": value, "unit": unit,
            "timeframe": frame, "as_of": stamp(at),
            "gate_result": "NOT_EVALUATED",
            "reason_codes": ["RAW_MEASUREMENT_NOT_APPROVED_QUALIFICATION_GATE"]}


def absent(reason: str, *, availability: str = "UNKNOWN", frame: str = "30m") -> dict:
    if availability not in ("UNKNOWN", "INSUFFICIENT_HISTORY", "NOT_IMPLEMENTED"):
        raise ContractError("R2_INVALID_FEATURE_AVAILABILITY")
    return {"availability": availability, "raw_value": None, "unit": None,
            "timeframe": frame, "as_of": None, "gate_result": "NOT_EVALUATED",
            "reason_codes": [reason]}


def _rvol(item: Closed30mItem, decision: datetime) -> dict:
    """Use prior 20 CLOSED and contiguous 30m parents, same source and PIT only."""
    history = sorted(item.previous_30m, key=lambda c: c.open_at)
    if len(history) < HISTORICAL_WINDOW:
        return {name: absent("PRIOR_20_CLOSED_30M_REQUIRED",
                             availability="INSUFFICIENT_HISTORY")
                for name in ("rvol_base_20", "rvol_quote_20")}
    window = history[-HISTORICAL_WINDOW:]
    expected = item.parent.open_at - timedelta(minutes=HISTORICAL_WINDOW * 30)
    for bar in window:
        if (bar.timeframe != "30m" or bar.source_id != item.parent.source_id
                or bar.open_at != expected or bar.errors_at(decision)):
            return {name: absent("HISTORICAL_FRAME_INVALID_OR_NOT_CAUSAL")
                    for name in ("rvol_base_20", "rvol_quote_20")}
        expected = bar.close_at
    if expected != item.parent.open_at:
        return {name: absent("HISTORICAL_30M_WINDOW_NOT_ADJACENT")
                for name in ("rvol_base_20", "rvol_quote_20")}
    features = {}
    for field, name in (("base_volume", "rvol_base_20"),
                        ("quote_volume", "rvol_quote_20")):
        mean = sum((getattr(bar, field) for bar in window), ZERO) / HISTORICAL_WINDOW
        features[name] = (present(getattr(item.parent, field) / mean,
                                  unit="RATIO_TO_PRIOR_20_30M_MEAN", frame="30m",
                                  at=item.parent.close_at)
                          if mean > ZERO else absent("PRIOR_VOLUME_BASELINE_ZERO"))
    return features


def raw_features(item: Closed30mItem, *, decision_at: datetime) -> dict:
    """Call only after R1 has confirmed exact integrity and causal availability."""
    decision = utc(decision_at)
    p = item.parent
    children = item.children
    if len(children) != 6 or p.errors_at(decision) or any(x.errors_at(decision) for x in children):
        raise ContractError("R2_RAW_INPUT_NOT_STRUCTURALLY_ADMITTED")
    span = p.high - p.low
    f: dict[str, dict] = {}
    if span > ZERO:
        measures = {
            "closing_location": ((p.close - p.low) / span, "RATIO_0_1"),
            "directional_close_location": ((p.close - p.low) / span, "UP_LOCATION_RATIO"),
            "body_to_range": (abs(p.close - p.open) / span, "RATIO_0_1"),
            "signed_body_to_range": ((p.close - p.open) / span, "SIGNED_RATIO"),
            "upper_wick_to_range": ((p.high - max(p.open, p.close)) / span, "RATIO_0_1"),
            "lower_wick_to_range": ((min(p.open, p.close) - p.low) / span, "RATIO_0_1"),
        }
        f.update({name: present(value, unit=unit, frame="30m", at=p.close_at)
                  for name, (value, unit) in measures.items()})
    else:
        f.update({name: absent("ZERO_30M_HIGH_LOW_RANGE") for name in (
            "closing_location", "directional_close_location", "body_to_range",
            "signed_body_to_range", "upper_wick_to_range", "lower_wick_to_range",
        )})

    f["parent_base_volume"] = present(p.base_volume, unit="BASE_ASSET", frame="30m", at=p.close_at)
    f["parent_quote_volume"] = present(p.quote_volume, unit="QUOTE_ASSET", frame="30m", at=p.close_at)
    moves = []
    previous = p.open
    for child in children:
        moves.append(child.close - previous)
        previous = child.close
    net = p.close - p.open
    total_path = sum((abs(x) for x in moves), ZERO)
    favorable = max((c.high - p.open for c in children), default=ZERO)
    f["child_close_deltas"] = present(moves, unit="PRICE_DELTA", frame="6x5m", at=p.close_at)
    f["child_base_volumes"] = present([c.base_volume for c in children],
                                      unit="BASE_ASSET", frame="6x5m", at=p.close_at)
    f["child_quote_volumes"] = present([c.quote_volume for c in children],
                                       unit="QUOTE_ASSET", frame="6x5m", at=p.close_at)
    f["child_base_volume_changes"] = present(
        [children[i].base_volume-children[i-1].base_volume for i in range(1, 6)],
        unit="BASE_ASSET_CHANGE", frame="6x5m", at=p.close_at)
    f["child_quote_volume_changes"] = present(
        [children[i].quote_volume-children[i-1].quote_volume for i in range(1, 6)],
        unit="QUOTE_ASSET_CHANGE", frame="6x5m", at=p.close_at)
    f["net_price_move"] = present(net, unit="PRICE_DELTA", frame="30m", at=p.close_at)
    f["net_to_path_efficiency"] = (
        present(net / total_path, unit="SIGNED_RATIO", frame="6x5m", at=p.close_at)
        if total_path > ZERO else absent("NO_CHILD_CLOSE_PATH"))
    f["gain_retention"] = (
        present(net / favorable, unit="SIGNED_FRACTION_OF_FAVORABLE_HIGH",
                frame="6x5m", at=p.close_at)
        if favorable > ZERO else absent("NO_POSITIVE_UP_EXCURSION"))
    f.update(_rvol(item, decision))

    # R1 has selected latest *available* closed frames at or before event close.
    for frame in ("1h", "4h"):
        available = [x for x in item.context if x.close_at <= p.close_at]
        selected = available_closed_context(available, timeframe=frame, decision_at=decision)
        if selected is None:
            raise ContractError("R2_CONTEXT_CHANGED_AFTER_R1_ADMISSION")
        f[frame + "_directional_change_pct"] = present(
            (selected.close - selected.open) * Decimal("100") / selected.open,
            unit="SIGNED_PERCENT_OPEN_TO_CLOSE", frame=frame, at=selected.close_at)
        f[frame + "_closed_age_seconds"] = present(
            Decimal(str((decision - selected.close_at).total_seconds())),
            unit="SECONDS_NO_APPROVED_MAX_AGE", frame=frame, at=selected.close_at)
        f[frame + "_source_available_at"] = present(
            stamp(selected.available_at), unit="UTC_TIMESTAMP", frame=frame,
            at=selected.close_at)
    f["research_market_spread_bps"] = present(
        spread_bps(item.market.bid, item.market.ask), unit="BASIS_POINTS_RESEARCH_SCREEN",
        frame="MARKET", at=item.market.observed_at)
    f["research_quote_volume_24h"] = present(
        item.market.quote_volume_24h, unit="QUOTE_ASSET_ROLLING_24H_RESEARCH_SCREEN",
        frame="MARKET", at=item.market.observed_at)
    f["market_received_at"] = present(
        stamp(item.market_receipt.received_at), unit="UTC_TIMESTAMP",
        frame="MARKET", at=item.market.observed_at)
    f["market_available_at"] = present(
        stamp(item.market_receipt.available_at), unit="UTC_TIMESTAMP",
        frame="MARKET", at=item.market.observed_at)

    f["volatility_normalized_move"] = absent(
        "VOLATILITY_NORMALIZER_NOT_APPROVED", availability="NOT_IMPLEMENTED")
    f["n03_r2_numeric_normalizer"] = absent(
        "N03_V0_2_DIAGNOSTIC_ONLY_NO_NUMERIC_R2", availability="NOT_IMPLEMENTED")
    for name in ("SEM_I_01", "SEM_I_02", "SEM_S_01", "SEM_S_02"):
        f[name] = absent("SEM_LINK_UNMAPPED", availability="NOT_IMPLEMENTED")
    return f


def evaluate_raw_research_batch(items: tuple[Closed30mItem, ...], *, closed_at: datetime,
                                decision_at: datetime) -> list[dict]:
    """Full OFFLINE R0→R1→R2 entrypoint, independently triggered on closed 30m."""
    rows = evaluate_local_universe(items, closed_at=closed_at, decision_at=decision_at)
    ordered = sorted(items, key=lambda item: (item.market.symbol, item.discriminator))
    for item, row in zip(ordered, rows):
        row["raw_feature_schema"] = VERSION
        row["raw_features"] = (raw_features(item, decision_at=decision_at)
                               if row["raw_30m_evaluation_eligible"] else {})
        row["raw_features_status"] = ("RESEARCH_MEASURED" if row["raw_features"]
                                      else "NOT_ADMISSIBLE")
        row["raw_features_sha256"] = digest(canonical({
            "feature_version": VERSION, "evaluation_version": EVALUATION_VERSION,
            "event_id": row["event_id"], "input_sha256": row["input_sha256"],
            "features": row["raw_features"],
        }))
        # Never convert the R1 research output to a Stage05 v1 event.
        row["qualification_state"] = "UNKNOWN"
        row["signal_id"] = None
        row["score"] = None
        row["publishable"] = False
        row["stage05_event_v1_compatible"] = False
    return rows


def persist_raw_feature_snapshot(store: LocalOutbox, row: dict) -> dict:
    """Separate versioned append-only receipt; do not overwrite the R1 evidence."""
    if (type(store) is not LocalOutbox
            or row.get("schema") != EVALUATION_VERSION
            or row.get("raw_feature_schema") != VERSION
            or row.get("source_scope") != "SYNTHETIC_TEST_ONLY"
            or row.get("signal_id") is not None or row.get("qualification_state") != "UNKNOWN"
            or row.get("publishable") is not False):
        raise ContractError("R2_RESEARCH_ONLY_CUSTODY_REQUIRED")
    expected = digest(canonical({
        "feature_version": VERSION, "evaluation_version": EVALUATION_VERSION,
        "event_id": row["event_id"], "input_sha256": row["input_sha256"],
        "features": row["raw_features"],
    }))
    if row.get("raw_features_sha256") != expected:
        raise ContractError("R2_FEATURE_DIGEST_MISMATCH")
    payload = canonical(row)
    key = "research-features/" + digest(canonical([
        VERSION, row["event_id"], row["input_sha256"],
    ]))
    store.create_if_absent(key, payload)
    if store.read(key) != payload:
        raise ContractError("R2_FEATURE_CUSTODY_CONFLICT")
    return {"research_event_id": row["event_id"], "record_key": key,
            "record_sha256": digest(payload), "readback": "PASS",
            "signal_id": None, "dispatch_allowed": False}
