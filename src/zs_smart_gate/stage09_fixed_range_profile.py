"""Stage09 fixed-range volume levels: source/clock-bound offline research only.

EXACT_SYNTHETIC_TRADES describes exact arithmetic on a complete *synthetic*
trade fixture, NOT independent Spot Trades/AggTrades authentication. There is
no live-feed adapter, score, signal, order, policy gate, or network IO.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
from typing import Sequence

from .core import utc
from .mtf_contracts import CandleWindow, DURATIONS
from .stage03_r0_identity import SYMBOL, stamp
from .stage05_contracts import ContractError, SHA, canonical, digest, parse_utc

VERSION = "zs.stage09.fixed-range-levels.v1"
OUTCOME_VERSION = "zs.stage09.retrospective-observation.v1"
BASELINE_VERSION = "zs.stage09.synthetic-ablation.v1"
ZERO = Decimal("0")
ONE = Decimal("1")
MAX_BARS = 512
MAX_BINS = 2048
MAX_TRADES = 10000
KINDS = {"1h": "1h", "4h": "4h", "DAILY": "1d",
         "PREVIOUS_COMPLETED_WEEK": "1w"}
METHODS = {"APPROX_OHLCV", "EXACT_SYNTHETIC_TRADES"}


@dataclass(frozen=True)
class TradePrint:
    trade_id: int
    event_at: datetime
    received_at: datetime
    available_at: datetime
    source_id: str
    price: Decimal
    base_qty: Decimal


@dataclass(frozen=True)
class SyntheticTradeCoverage:
    source_id: str
    window_open_at: datetime
    window_close_at: datetime
    first_trade_id: int
    last_trade_id: int
    expected_count: int
    trade_digest_sha256: str
    complete_attested: bool
    attestation_scope: str = "SYNTHETIC_FIXTURE_ONLY"


@dataclass(frozen=True)
class ResearchHypothesis:
    direction: str
    entry: Decimal
    stop: Decimal
    target: Decimal
    fee_per_side_bps: Decimal
    slippage_per_side_bps: Decimal
    structure_level: Decimal | None = None
    structure_available_at: datetime | None = None
    structure_source_id: str | None = None


@dataclass(frozen=True)
class ProfileWindow:
    symbol: str
    direction: str
    kind: str
    anchor_at: datetime
    bars: tuple[CandleWindow, ...]
    bin_size: Decimal
    source_manifest_sha256: str
    method: str = "APPROX_OHLCV"
    trades: tuple[TradePrint, ...] = ()
    trade_coverage: SyntheticTradeCoverage | None = None
    reaction: tuple[CandleWindow, ...] = ()
    value_area_fraction: Decimal | None = None
    hypothesis: ResearchHypothesis | None = None
    price_origin: Decimal = ZERO
    source_scope: str = "SYNTHETIC_TEST_ONLY"


def _failure(reason: str) -> dict:
    return {"schema": VERSION, "status": "UNAVAILABLE", "reason_codes": [reason],
            "qualification_state": "RESEARCH_ONLY", "signal_id": None,
            "score": None, "trade_ready": False, "publishable": False,
            "dispatch_allowed": False, "features": {}}


def _decimal_ok(value, *, positive: bool = False) -> bool:
    return (isinstance(value, Decimal) and value.is_finite()
            and (value > ZERO if positive else value >= ZERO))


def _serialize_bar(bar: CandleWindow) -> list[str]:
    return [bar.timeframe, stamp(bar.open_at), stamp(bar.close_at),
            stamp(bar.received_at), stamp(bar.available_at), bar.source_id,
            *[str(getattr(bar, f)) for f in
              ("open", "high", "low", "close", "base_volume", "quote_volume")]]


def _serialize_trade(trade: TradePrint) -> list[str | int]:
    return [trade.trade_id, stamp(utc(trade.event_at)),
            stamp(utc(trade.received_at)), stamp(utc(trade.available_at)),
            trade.source_id, str(trade.price), str(trade.base_qty)]


def _validate_bars(bars: Sequence[CandleWindow], frame: str, source: str,
                   decision: datetime, *, first_open: datetime | None = None,
                   require_nonempty: bool = True) -> str | None:
    if (not isinstance(bars, (tuple, list)) or len(bars) > MAX_BARS
            or require_nonempty and not bars):
        return "BOUNDED_CLOSED_BARS_REQUIRED"
    previous = first_open
    for bar in bars:
        if not isinstance(bar, CandleWindow) or bar.timeframe != frame:
            return "BAR_FRAME_INVALID"
        if bar.source_id != source:
            return "BAR_SOURCE_MISMATCH"
        if previous is not None and bar.open_at != previous:
            return "BAR_GAP_DUPLICATE_OUT_OF_ORDER"
        errors = bar.errors_at(decision)
        if errors:
            return "BAR_TIME_OR_OHLCV_INVALID:" + ",".join(errors)
        previous = bar.close_at
    return None


def _completed_week(decision: datetime) -> tuple[datetime, datetime]:
    now = utc(decision)
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return monday - timedelta(weeks=1), monday


def _bin_index(price: Decimal, size: Decimal, origin: Decimal) -> int:
    return int(((price-origin)/size).to_integral_value(rounding=ROUND_FLOOR))


def _range_indices(lo: Decimal, hi: Decimal, size: Decimal,
                   origin: Decimal) -> tuple[int, int]:
    bottom = _bin_index(lo, size, origin)
    top = (_bin_index(hi, size, origin) if lo == hi
           else int(((hi-origin)/size).to_integral_value(rounding=ROUND_CEILING))-1)
    return bottom, max(bottom, top)


def _coverage_digest(trades: tuple[TradePrint, ...]) -> str:
    return digest(canonical([_serialize_trade(t) for t in trades]))


def _verified_trades(w: ProfileWindow, source: str, first: datetime,
                     end: datetime, decision: datetime) -> str | None:
    ts, cover = w.trades, w.trade_coverage
    if (not isinstance(ts, tuple) or not 1 <= len(ts) <= MAX_TRADES
            or not isinstance(cover, SyntheticTradeCoverage)
            or cover.attestation_scope != "SYNTHETIC_FIXTURE_ONLY"
            or cover.complete_attested is not True
            or cover.source_id != source
            or not isinstance(cover.expected_count, int) or
            isinstance(cover.expected_count, bool)
            or cover.expected_count != len(ts)
            or not isinstance(cover.first_trade_id, int)
            or not isinstance(cover.last_trade_id, int)
            or isinstance(cover.first_trade_id, bool)
            or isinstance(cover.last_trade_id, bool)
            or cover.first_trade_id < 0):
        return "SYNTHETIC_TRADE_COVERAGE_RECEIPT_REQUIRED"
    try:
        if (utc(cover.window_open_at) != first or
                utc(cover.window_close_at) != end):
            return "TRADE_COVERAGE_WINDOW_MISMATCH"
    except (ValueError, TypeError):
        return "TRADE_COVERAGE_UTC_INVALID"
    if not isinstance(cover.trade_digest_sha256, str) or not SHA.fullmatch(
            cover.trade_digest_sha256):
        return "TRADE_COVERAGE_SHA_INVALID"
    prior_time = None
    ids = []
    for t in ts:
        if not isinstance(t, TradePrint):
            return "TRADE_TYPED_RECEIPT_REQUIRED"
        if (not isinstance(t.trade_id, int) or isinstance(t.trade_id, bool)
                or not _decimal_ok(t.price, positive=True)
                or not _decimal_ok(t.base_qty, positive=True)
                or t.source_id != source):
            return "TRADE_ID_PRICE_VOLUME_SOURCE_INVALID"
        try:
            event, recv, avail = (utc(t.event_at), utc(t.received_at),
                                  utc(t.available_at))
        except (ValueError, TypeError):
            return "TRADE_UTC_INVALID"
        if not first <= event < end or not event <= recv <= avail <= decision:
            return "TRADE_EVENT_RECEIPT_UNAVAILABLE"
        if prior_time is not None and event < prior_time:
            return "TRADE_TIME_OUT_OF_ORDER"
        prior_time = event
        ids.append(t.trade_id)
    if (ids != list(range(cover.first_trade_id, cover.last_trade_id+1))
            or cover.trade_digest_sha256 != _coverage_digest(ts)):
        return "TRADE_SEQUENCE_OR_DIGEST_MISMATCH"
    # Reconcile complete synthetic prints to every OHLCV parent. A self-attested
    # ID interval alone is never evidence of completeness in a live feed.
    for bar in w.bars:
        inside = [t for t in ts if bar.open_at <= utc(t.event_at) < bar.close_at]
        if not inside:
            return "TRADE_BAR_MISSING_PRINTS"
        if (inside[0].price != bar.open or inside[-1].price != bar.close
                or max(t.price for t in inside) != bar.high
                or min(t.price for t in inside) != bar.low
                or sum((t.base_qty for t in inside), ZERO) != bar.base_volume
                or sum((t.price*t.base_qty for t in inside), ZERO) != bar.quote_volume):
            return "TRADE_OHLCV_RECONCILIATION_FAILED"
    # No authentic exchange signature or completeness witness is implied.
    return None


def _bin_profile(w: ProfileWindow, source: str, first: datetime,
                 end: datetime, decision: datetime) -> tuple[dict[int, Decimal], Decimal, Decimal]:
    allocations: dict[int, Decimal] = {}
    vwap_numerator = ZERO
    base_sum = ZERO
    if w.method == "EXACT_SYNTHETIC_TRADES":
        error = _verified_trades(w, source, first, end, decision)
        if error:
            raise ContractError(error)
        for t in w.trades:
            idx = _bin_index(t.price, w.bin_size, w.price_origin)
            allocations[idx] = allocations.get(idx, ZERO) + t.base_qty
            vwap_numerator += t.price * t.base_qty
            base_sum += t.base_qty
    else:
        for bar in w.bars:
            low, high = _range_indices(bar.low, bar.high, w.bin_size, w.price_origin)
            span = high-low+1
            if span > MAX_BINS:
                raise ContractError("OHLCV_BIN_RANGE_LIMIT")
            part = bar.base_volume/Decimal(span)
            for idx in range(low, high+1):
                allocations[idx] = allocations.get(idx, ZERO)+part
            # HLC3 * base_volume is explicitly an OHLCV approximation.
            typical = (bar.high+bar.low+bar.close)/Decimal(3)
            vwap_numerator += typical * bar.base_volume
            base_sum += bar.base_volume
    if (not allocations or len(allocations) > MAX_BINS or not base_sum
            or max(allocations)-min(allocations)+1 > MAX_BINS):
        # Prevent sparse exact-print bins from causing unbounded value-area scans.
        raise ContractError("PROFILE_EMPTY_VOLUME_OR_BIN_LIMIT")
    return allocations, vwap_numerator/base_sum, base_sum


def _value_area(volumes: dict[int, Decimal], poc: int, total: Decimal,
                fraction: Decimal | None, size: Decimal, origin: Decimal) -> dict:
    if fraction is None:
        return {"status": "NOT_REQUESTED", "vah": None, "val": None}
    if not _decimal_ok(fraction, positive=True) or fraction > ONE:
        raise ContractError("VALUE_AREA_FRACTION_INVALID")
    chosen = {poc}
    lo = hi = poc
    measured = volumes[poc]
    while measured < total*fraction:
        left, right = lo-1, hi+1
        lv, rv = volumes.get(left, ZERO), volumes.get(right, ZERO)
        if (left < min(volumes) and right > max(volumes)):
            break
        if left < min(volumes):
            take_left = False
        elif right > max(volumes):
            take_left = True
        else:
            take_left = lv >= rv  # equal-volume tie goes to lower bin
        idx = left if take_left else right
        chosen.add(idx)
        measured += volumes.get(idx, ZERO)
        lo = min(lo, idx)
        hi = max(hi, idx)
    return {"status": "PRESENT", "fraction_requested": str(fraction),
            "fraction_realized": str(measured/total),
            "val": str(origin+Decimal(lo)*size),
            "vah": str(origin+Decimal(hi+1)*size),
            "bin_count": len(chosen),
            "tie_policy": "EXPAND_HIGHER_NEIGHBOR_VOLUME_THEN_LOWER_BIN"}


def _distance(price: Decimal, level: Decimal) -> dict:
    signed = price-level
    return {"signed_price": str(signed), "absolute_price": str(abs(signed)),
            "signed_fraction": str(signed/level) if level > ZERO else None,
            "absolute_fraction": str(abs(signed)/level) if level > ZERO else None}


def _reactions(bars: tuple[CandleWindow, ...], *, ref_close: Decimal,
               level: Decimal, side: str, decision: datetime) -> dict:
    """Frozen-level reaction only AFTER the reference profile is available."""
    sign = ONE if side == "UP" else -ONE
    previous = ref_close
    crossings: list[dict] = []
    retests: list[dict] = []
    rejections: list[dict] = []
    holds = 0
    previous_favorable = sign*(previous-level) > ZERO
    for bar in bars:
        favorable = sign*(bar.close-level) > ZERO
        touched = bar.low <= level <= bar.high
        crossed = not previous_favorable and favorable
        if crossed:
            crossings.append({"event_close_at": stamp(bar.close_at),
                              "available_at": stamp(bar.available_at)})
        if crossings and not crossed and touched and favorable:
            retests.append({"event_close_at": stamp(bar.close_at),
                            "available_at": stamp(bar.available_at)})
        if previous_favorable and touched and not favorable:
            rejections.append({"event_close_at": stamp(bar.close_at),
                               "available_at": stamp(bar.available_at)})
        if previous_favorable and favorable and crossings:
            holds += 1
        previous, previous_favorable = bar.close, favorable
    crossing = crossings[-1] if crossings else None
    return {"status": "PRESENT" if bars else "UNAVAILABLE",
            "cross_count": len(crossings), "latest_cross": crossing,
            "retest_count": len(retests), "hold_consecutive_pairs": holds,
            "rejection_count": len(rejections),
            "seconds_since_last_cross_available": (
                str(Decimal(str((decision-parse_utc(crossing["available_at"])).total_seconds())))
                if crossing else None),
            "criterion": "CLOSE_SIDE_FLIP; RANGE_TOUCH; TWO_FAVORABLE_CLOSES",
            "reference_level": str(level)}


def _hypothesis(h: ResearchHypothesis | None, direction: str, source: str,
                decision: datetime) -> dict:
    if h is None:
        return {"status": "NOT_PROVIDED", "trade_ready": False}
    if not isinstance(h, ResearchHypothesis) or h.direction != direction:
        raise ContractError("RESEARCH_HYPOTHESIS_DIRECTION_INVALID")
    values = (h.entry, h.stop, h.target)
    costs = (h.fee_per_side_bps, h.slippage_per_side_bps)
    if not all(_decimal_ok(v, positive=True) for v in values):
        raise ContractError("HYPOTHESIS_LEVELS_INVALID")
    if not all(_decimal_ok(x) for x in costs):
        raise ContractError("HYPOTHESIS_COSTS_INVALID")
    if not (h.stop < h.entry < h.target if direction == "UP"
            else h.target < h.entry < h.stop):
        raise ContractError("HYPOTHESIS_PRICE_ORDER_INVALID")
    if h.structure_level is not None:
        if (not _decimal_ok(h.structure_level, positive=True)
                or h.structure_source_id != source
                or h.structure_available_at is None):
            raise ContractError("HYPOTHESIS_STRUCTURE_EVIDENCE_INVALID")
        try:
            if utc(h.structure_available_at) > decision:
                raise ContractError("HYPOTHESIS_STRUCTURE_FUTURE")
        except (TypeError, ValueError):
            raise ContractError("HYPOTHESIS_STRUCTURE_UTC_INVALID") from None
    elif h.structure_available_at is not None or h.structure_source_id is not None:
        raise ContractError("HYPOTHESIS_STRUCTURE_PAIR_REQUIRED")
    reward = abs(h.target-h.entry)
    risk = abs(h.entry-h.stop)
    roundtrip_bps = Decimal(2)*(h.fee_per_side_bps+h.slippage_per_side_bps)
    net_reward_fraction = reward/h.entry - roundtrip_bps/Decimal(10000)
    return {"status": "SCENARIO_ONLY_NOT_VALIDATED",
            "direction": direction, "entry": str(h.entry),
            "stop": str(h.stop), "target": str(h.target),
            "structure_level": str(h.structure_level) if h.structure_level is not None else None,
            "structure_evidence": ("CALLER_SUPPLIED_RESEARCH_LEVEL_NOT_AUTHENTICATED"
                                   if h.structure_level is not None else "NOT_PROVIDED"),
            "gross_reward_to_risk": str(reward/risk),
            "fee_per_side_bps": str(h.fee_per_side_bps),
            "slippage_per_side_bps": str(h.slippage_per_side_bps),
            "roundtrip_assumed_cost_bps": str(roundtrip_bps),
            "net_reward_fraction_after_assumed_costs": str(net_reward_fraction),
            "trade_ready": False, "is_order": False,
            "note": "NOT_ENTRY_RECOMMENDATION_NO_FILL_OR_EXECUTION_AUTHORITY"}


def evaluate_profile(w: ProfileWindow, *, decision_at: datetime) -> dict:
    """Freeze source-available profile and post-reference observations at decision."""
    if not isinstance(w, ProfileWindow):
        return _failure("PROFILE_WINDOW_TYPED_REQUIRED")
    try:
        decision = utc(decision_at)
        anchor = utc(w.anchor_at)
    except (TypeError, ValueError):
        return _failure("DECISION_ANCHOR_UTC_REQUIRED")
    if (not isinstance(w.symbol, str) or not SYMBOL.fullmatch(w.symbol)
            or w.direction not in ("UP", "DOWN")
            or w.kind not in KINDS or w.method not in METHODS
            or w.source_scope != "SYNTHETIC_TEST_ONLY"
            or not isinstance(w.source_manifest_sha256, str)
            or not SHA.fullmatch(w.source_manifest_sha256)
            or not _decimal_ok(w.bin_size, positive=True)
            or not _decimal_ok(w.price_origin)):
        return _failure("RESEARCH_IDENTITY_BIN_SCOPE_INVALID")
    if not isinstance(w.bars, tuple) or not w.bars:
        return _failure("PROFILE_BARS_REQUIRED")
    source = w.bars[0].source_id if isinstance(w.bars[0], CandleWindow) else None
    if not isinstance(source, str) or not source.startswith("SYNTHETIC:"):
        return _failure("UNVERIFIED_SOURCE")
    frame = KINDS[w.kind]
    invalid = _validate_bars(w.bars, frame, source, decision, first_open=anchor)
    if invalid:
        return _failure("PROFILE_" + invalid)
    if w.kind == "PREVIOUS_COMPLETED_WEEK":
        week_start, week_end = _completed_week(decision)
        if (len(w.bars) != 1 or anchor != week_start
                or w.bars[0].close_at != week_end):
            return _failure("PREVIOUS_COMPLETED_WEEK_REQUIRED_NOT_DEVELOPING")
    if w.method == "APPROX_OHLCV" and (w.trades or w.trade_coverage is not None):
        return _failure("APPROX_TRADES_MUST_BE_ABSENT")
    if w.value_area_fraction is not None and (
            not _decimal_ok(w.value_area_fraction, positive=True)
            or w.value_area_fraction > ONE):
        return _failure("VALUE_AREA_FRACTION_INVALID")
    reference_available = max(b.available_at for b in w.bars)
    if not isinstance(w.reaction, tuple):
        return _failure("REACTION_SEQUENCE_REQUIRED")
    if w.reaction:
        first = w.reaction[0]
        if not isinstance(first, CandleWindow) or first.open_at < reference_available:
            return _failure("REACTION_STRADDLES_REFERENCE_AVAILABILITY")
        reaction_frame = first.timeframe
        if reaction_frame not in ("5m", "30m", "1h", "4h", "1d"):
            return _failure("REACTION_FRAME_INVALID")
        invalid = _validate_bars(w.reaction, reaction_frame, source, decision)
        if invalid:
            return _failure("REACTION_" + invalid)
    try:
        allocations, vwap, total = _bin_profile(
            w, source, anchor, w.bars[-1].close_at, decision)
        poc_index = min(k for k, vol in allocations.items()
                        if vol == max(allocations.values()))
        poc = w.price_origin+(Decimal(poc_index)+Decimal("0.5"))*w.bin_size
        value_area = _value_area(allocations, poc_index, total,
                                 w.value_area_fraction, w.bin_size, w.price_origin)
        hypothesis = _hypothesis(w.hypothesis, w.direction, source, decision)
    except (ContractError, ValueError, OverflowError, ArithmeticError) as exc:
        return _failure(str(exc) if isinstance(exc, ContractError)
                        else "INVALID_NUMERIC_PROFILE")
    last_observed_bar = w.reaction[-1] if w.reaction else w.bars[-1]
    last_close = last_observed_bar.close
    baseline_delta = last_observed_bar.close-last_observed_bar.open
    baseline_sign = ("UP" if baseline_delta > ZERO else
                     "DOWN" if baseline_delta < ZERO else "NEUTRAL")
    profile_end = w.bars[-1].close_at
    key = digest(canonical([VERSION, w.symbol, w.direction, w.kind, stamp(anchor),
                             stamp(profile_end), source, w.source_manifest_sha256,
                             w.method, str(w.bin_size), str(w.price_origin)]))
    events = _reactions(w.reaction, ref_close=w.bars[-1].close, level=poc,
                         side=w.direction, decision=decision)
    bars_data = [_serialize_bar(b) for b in (*w.bars, *w.reaction)]
    trade_data = [_serialize_trade(t) for t in w.trades]
    coverage_data = (None if w.trade_coverage is None else [
        w.trade_coverage.source_id, stamp(utc(w.trade_coverage.window_open_at)),
        stamp(utc(w.trade_coverage.window_close_at)), w.trade_coverage.first_trade_id,
        w.trade_coverage.last_trade_id, w.trade_coverage.expected_count,
        w.trade_coverage.trade_digest_sha256, w.trade_coverage.complete_attested,
        w.trade_coverage.attestation_scope])
    hypothesis_data = (None if w.hypothesis is None else [
        str(x) for x in (w.hypothesis.entry, w.hypothesis.stop,
                        w.hypothesis.target, w.hypothesis.fee_per_side_bps,
                        w.hypothesis.slippage_per_side_bps, w.hypothesis.structure_level,
                        stamp(utc(w.hypothesis.structure_available_at))
                        if w.hypothesis.structure_available_at is not None else None,
                        w.hypothesis.structure_source_id)])
    row = {
        "schema": VERSION, "status": "RESEARCH_MEASURED", "reason_codes": [],
        "event_id": "s09-"+key, "candidate_id": "s09cand-"+key,
        "symbol": w.symbol, "direction": w.direction,
        "source_id": source, "source_manifest_sha256": w.source_manifest_sha256,
        "source_scope": w.source_scope,
        "input_sha256": digest(canonical([VERSION, key, bars_data, trade_data,
                                           coverage_data, hypothesis_data,
                                           str(w.value_area_fraction)])),
        "kind": w.kind, "anchor_at": stamp(anchor),
        "profile_close_at": stamp(profile_end),
        "reference_available_at": stamp(reference_available),
        "decision_at": stamp(decision),
        "method": w.method, "precision_label": (
            "EXACT_SYNTHETIC_FIXTURE_ARITHMETIC_NOT_VERIFIED_EXCHANGE"
            if w.method == "EXACT_SYNTHETIC_TRADES"
            else "APPROX_OHLCV_UNIFORM_HIGH_LOW_ALLOCATION"),
        "source_trust": "SYNTHETIC_SELF_ATTESTED_NOT_INDEPENDENT_AUTHENTICATION",
        "coverage": {"status": "SYNTHETIC_FIXTURE_ATTESTED"
                     if w.method == "EXACT_SYNTHETIC_TRADES"
                     else "CLOSED_OHLCV_BARS_ONLY",
                     "complete_bars": len(w.bars), "trades": len(w.trades),
                     "volume_unit": "BASE_ASSET"},
        "binning": {"origin": str(w.price_origin), "size": str(w.bin_size),
                    "poc_index": poc_index, "poc_tie": "LOWEST_BIN",
                    "high_exact_boundary": "PREVIOUS_BIN",
                    "allocation": ("TRADE_PRICE_EXACT_BIN"
                                   if w.method == "EXACT_SYNTHETIC_TRADES"
                                   else "EQUAL_BASE_VOLUME_ACROSS_TOUCHED_BINS")},
        "features": {"poc": str(poc), "poc_bin_low": str(
            w.price_origin+Decimal(poc_index)*w.bin_size),
            "poc_bin_high": str(w.price_origin+Decimal(poc_index+1)*w.bin_size),
            "vwap": str(vwap), "vwap_method": (
                "SUM_TRADE_PRICE_TIMES_BASE_QTY_OVER_BASE_QTY"
                if w.method == "EXACT_SYNTHETIC_TRADES"
                else "SUM_HLC3_TIMES_BASE_VOLUME_OVER_BASE_VOLUME"),
            "value_area": value_area,
            "total_base_volume": str(total),
            "bin_volumes": [[i, str(allocations[i])] for i in sorted(allocations)],
            "decision_price": str(last_close),
            "price_only_baseline": baseline_sign,
            "price_only_baseline_rule": "LAST_OBSERVED_BAR_CLOSE_MINUS_OPEN_SIGN",
            "decision_price_at": stamp(w.reaction[-1].close_at
                                       if w.reaction else w.bars[-1].close_at),
            "poc_distance": _distance(last_close, poc),
            "vwap_distance": _distance(last_close, vwap),
            "reaction_to_frozen_poc": events,
            "profile_source_id": source, "profile_available_at": stamp(reference_available)},
        "hypothesis": hypothesis, "no_lookahead": True,
        "signal_id": None, "score": None, "qualification_state": "RESEARCH_ONLY",
        "trade_ready": False, "publishable": False, "dispatch_allowed": False,
        "is_trade": False,
    }
    row["result_sha256"] = digest(canonical(row))
    return row


def retrospective_profile_observation(research: dict, future: Sequence[CandleWindow],
                                      *, as_of: datetime) -> dict:
    """Descriptive future closes, separate from immutable decision features."""
    if (not isinstance(research, dict) or research.get("schema") != VERSION
            or research.get("status") != "RESEARCH_MEASURED"
            or research.get("source_scope") != "SYNTHETIC_TEST_ONLY"
            or research.get("signal_id") is not None
            or research.get("score") is not None
            or research.get("trade_ready") is not False
            or research.get("publishable") is not False
            or research.get("result_sha256") != digest(canonical({
                k: v for k, v in research.items() if k != "result_sha256"}))):
        raise ContractError("STAGE09_RESEARCH_RECEIPT_REQUIRED")
    decision = parse_utc(research["decision_at"])
    now = utc(as_of)
    if now < decision or not isinstance(future, (tuple, list)):
        raise ContractError("STAGE09_RETROSPECTIVE_INPUT_INVALID")
    expected = None
    if future:
        if not isinstance(future[0], CandleWindow) or future[0].open_at < decision:
            raise ContractError("STAGE09_RETROSPECTIVE_STRADDLE")
        frame = future[0].timeframe
        if frame not in ("5m", "30m", "1h", "4h", "1d"):
            raise ContractError("STAGE09_RETROSPECTIVE_FRAME_INVALID")
        duration = int(DURATIONS[frame].total_seconds())
        expected = datetime.fromtimestamp(
            (int(decision.timestamp()) // duration + 1)*duration, timezone.utc)
        error = _validate_bars(future, frame, research["source_id"], now)
        if error:
            raise ContractError("STAGE09_RETROSPECTIVE_" + error)
    gap = bool(future and future[0].open_at != expected)
    poc = Decimal(research["features"]["poc"])
    last = future[-1].close if future and not gap else None
    row = {"schema": OUTCOME_VERSION, "research_sha256": research["result_sha256"],
           "as_of": stamp(now), "status": ("CENSORED_NO_BARS" if not future else
                                          "CENSORED_GAP" if gap else "OBSERVED"),
           "reference_poc": str(poc), "closed_bars": len(future),
           "first_expected_full_bar_at": stamp(expected) if expected else None,
           "last_available_at": stamp(future[-1].available_at) if future else None,
           "last_close_minus_frozen_poc": str(last-poc) if last is not None else None,
           "is_trade": False, "is_predictive_validation": False}
    row["result_sha256"] = digest(canonical(row))
    return row


def synthetic_ablation(records: Sequence[dict]) -> dict:
    """Descriptive same-snapshot ablations, never evidence of prediction."""
    if not isinstance(records, (tuple, list)) or len(records) > 128:
        raise ContractError("STAGE09_ABLATION_BOUNDED_RECORDS_REQUIRED")
    counts = {k: {"up": 0, "down": 0, "neutral": 0,
                  "agreement_with_baseline": 0, "conflict_with_baseline": 0}
              for k in ("price_only", "with_poc_without_vwap",
                        "with_vwap_without_poc")}
    for row in records:
        if (not isinstance(row, dict) or row.get("schema") != VERSION
                or row.get("status") != "RESEARCH_MEASURED"
                or row.get("signal_id") is not None
                or row.get("source_scope") != "SYNTHETIC_TEST_ONLY"
                or row.get("result_sha256") != digest(canonical({
                    k: v for k, v in row.items() if k != "result_sha256"}))):
            raise ContractError("STAGE09_ABLATION_RESEARCH_RECEIPT_REQUIRED")
        f = row["features"]
        baseline = f["price_only_baseline"]
        if baseline not in ("UP", "DOWN", "NEUTRAL"):
            raise ContractError("STAGE09_ABLATION_BASELINE_INVALID")
        price = Decimal(f["decision_price"])
        comparisons = {
            "price_only": baseline,
            "with_poc_without_vwap": ("UP" if price > Decimal(f["poc"])
                                       else "DOWN" if price < Decimal(f["poc"])
                                       else "NEUTRAL"),
            "with_vwap_without_poc": ("UP" if price > Decimal(f["vwap"])
                                        else "DOWN" if price < Decimal(f["vwap"])
                                        else "NEUTRAL")}
        for key, result in comparisons.items():
            stat = counts[key]
            stat[result.lower()] += 1
            if key != "price_only" and baseline != "NEUTRAL" and result != "NEUTRAL":
                stat["agreement_with_baseline" if result == baseline
                     else "conflict_with_baseline"] += 1
    return {"schema": BASELINE_VERSION, "sample_count": len(records),
            "baseline": "LAST_OBSERVED_CLOSED_BAR_CLOSE_MINUS_OPEN",
            "ablation": "REMOVE_POC_OR_VWAP_AS_DESCRIPTIVE_LEVEL_ONLY",
            "variants": counts, "prediction_accuracy": None,
            "false_positive_rate": None,
            "source_scope": "SYNTHETIC_TEST_ONLY",
            "scientific_validity": "DESCRIPTIVE_ONLY_NOT_OOS",
            "qualification_authority": None}
