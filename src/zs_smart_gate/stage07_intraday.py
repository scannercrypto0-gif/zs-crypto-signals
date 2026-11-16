"""Stage07 deterministic intraday research, no market IO or publication authority.

Uses source-labelled immutable CandleWindow records and actual availability timestamps.
Outcome labels are deliberately computed in a separate retrospective function.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

from .core import utc
from .mtf_contracts import CandleWindow, ReconciliationTolerance, reconcile
from .stage03_r0_identity import SYMBOL, stamp
from .stage05_contracts import ContractError, canonical, digest

VERSION = "zs.stage07.intraday-premovement.v1"
LABEL_VERSION = "zs.stage07.retrospective-label.v1"
ZERO = Decimal("0")
ONE = Decimal("1")
HORIZONS_H = (1, 2, 4, 8, 12, 24)


@dataclass(frozen=True)
class ResearchWindow:
    symbol: str
    direction: str
    parent: CandleWindow
    children: tuple[CandleWindow, ...]
    history_5m: tuple[CandleWindow, ...]
    comparison_15m: tuple[CandleWindow, ...] = ()
    source_manifest_sha256: str = ""
    source_scope: str = "SYNTHETIC_TEST_ONLY"


def _failed(reason: str, *, event_id: str | None = None) -> dict:
    return dict(schema=VERSION, status="UNAVAILABLE", reasons=[reason],
                event_id=event_id, signal_id=None, score=None,
                qualification_state="RESEARCH_ONLY", publishable=False,
                features={}, input_sha256=None)


def _finite_bar(bar: CandleWindow) -> bool:
    """Reject NaN/infinity before Decimal comparisons or source reconciliation."""
    return all(isinstance(getattr(bar, key), Decimal) and getattr(bar, key).is_finite()
               for key in ("open", "high", "low", "close", "base_volume", "quote_volume"))


def _aligned(bars: Sequence[CandleWindow], frame: str, source: str,
             decision: datetime, *, until: datetime | None = None) -> str | None:
    previous = None
    for bar in bars:
        if not isinstance(bar, CandleWindow) or bar.timeframe != frame:
            return "FRAME_MISMATCH"
        if bar.source_id != source:
            return "SOURCE_MISMATCH"
        if previous is not None and bar.open_at != previous:
            return "GAP_OVERLAP_OR_OUT_OF_ORDER"
        if until is not None and bar.close_at > until:
            return "POST_EVENT_FEATURE_FORBIDDEN"
        if not _finite_bar(bar):
            return "NONFINITE_BAR_VALUE"
        if bar.errors_at(decision):
            return "BAR_INVALID_OR_UNAVAILABLE:" + ",".join(bar.errors_at(decision))
        previous = bar.close_at
    return None


def _feature(value: Decimal | None, unit: str, source: CandleWindow,
             reason: str = "") -> dict:
    return {"value": str(value) if value is not None else None,
            "unit": unit, "timeframe": source.timeframe,
            "event_close_at": stamp(source.close_at),
            "available_at": stamp(source.available_at),
            "source_id": source.source_id,
            "status": "PRESENT" if value is not None else "UNAVAILABLE",
            "reason": "" if value is not None else reason}


def _div(n: Decimal, d: Decimal) -> Decimal | None:
    return n / d if d != ZERO else None


def evaluate_window(window: ResearchWindow, *, decision_at: datetime) -> dict:
    """No future bars in inputs; conservative fail-closed source/clock validation."""
    decision = utc(decision_at)
    if not isinstance(window, ResearchWindow):
        return _failed("RESEARCH_WINDOW_TYPE_REQUIRED")
    if (not isinstance(window.symbol, str) or not SYMBOL.fullmatch(window.symbol) or window.direction not in ("UP", "DOWN")
            or window.source_scope != "SYNTHETIC_TEST_ONLY"
            or not isinstance(window.source_manifest_sha256, str)
            or len(window.source_manifest_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in window.source_manifest_sha256)):
        return _failed("RESEARCH_IDENTITY_OR_SCOPE_INVALID")
    parent = window.parent
    if not isinstance(parent, CandleWindow) or parent.timeframe != "30m":
        return _failed("PARENT_30M_REQUIRED")
    key = "s07-" + digest(canonical([VERSION, window.symbol, window.direction,
                                     stamp(parent.close_at), parent.source_id]))
    if decision < parent.close_at:
        return _failed("DECISION_BEFORE_EVENT_CLOSE", event_id=key)
    if (not isinstance(window.children, tuple) or len(window.children) != 6
            or not isinstance(window.history_5m, tuple)
            or len(window.history_5m) < 6):
        return _failed("SIX_CHILDREN_AND_PRIOR_5M_REQUIRED", event_id=key)
    source = parent.source_id
    if not source.startswith("SYNTHETIC:"):
        return _failed("UNVERIFIED_SOURCE", event_id=key)
    if not _finite_bar(parent):
        return _failed("NONFINITE_PARENT_VALUE", event_id=key)
    if parent.errors_at(decision):
        return _failed("PARENT_INVALID_OR_UNAVAILABLE", event_id=key)
    for bars, frame, until in ((window.children, "5m", parent.close_at),
                               (window.history_5m, "5m", parent.open_at),
                               (window.comparison_15m, "15m", parent.close_at)):
        invalid = _aligned(bars, frame, source, decision, until=until)
        if invalid:
            return _failed(invalid, event_id=key)
    if window.history_5m[-1].close_at != parent.open_at:
        return _failed("HISTORY_NOT_ADJACENT", event_id=key)
    if window.comparison_15m and (len(window.comparison_15m) != 2
                                  or window.comparison_15m[0].open_at != parent.open_at
                                  or window.comparison_15m[-1].close_at != parent.close_at):
        return _failed("COMPARISON_15M_NOT_FULL_PARENT", event_id=key)
    exact = ReconciliationTolerance(ZERO, ZERO, ZERO, "S07_EXACT_SYNTHETIC_ONLY")
    if reconcile(parent, window.children, decision, tolerance=exact).status != "PASS":
        return _failed("PARENT_CHILD_RECONCILIATION_FAILED", event_id=key)

    children = window.children
    history = window.history_5m
    sign = ONE if window.direction == "UP" else -ONE
    old = history[-6:]
    first, last = children[0], children[-1]
    net = sign * (parent.close - parent.open)
    path = sum((abs(b.close - b.open) for b in children), ZERO)
    r = parent.high - parent.low
    body = abs(parent.close - parent.open)
    favorable = (max(b.high for b in children) - parent.open if sign == ONE
                 else parent.open - min(b.low for b in children))
    peak = max(favorable, ZERO)
    base_now = sum((b.base_volume for b in children), ZERO)
    base_prior = sum((b.base_volume for b in old), ZERO)
    quote_now = sum((b.quote_volume for b in children), ZERO)
    quote_prior = sum((b.quote_volume for b in old), ZERO)
    p1 = sign * (children[-1].close - children[-2].close)
    p0 = sign * (children[-2].close - children[-3].close)
    volume_change = _div(base_now - base_prior, base_prior)
    features = {}
    def put(name: str, value: Decimal | None, unit: str, reason: str = ""):
        features[name] = _feature(value, unit, parent, reason or "ZERO_DENOMINATOR")

    put("directional_return", _div(net, parent.open), "RATIO")
    put("price_acceleration", p1 - p0, "QUOTE_PRICE_PER_5M_DELTA")
    put("base_volume_acceleration", children[-1].base_volume - 2 * children[-2].base_volume
        + children[-3].base_volume, "BASE_ASSET_SECOND_DIFFERENCE")
    put("base_volume_change_prior_30m", volume_change, "RATIO")
    put("quote_volume_change_prior_30m", _div(quote_now - quote_prior, quote_prior), "RATIO")
    put("wick_favorable_to_range",
        _div((parent.high - max(parent.open, parent.close)) if sign == ONE
             else (min(parent.open, parent.close) - parent.low), r), "RATIO")
    put("wick_adverse_to_range",
        _div((min(parent.open, parent.close) - parent.low) if sign == ONE
             else (parent.high - max(parent.open, parent.close)), r), "RATIO")
    put("body_to_range", _div(body, r), "RATIO")
    put("directional_efficiency", _div(net, path), "SIGNED_RATIO")
    put("gain_retention", _div(net, peak), "SIGNED_RATIO", "NO_FAVORABLE_EXCURSION")
    put("pullback_depth", _div(peak - net, peak), "RATIO", "NO_FAVORABLE_EXCURSION")
    old_ranges = [b.high - b.low for b in old]
    new_ranges = [b.high - b.low for b in children]
    put("range_expansion_prior_30m",
        _div(sum(new_ranges, ZERO), sum(old_ranges, ZERO)), "RATIO")
    put("range_transition_second_half",
        _div(sum(new_ranges[3:], ZERO), sum(new_ranges[:3], ZERO)), "RATIO")
    put("directional_higher_highs_or_lower_lows",
        Decimal(sum(1 for a, b in zip(children, children[1:]) if
                    (b.high > a.high if sign == ONE else b.low < a.low))),
        "COUNT_0_TO_5")
    put("directional_higher_lows_or_lower_highs",
        Decimal(sum(1 for a, b in zip(children, children[1:]) if
                    (b.low > a.low if sign == ONE else b.high < a.high))),
        "COUNT_0_TO_5")
    positive = sum(1 for b in children if sign * (b.close - b.open) > ZERO)
    put("directional_body_count", Decimal(positive), "COUNT_0_TO_6")
    put("price_volume_agreement", Decimal(1 if net > ZERO and volume_change is not None
                                         and volume_change > ZERO else 0)
        if volume_change is not None else None, "BOOLEAN_0_1")
    early = sign * (children[2].close - parent.open)
    late = sign * (children[-1].close - children[2].close)
    put("momentum_transition", late - early, "QUOTE_PRICE_DELTA")
    put("continuation_vs_fade", sign * (last.close - first.close),
        "QUOTE_PRICE_DELTA")
    if window.comparison_15m:
        a, b = window.comparison_15m
        if (a.open != children[0].open or a.close != children[2].close
                or b.open != children[3].open or b.close != children[-1].close
                or a.high != max(x.high for x in children[:3])
                or a.low != min(x.low for x in children[:3])
                or b.high != max(x.high for x in children[3:])
                or b.low != min(x.low for x in children[3:])
                or a.base_volume != sum((x.base_volume for x in children[:3]), ZERO)
                or b.base_volume != sum((x.base_volume for x in children[3:]), ZERO)
                or a.quote_volume != sum((x.quote_volume for x in children[:3]), ZERO)
                or b.quote_volume != sum((x.quote_volume for x in children[3:]), ZERO)):
            return _failed("COMPARISON_15M_RECONCILIATION_FAILED", event_id=key)
        put("comparison_15m_directional_first",
            _div(sign * (a.close - a.open), a.open), "RATIO")
        put("comparison_15m_directional_second",
            _div(sign * (b.close - b.open), b.open), "RATIO")
    else:
        put("comparison_15m_directional_first", None, "RATIO", "OPTIONAL_15M_NOT_PROVIDED")
        put("comparison_15m_directional_second", None, "RATIO", "OPTIONAL_15M_NOT_PROVIDED")
    payload = dict(schema=VERSION, status="RESEARCH_MEASURED", reasons=[],
        event_id=key, candidate_id="s07cand-" + key[4:],
        source_scope=window.source_scope, symbol=window.symbol, direction=window.direction,
        source_manifest_sha256=window.source_manifest_sha256, source_id=source,
        event_close_at=stamp(parent.close_at), decision_reference_price=str(parent.close),
        reference_available_at=stamp(parent.available_at),
        observation_status="CLOSED_30M", last_observed_5m_close=stamp(children[-1].close_at), decision_at=stamp(decision),
        available_at=stamp(max([parent.available_at] +
                              [b.available_at for b in (*history, *children, *window.comparison_15m)])),
        input_sha256=digest(canonical([
            VERSION, window.symbol, window.direction, window.source_manifest_sha256,
            [(b.timeframe, stamp(b.open_at), stamp(b.close_at),
              stamp(b.received_at), stamp(b.available_at), str(b.open),
              str(b.high), str(b.low), str(b.close), str(b.base_volume),
              str(b.quote_volume), b.source_id) for b in
             (parent, *history, *children, *window.comparison_15m)]])),
        features=features, qualification_state="RESEARCH_ONLY",
        signal_id=None, score=None, publishable=False, dispatch_allowed=False)
    payload["result_sha256"] = digest(canonical(payload))
    return payload


def evaluate_partial_window(window: ResearchWindow, observed_5m: tuple[CandleWindow, ...],
                            *, decision_at: datetime) -> dict:
    """Explicit early research snapshot: only fully observed 5m prefix, never parent OHLC.

    A future 30m parent is used only as a schedule/source anchor. Its price,
    volumes and full-period high/low are intentionally inaccessible here.
    """
    decision = utc(decision_at)
    if not isinstance(window, ResearchWindow):
        return _failed("RESEARCH_WINDOW_TYPE_REQUIRED")
    p = window.parent
    if (not isinstance(p, CandleWindow) or p.timeframe != "30m"
            or not isinstance(window.symbol, str) or not SYMBOL.fullmatch(window.symbol)
            or window.direction not in ("UP", "DOWN")
            or window.source_scope != "SYNTHETIC_TEST_ONLY"
            or not isinstance(window.source_manifest_sha256, str)
            or len(window.source_manifest_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in window.source_manifest_sha256)
            or not p.source_id.startswith("SYNTHETIC:")):
        return _failed("PARTIAL_IDENTITY_SOURCE_INVALID")
    if (p.close_at - p.open_at != timedelta(minutes=30)
            or p.open_at.microsecond or int(p.open_at.timestamp()) % 1800):
        return _failed("PARTIAL_PARENT_DURATION_INVALID")
    if not p.open_at < decision < p.close_at:
        return _failed("PARTIAL_DECISION_MUST_PRECEDE_PARENT_CLOSE")
    if (not isinstance(observed_5m, tuple) or not 3 <= len(observed_5m) < 6
            or not isinstance(window.history_5m, tuple)
            or len(window.history_5m) < 6):
        return _failed("PARTIAL_3_TO_5_CLOSED_5M_REQUIRED")
    if observed_5m[0].open_at != p.open_at:
        return _failed("PARTIAL_CHILD_START_MISMATCH")
    for bars, end in ((window.history_5m, p.open_at), (observed_5m, p.close_at)):
        invalid = _aligned(bars, "5m", p.source_id, decision, until=end)
        if invalid:
            return _failed("PARTIAL_" + invalid)
    if window.history_5m[-1].close_at != p.open_at:
        return _failed("PARTIAL_HISTORY_GAP")
    if observed_5m[-1].close_at >= p.close_at:
        return _failed("PARTIAL_NOT_EARLY")
    sign = ONE if window.direction == "UP" else -ONE
    old = window.history_5m[-len(observed_5m):]
    net = sign * (observed_5m[-1].close - observed_5m[0].open)
    base_now = sum((x.base_volume for x in observed_5m), ZERO)
    base_old = sum((x.base_volume for x in old), ZERO)
    q_now = sum((x.quote_volume for x in observed_5m), ZERO)
    q_old = sum((x.quote_volume for x in old), ZERO)
    anchor = observed_5m[-1]
    def feat(value, unit, reason="ZERO_DENOMINATOR"):
        return _feature(value, unit, anchor, reason)
    f = {
        "directional_return": feat(_div(net, observed_5m[0].open), "RATIO"),
        "base_volume_change_prior_equal_count": feat(_div(base_now-base_old, base_old), "RATIO"),
        "quote_volume_change_prior_equal_count": feat(_div(q_now-q_old, q_old), "RATIO"),
        "price_acceleration": feat(
            sign*(observed_5m[-1].close-observed_5m[-2].close)
            - sign*(observed_5m[-2].close-observed_5m[-3].close),
            "QUOTE_PRICE_PER_5M_DELTA"),
    }
    delta = f["base_volume_change_prior_equal_count"]["value"]
    f["price_volume_agreement"] = feat(
        Decimal(int(net > ZERO and Decimal(delta) > ZERO)) if delta is not None else None,
        "BOOLEAN_0_1")
    key = "s07p-" + digest(canonical([VERSION, window.symbol, window.direction,
        stamp(p.open_at), stamp(anchor.close_at), p.source_id]))
    payload = {
        "schema": VERSION, "event_id": key, "candidate_id": "s07cand-" + key[5:],
        "status": "RESEARCH_MEASURED", "reasons": [], "observation_status": "PARTIAL_PARENT_30M",
        "source_scope": window.source_scope, "source_id": p.source_id,
        "source_manifest_sha256": window.source_manifest_sha256,
        "symbol": window.symbol, "direction": window.direction,
        "event_close_at": stamp(p.close_at), "decision_at": stamp(decision),
        "available_at": stamp(max(x.available_at for x in observed_5m)),
        "reference_available_at": stamp(anchor.available_at),
        "decision_reference_price": str(anchor.close),
        "last_observed_5m_close": stamp(anchor.close_at),
        "observed_closed_5m_count": len(observed_5m),
        "input_sha256": digest(canonical([
            VERSION, key, window.source_manifest_sha256,
            [(stamp(x.open_at), stamp(x.close_at), stamp(x.available_at),
              str(x.open), str(x.high), str(x.low), str(x.close),
              str(x.base_volume), str(x.quote_volume), x.source_id)
             for x in (*old, *observed_5m)]])),
        "features": f, "qualification_state": "RESEARCH_ONLY",
        "signal_id": None, "score": None,
        "publishable": False, "dispatch_allowed": False}
    payload["result_sha256"] = digest(canonical(payload))
    return payload


def _verify_research(research: dict) -> datetime:
    if (not isinstance(research, dict) or research.get("schema") != VERSION
            or research.get("status") != "RESEARCH_MEASURED"
            or research.get("signal_id") is not None
            or research.get("score") is not None
            or research.get("publishable") is not False
            or research.get("dispatch_allowed") is not False
            or research.get("source_scope") != "SYNTHETIC_TEST_ONLY"
            or research.get("direction") not in ("UP", "DOWN")
            or not isinstance(research.get("source_id"), str)
            or not research["source_id"].startswith("SYNTHETIC:")
            or research.get("observation_status") not in ("CLOSED_30M", "PARTIAL_PARENT_30M")
            or research.get("result_sha256") != digest(canonical({
                k: v for k, v in research.items() if k != "result_sha256"}))):
        raise ContractError("S07_RESEARCH_RECORD_REQUIRED")
    from .stage05_contracts import parse_utc
    decision = parse_utc(research.get("decision_at"))
    availability = parse_utc(research.get("reference_available_at"))
    if availability > decision:
        raise ContractError("S07_REFERENCE_NOT_AVAILABLE_AT_DECISION")
    try:
        price = Decimal(research["decision_reference_price"])
    except (TypeError, ValueError, ArithmeticError):
        raise ContractError("S07_DECISION_REFERENCE_INVALID") from None
    if not price.is_finite() or price <= ZERO:
        raise ContractError("S07_DECISION_REFERENCE_INVALID")
    return decision


def _first_full_start(decision: datetime) -> datetime:
    """Earliest UTC-aligned five-minute open at or after the decision."""
    seconds = int(decision.timestamp())
    aligned = ((seconds + 299) // 300) * 300
    result = datetime.fromtimestamp(aligned, timezone.utc)
    return result if result >= decision else result + timedelta(minutes=5)


def retrospective_labels(research: dict, future: Sequence[CandleWindow], *,
                         as_of: datetime, move_fraction: Decimal) -> dict:
    """Independent 1/2/4/8/12/24h prospective-clock labels, with censoring.

    Decision reference is frozen in a hash-bound feature record. A future
    candle is never part of feature computation or the reference price.
    """
    decision = _verify_research(research)
    if (not isinstance(move_fraction, Decimal) or not move_fraction.is_finite()
            or not ZERO < move_fraction < ONE):
        raise ContractError("S07_RESEARCH_THRESHOLD_REQUIRED")
    now = utc(as_of)
    if now < decision:
        raise ContractError("S07_RETROSPECTIVE_BEFORE_DECISION")
    if not isinstance(future, (list, tuple)):
        raise ContractError("S07_FUTURE_SEQUENCE_REQUIRED")
    first_expected = _first_full_start(decision)
    source = research["source_id"]
    if future:
        if not isinstance(future[0], CandleWindow):
            raise ContractError("S07_FUTURE_BAR_TYPE_REQUIRED")
        if future[0].open_at < decision:
            raise ContractError("S07_LABEL_STRADDLES_DECISION")
        invalid = _aligned(future, "5m", source, now)
        if invalid:
            raise ContractError("S07_LABEL_BAR_INVALID:" + invalid)
        if future[-1].close_at > decision + timedelta(hours=24, minutes=5):
            raise ContractError("S07_LABEL_OVER_24H_INPUT")
    gap_at_start = bool(future and future[0].open_at != first_expected)
    ref = Decimal(research["decision_reference_price"])
    sign = ONE if research["direction"] == "UP" else -ONE
    target = ref * (ONE + sign * move_fraction)
    opposite = ref * (ONE - sign * move_fraction)
    result = {}
    for hours in HORIZONS_H:
        end = decision + timedelta(hours=hours)
        eligible = [b for b in future if b.close_at <= end]
        covered_end = eligible[-1].close_at if eligible else first_expected
        first_touch = None
        touch_close = None
        last_end = first_expected
        gap = gap_at_start
        for b in eligible:
            if b.open_at != last_end:
                gap = True
                break
            last_end = b.close_at
            favorable = b.high >= target if sign == ONE else b.low <= target
            adverse = b.low <= opposite if sign == ONE else b.high >= opposite
            if favorable or adverse:
                first_touch = ("AMBIGUOUS_OHLC_ORDER" if favorable and adverse
                               else "DIRECTIONAL_MOVE_TOUCHED" if favorable
                               else "OPPOSITE_MOVE_TOUCHED")
                touch_close = b.close_at
                break
        if gap:
            state, reason = "CENSORED_GAP", "UNOBSERVED_INTERVAL"
            touch_close = None
        elif first_touch:
            state, reason = first_touch, ""
        elif covered_end < end or now < end:
            state, reason = "CENSORED_HORIZON", "INCOMPLETE_OR_ASOF_WINDOW"
        else:
            state, reason = "NO_DIRECTIONAL_MOVE", ""
        result[str(hours)] = {
            "status": state, "censor_reason": reason,
            "horizon_end_at": stamp(end),
            "observed_until": stamp(min(covered_end, end)),
            "lead_hours": (str(Decimal(str((touch_close - decision).total_seconds()))
                               / Decimal("3600")) if touch_close is not None
                               and state in ("DIRECTIONAL_MOVE_TOUCHED", "OPPOSITE_MOVE_TOUCHED")
                               else None),
            "event_available_at": (stamp(next(b.available_at for b in eligible
                if b.close_at == touch_close)) if touch_close is not None else None),
            "bars_examined": len(eligible),
        }
    row = {"schema": LABEL_VERSION, "record_sha256": research["result_sha256"],
           "decision_at": stamp(decision), "reference_price": str(ref),
           "reference_policy": "FROZEN_LAST_AVAILABLE_CLOSE_AT_DECISION",
           "expected_first_full_bar_at": stamp(first_expected),
           "as_of": stamp(now), "source_id": source,
           "threshold_fraction": str(move_fraction), "horizons": result,
           "overlap_policy": "REQUIRES_DEDUP_OR_BLOCKED_EVALUATION",
           "is_trade": False, "is_signal": False}
    row["result_sha256"] = digest(canonical(row))
    return row


def compare_research_candidates(rows: Sequence[tuple[dict, dict]], *,
                                horizon_hours: int = 4) -> dict:
    """Synthetic-only false-positive/ablation demonstration, not calibrated policy.

    Baseline: directional return > 0. Illustrative 'full' research rule adds
    positive base volume; removing that condition is the explicit ablation.
    Overlapping 24h opportunities for the same symbol are discarded.
    """
    if horizon_hours not in HORIZONS_H:
        raise ContractError("S07_COMPARISON_HORIZON_INVALID")
    ordered = []
    for research, labels in rows:
        decision = _verify_research(research)
        if not isinstance(labels, dict):
            raise ContractError("S07_COMPARISON_LABEL_MISMATCH")
        if (labels.get("schema") != LABEL_VERSION
                or labels.get("record_sha256") != research["result_sha256"]
                or labels.get("result_sha256") != digest(canonical({
                    k: v for k, v in labels.items() if k != "result_sha256"}))
                or str(horizon_hours) not in labels.get("horizons", {})):
            raise ContractError("S07_COMPARISON_LABEL_MISMATCH")
        ordered.append((decision, research, labels))
    ordered.sort(key=lambda t: (t[0], t[1]["event_id"]))
    kept = []
    most_recent: dict[str, datetime] = {}
    skipped_overlap = 0
    for decision, research, labels in ordered:
        symbol = research["symbol"]
        if symbol in most_recent and decision < most_recent[symbol] + timedelta(hours=24):
            skipped_overlap += 1
            continue
        most_recent[symbol] = decision
        kept.append((research, labels))
    variants = {"baseline_directional_sign": {"selected": 0, "false_positive": 0,
        "true_positive": 0, "excluded_censored": 0},
        "research_price_plus_volume": {"selected": 0, "false_positive": 0,
        "true_positive": 0, "excluded_censored": 0}}
    for research, labels in kept:
        feat = research["features"]
        move = feat.get("directional_return", {}).get("value")
        volume = feat.get("base_volume_change_prior_30m",
                          feat.get("base_volume_change_prior_equal_count", {})).get("value")
        up = move is not None and Decimal(move) > ZERO
        vup = volume is not None and Decimal(volume) > ZERO
        state = labels["horizons"][str(horizon_hours)]["status"]
        for key, selected in (("baseline_directional_sign", up),
                              ("research_price_plus_volume", up and vup)):
            if not selected:
                continue
            stat = variants[key]
            stat["selected"] += 1
            if state == "DIRECTIONAL_MOVE_TOUCHED":
                stat["true_positive"] += 1
            elif state in ("OPPOSITE_MOVE_TOUCHED", "NO_DIRECTIONAL_MOVE"):
                stat["false_positive"] += 1
            else:
                stat["excluded_censored"] += 1
    for stat in variants.values():
        assessed = stat["true_positive"] + stat["false_positive"]
        stat["false_positive_rate"] = (
            str(Decimal(stat["false_positive"]) / assessed) if assessed else None)
    return {"schema": "zs.stage07.synthetic-comparison.v1",
            "horizon_hours": horizon_hours, "input_count": len(rows),
            "nonoverlapping_count": len(kept), "excluded_overlap": skipped_overlap,
            "baseline_and_ablation": variants,
            "source_scope": "SYNTHETIC_TEST_ONLY",
            "scientific_validity": "DEMONSTRATION_ONLY_NOT_OOS",
            "qualification_authority": None}
