"""Stage07 deterministic intraday research, no market IO or publication authority.

Uses source-labelled immutable CandleWindow records and actual availability timestamps.
Outcome labels are deliberately computed in a separate retrospective function.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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
    if (not SYMBOL.fullmatch(window.symbol) or window.direction not in ("UP", "DOWN")
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
        source_manifest_sha256=window.source_manifest_sha256,
        event_close_at=stamp(parent.close_at), decision_at=stamp(decision),
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


def retrospective_labels(research: dict, future: Sequence[CandleWindow], *,
                         as_of: datetime, move_fraction: Decimal) -> dict:
    """Post-decision ONLY; earliest complete-bar threshold touch, not an executed fill.

    The positive move_fraction is a caller-selected RESEARCH scenario, not policy.
    OHLC may cross both opposing boundaries in one bar: report ambiguity.
    """
    if (research.get("schema") != VERSION or research.get("status") != "RESEARCH_MEASURED"
            or research.get("signal_id") is not None or research.get("publishable") is not False):
        raise ContractError("S07_RESEARCH_RECORD_REQUIRED")
    if not isinstance(move_fraction, Decimal) or not move_fraction.is_finite() or move_fraction <= 0:
        raise ContractError("S07_RESEARCH_THRESHOLD_REQUIRED")
    now = utc(as_of)
    decision = datetime.fromisoformat(research["decision_at"].replace("Z", "+00:00"))
    direction = research["direction"]
    sign = ONE if direction == "UP" else -ONE
    if not future:
        return {"schema": LABEL_VERSION, "status": "CENSORED_NO_BARS", "lead_hours": None}
    source = future[0].source_id
    invalid = _aligned(future, "5m", source, now)
    if invalid or source not in research["event_id"] and not source.startswith("SYNTHETIC:"):
        raise ContractError("S07_LABEL_BAR_INVALID:" + str(invalid or "SOURCE"))
    if future[0].open_at < decision:
        raise ContractError("S07_LABEL_STRADDLES_DECISION")
    if future[-1].close_at > decision + timedelta(hours=24):
        raise ContractError("S07_LABEL_MAX_24H")
    # A price threshold must be supplied independently; the research row intentionally
    # contains no trade plan. Reference is a source-proven first post-decision open.
    reference = future[0].open
    target = reference * (ONE + sign * move_fraction)
    opposite = reference * (ONE - sign * move_fraction)
    result = "CENSORED"
    lead = None
    for b in future:
        up_hit = (b.high >= target if sign == ONE else b.low <= target)
        down_hit = (b.low <= opposite if sign == ONE else b.high >= opposite)
        if up_hit and down_hit:
            result = "AMBIGUOUS_OHLC_ORDER"
            break
        if up_hit:
            result = "DIRECTIONAL_MOVE_TOUCHED"
            lead = str(Decimal(str((b.close_at - decision).total_seconds())) / Decimal("3600"))
            break
        if down_hit:
            result = "OPPOSITE_MOVE_TOUCHED"
            lead = str(Decimal(str((b.close_at - decision).total_seconds())) / Decimal("3600"))
            break
    return {"schema": LABEL_VERSION, "status": result, "lead_hours": lead,
            "horizons_hours": list(HORIZONS_H),
            "decision_at": stamp(decision), "as_of": stamp(now),
            "source_id": source, "threshold_fraction": str(move_fraction),
            "reference_price": str(reference), "bars_examined": len(future),
            "is_trade": False, "is_signal": False}
