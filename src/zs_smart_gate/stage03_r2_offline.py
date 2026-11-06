"""R2 offline-only *unfrozen* normalizer candidates.

Synthetic sources only. This module deliberately does not call score_v2,
qualify events, emit signal IDs, access a network, or alter frozen contracts.
Numbers below are DEV research candidates, not probabilities or PIT proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence

from .stage03a_contracts import Direction, Horizon, V2_GROUPS

VERSION = "STAGE03_R2_DEV_CANDIDATE_UNFROZEN"
ONSET_ATR_THRESHOLD_CANDIDATE = Decimal("0.5")
PIVOT_LEFT_CANDIDATE = 2
PIVOT_RIGHT_CANDIDATE = 2
PIVOT_VALID_BARS_CANDIDATE = 12
BREAK_ATR_CANDIDATE = Decimal("0.10")
BOOK_TTL_SECONDS_CANDIDATE = Decimal("5")
TICKER_TTL_SECONDS_CANDIDATE = Decimal("60")
CLOCK_UNCERTAINTY_LIMIT_APPROVED = Decimal("1.5")
DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


class Unavailable(ValueError):
    """Strict unavailability with a stable, non-sensitive reason code."""


def number(value: object) -> Decimal:
    if isinstance(value, bool):
        raise Unavailable("BOOLEAN_NUMERIC_INPUT")
    try:
        x = Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise Unavailable("NUMERIC_INPUT_INVALID") from exc
    if not x.is_finite():
        raise Unavailable("NONFINITE_NUMERIC_INPUT")
    return x


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise Unavailable("UTC_AWARE_TIME_REQUIRED")
    return value.astimezone(timezone.utc)


def clip(x: Decimal) -> Decimal:
    return min(DECIMAL_ONE, max(DECIMAL_ZERO, x))


def fpos(x: Decimal) -> Decimal:
    x = max(DECIMAL_ZERO, x)
    return x / (DECIMAL_ONE + x)


@dataclass(frozen=True)
class Candle:
    open_at: datetime
    close_at: datetime
    received_at: datetime
    available_at: datetime
    o: Decimal
    h: Decimal
    l: Decimal
    c: Decimal
    q: Decimal
    source_id: str = "SYNTHETIC:CANDLE"

    def __post_init__(self) -> None:
        for key in ("open_at", "close_at", "received_at", "available_at"):
            object.__setattr__(self, key, utc(getattr(self, key)))
        if not self.source_id.startswith("SYNTHETIC:"):
            raise Unavailable("NON_SYNTHETIC_SOURCE_FORBIDDEN")
        if not (self.open_at < self.close_at <= self.received_at <= self.available_at):
            raise Unavailable("CANDLE_RECEIPT_ORDER_INVALID")
        for key in ("o", "h", "l", "c", "q"):
            object.__setattr__(self, key, number(getattr(self, key)))
        if (self.o <= 0 or self.c <= 0 or self.q < 0
                or self.l < 0 or self.h < max(self.o, self.c)
                or self.l > min(self.o, self.c)):
            raise Unavailable("CANDLE_OHLCV_INVALID")


@dataclass(frozen=True)
class SourceReceipt:
    observed_at: datetime
    received_at: datetime
    available_at: datetime
    source_id: str = "SYNTHETIC:MARKET"

    def __post_init__(self) -> None:
        for key in ("observed_at", "received_at", "available_at"):
            object.__setattr__(self, key, utc(getattr(self, key)))
        if not self.source_id.startswith("SYNTHETIC:"):
            raise Unavailable("NON_SYNTHETIC_SOURCE_FORBIDDEN")
        if not self.observed_at <= self.received_at <= self.available_at:
            raise Unavailable("MARKET_RECEIPT_ORDER_INVALID")


@dataclass(frozen=True)
class Market:
    book: SourceReceipt
    ticker24: SourceReceipt
    bid: Decimal
    ask: Decimal
    quote_24h: Decimal
    spot_usdt_trading: bool = True

    def __post_init__(self) -> None:
        for key in ("bid", "ask", "quote_24h"):
            object.__setattr__(self, key, number(getattr(self, key)))
        if type(self.spot_usdt_trading) is not bool:
            raise Unavailable("MARKET_ELIGIBILITY_UNKNOWN")


@dataclass(frozen=True)
class ClockWitness:
    independent_reference: str
    uncertainty_seconds: Decimal
    synthetic: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "uncertainty_seconds", number(self.uncertainty_seconds))
        if not self.synthetic or not self.independent_reference.startswith("SYNTHETIC:"):
            raise Unavailable("REAL_CLOCK_PROOF_NOT_AUTHORIZED")
        if not DECIMAL_ZERO <= self.uncertainty_seconds < CLOCK_UNCERTAINTY_LIMIT_APPROVED:
            raise Unavailable("CLOCK_UNCERTAINTY_AT_OR_ABOVE_LIMIT")


def asof(available_at: datetime, decision_at: datetime, witness: ClockWitness) -> None:
    """Worst-case independent UTC intervals: latest availability <= earliest decision."""
    u = timedelta(seconds=float(witness.uncertainty_seconds))
    if utc(available_at) + u > utc(decision_at) - u:
        raise Unavailable("PIT_AVAILABILITY_NOT_BEFORE_DECISION")


def check_bars(bars: Sequence[Candle], decision: datetime, witness: ClockWitness,
               step: timedelta | None = None) -> None:
    if not bars:
        raise Unavailable("CANDLE_HISTORY_MISSING")
    prev = None
    for b in bars:
        asof(b.available_at, decision, witness)
        if prev and (b.open_at < prev.close_at or
                     (step is not None and b.open_at != prev.open_at + step)):
            raise Unavailable("CANDLE_HISTORY_GAP_OR_OVERLAP")
        if step is not None and b.close_at - b.open_at != step:
            raise Unavailable("CANDLE_TIMEFRAME_MISMATCH")
        prev = b


def close_parts(c: Candle, direction: Direction) -> tuple[Decimal, Decimal, Decimal]:
    rng = c.h - c.l
    if rng <= 0:
        raise Unavailable("ZERO_CANDLE_RANGE")
    d = Decimal("1") if direction is Direction.UP else Decimal("-1")
    k = (DECIMAL_ONE + d * (2 * c.c - c.h - c.l) / rng) / 2
    body = clip(d * (c.c - c.o) / rng)
    wick = c.h - max(c.o, c.c) if d == 1 else min(c.o, c.c) - c.l
    return clip(k), body, clip(DECIMAL_ONE - wick / rng)


def path_parts(bars: Sequence[Candle], direction: Direction) -> tuple[Decimal, Decimal, Decimal]:
    d = DECIMAL_ONE if direction is Direction.UP else -DECIMAL_ONE
    previous = bars[0].o
    diffs = []
    path = [previous]
    for b in bars:
        diffs.append(b.c - previous)
        previous = b.c
        path.append(b.c)
    g = Decimal(sum(1 for x in diffs if d * x > 0)) / Decimal(len(bars))
    net = max(DECIMAL_ZERO, d * (path[-1] - path[0]))
    travel = sum((abs(x) for x in diffs), DECIMAL_ZERO)
    peak = max(max(DECIMAL_ZERO, d * (x - path[0])) for x in path[1:])
    return g, net / travel if travel else DECIMAL_ZERO, net / peak if peak else DECIMAL_ZERO


def atr14_prev(previous: Sequence[Candle]) -> Decimal:
    if len(previous) < 15:
        raise Unavailable("ATR_HISTORY_INSUFFICIENT")
    seq = previous[-15:]
    vals = []
    for p, b in zip(seq[:-1], seq[1:]):
        vals.append(max(b.h - b.l, abs(b.h - p.c), abs(b.l - p.c)))
    result = sum(vals, DECIMAL_ZERO) / 14
    if result <= 0:
        raise Unavailable("ATR_ZERO")
    return result


def required_context(context: Mapping[str, Sequence[Candle]], key: str, n: int,
                     decision: datetime, witness: ClockWitness,
                     step: timedelta) -> Sequence[Candle]:
    bars = context.get(key, ())
    if len(bars) < n:
        raise Unavailable("CONTEXT_MISSING:" + key)
    check_bars(bars, decision, witness, step)
    return bars


def liquidity(market: Market, decision: datetime, witness: ClockWitness) -> Decimal:
    if not market.spot_usdt_trading or market.bid <= 0 or market.ask < market.bid:
        raise Unavailable("BOOK_OR_MARKET_INELIGIBLE")
    mid = (market.bid + market.ask) / 2
    spread = Decimal(10000) * (market.ask - market.bid) / mid
    if spread > 20 or market.quote_24h < 10000000:
        raise Unavailable("SPREAD_OR_24H_TURNOVER_INELIGIBLE")
    for name, receipt, ttl in (("book", market.book, BOOK_TTL_SECONDS_CANDIDATE),
                               ("ticker24", market.ticker24, TICKER_TTL_SECONDS_CANDIDATE)):
        asof(receipt.available_at, decision, witness)
        u = timedelta(seconds=float(witness.uncertainty_seconds))
        max_age = utc(decision) + u - (receipt.observed_at - u)
        if max_age.total_seconds() > float(ttl):
            raise Unavailable("MARKET_SNAPSHOT_STALE:" + name)
    s = clip(DECIMAL_ONE - spread / 20)
    l = clip(DECIMAL_ONE - Decimal(10000000) / market.quote_24h)
    return (3 * s + 2 * l) / 5


def volume_continuity(children: Sequence[Candle], history: Sequence[Candle]) -> Decimal:
    if len(history) < 20:
        raise Unavailable("VOLUME_BASELINE_MISSING")
    q = sorted(x.q for x in history[-20:])
    mean = sum(q, DECIMAL_ZERO) / 20
    median = (q[9] + q[10]) / 2
    if mean <= 0 or median <= 0:
        raise Unavailable("VOLUME_REFERENCE_ZERO")
    rlast = children[-1].q / mean
    v = fpos(rlast - DECIMAL_ONE)
    u = Decimal(sum(1 for b in children if b.q > 0 and b.q >= median)) / len(children)
    return u * (v + u) / 2


def onset_timing(history5: Sequence[Candle], children5: Sequence[Candle],
                 direction: Direction, impulse_state: bool | None) -> Decimal:
    if impulse_state is None:
        raise Unavailable("FULL_IMPULSE_DEFINITION_UNFROZEN")
    history = list(history5) + list(children5)
    if len(history) < 39:
        raise Unavailable("ONSET_HISTORY_INSUFFICIENT")
    d = DECIMAL_ONE if direction is Direction.UP else -DECIMAL_ONE
    k = len(history) - 1
    crossings = []
    for j in range(k - 19, k):  # only preceding closed children, never current
        def q_at(i: int) -> Decimal:
            if i < 18:
                raise Unavailable("ONSET_ATR_HISTORY_MISSING")
            atr = atr14_prev(history[:i])
            return d * (history[i].c - history[i-3].c) / atr
        if (q_at(j) >= ONSET_ATR_THRESHOLD_CANDIDATE
                and q_at(j-1) < ONSET_ATR_THRESHOLD_CANDIDATE):
            crossings.append(j)
    if len(crossings) > 1:
        raise Unavailable("MULTIPLE_ONSET_EPISODES_UNRESOLVED")
    if impulse_state or not crossings:
        return DECIMAL_ZERO
    age = k - crossings[0]
    return clip(DECIMAL_ONE - Decimal(age) / 20) if 1 <= age < 20 else DECIMAL_ZERO


def prior_range_alignment(history: Sequence[Candle], direction: Direction) -> Decimal:
    if len(history) < 21:
        raise Unavailable("CONTEXT_RANGE_HISTORY_MISSING")
    prior, last = history[-21:-1], history[-1]
    upper, lower = max(b.h for b in prior), min(b.l for b in prior)
    if upper <= lower:
        raise Unavailable("CONTEXT_RANGE_ZERO")
    d = DECIMAL_ONE if direction is Direction.UP else -DECIMAL_ONE
    return clip(Decimal(".5") + d * (last.c - (upper + lower)/2) / (upper-lower))


def context_movement(history: Sequence[Candle], direction: Direction, mode: str) -> Decimal:
    if len(history) < 18:
        raise Unavailable("HIGHER_CONTEXT_HISTORY_MISSING")
    d = DECIMAL_ONE if direction is Direction.UP else -DECIMAL_ONE
    if mode == "REVERSAL":
        d = -d
    a = atr14_prev(history[:-1])
    move = (history[-1].c - history[-4].c) / a
    return fpos(d * move)


@dataclass(frozen=True)
class Pivot:
    kind: str
    price: Decimal
    formed_at: datetime
    confirmed_at: datetime
    available_at: datetime
    level_id: str


def confirmed_pivots(history: Sequence[Candle], parent_open: datetime,
                     left: int = PIVOT_LEFT_CANDIDATE,
                     right: int = PIVOT_RIGHT_CANDIDATE) -> tuple[Pivot, ...]:
    """Strict inequality on both sides; right-hand confirmation is historical."""
    if left < 1 or right < 1:
        raise Unavailable("PIVOT_SHAPE_INVALID")
    pivots = []
    for i in range(left, len(history) - right):
        center = history[i]
        neighbors = history[i-left:i] + history[i+1:i+right+1]
        for kind, val, predicate in (
            ("HIGH", center.h, lambda b: val > b.h),
            ("LOW", center.l, lambda b: val < b.l),
        ):
            if all(predicate(other) for other in neighbors):
                confirm = history[i+right]
                # Never use a pivot before the evidence of its right window arrives.
                if confirm.available_at > parent_open:
                    continue
                pivots.append(Pivot(kind, val, center.close_at, confirm.close_at,
                                    confirm.available_at,
                                    kind + ":" + center.close_at.isoformat()))
    return tuple(pivots)


def structure(history: Sequence[Candle], parent: Candle, direction: Direction,
              mode: str, market: Market, decision: datetime, witness: ClockWitness,
              consumed_levels: frozenset[str]) -> tuple[Decimal, bool, str]:
    check_bars(history, decision, witness, timedelta(hours=4))
    pivots = confirmed_pivots(history, parent.open_at)
    highs = [p for p in pivots if p.kind == "HIGH"]
    lows = [p for p in pivots if p.kind == "LOW"]
    if len(highs) < 2 or len(lows) < 2:
        raise Unavailable("PIVOT_HISTORY_INSUFFICIENT")
    rising = highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price
    falling = highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price
    if rising == falling:
        raise Unavailable("PREVIOUS_STRUCTURE_UNKNOWN")
    d = DECIMAL_ONE if direction is Direction.UP else -DECIMAL_ONE
    expected_rising = (direction is Direction.UP) if mode == "CONTINUATION" else (direction is Direction.DOWN)
    if rising != expected_rising:
        raise Unavailable("STRUCTURE_MODE_CONFLICT")
    level = highs[-1] if direction is Direction.UP else lows[-1]
    if (level.level_id in consumed_levels
            or parent.open_at < level.available_at
            or parent.open_at - level.confirmed_at > timedelta(hours=4 * PIVOT_VALID_BARS_CANDIDATE)):
        raise Unavailable("LEVEL_EXPIRED_CONSUMED_OR_FUTURE")
    a = atr14_prev(history)
    if market.bid <= 0 or market.ask < market.bid:
        raise Unavailable("BOOK_INVALID_FOR_BREAK")
    asof(market.book.available_at, decision, witness)
    b = d * (parent.c - level.price) - (market.ask - market.bid)
    event = b > BREAK_ATR_CANDIDATE * a
    z_valid = clip(b / a) if event else DECIMAL_ZERO
    return (Decimal(15) + Decimal(12) * int(event) + 8 * z_valid) / 35, event, level.level_id


def evaluate_r2(*, horizon: Horizon, direction: Direction, mode: str,
                parent: Candle, children: Sequence[Candle], context: Mapping[str, Sequence[Candle]],
                market: Market, witness: ClockWitness, decision_at: datetime,
                impulse_state: bool | None = None,
                consumed_levels: frozenset[str] = frozenset()) -> dict:
    """Compute research *group candidates*, never call a numeric score contract.

    Synthetic fixtures may demonstrate an as-of rule, not independently attest
    real clocks or market provenance. Missing groups remain unavailable.
    """
    if not isinstance(horizon, Horizon) or not isinstance(direction, Direction):
        raise ValueError("R2_HORIZON_DIRECTION_INVALID")
    if mode not in ("CONTINUATION", "REVERSAL"):
        raise ValueError("R2_MODE_INVALID")
    if not isinstance(witness, ClockWitness) or not isinstance(market, Market):
        raise ValueError("R2_SYNTHETIC_PROVENANCE_REQUIRED")
    decision_at = utc(decision_at)
    specs = V2_GROUPS[horizon]
    candidate = {"candidate_contract": VERSION, "horizon": horizon.value,
                 "direction": direction.value, "mode": mode,
                 "status": "DEV_CANDIDATE", "score_status": "SCORE_UNAVAILABLE",
                 "score": None, "probability": None, "qualified": False,
                 "publishable": False, "signal_id": None, "delivery_authorized": False,
                 "pit_status": "SYNTHETIC_ASOF_ONLY_NOT_REAL_PIT",
                 "scientific_status": "NOT_EVALUATED", "forward_status": "NOT_RUN",
                 "normalizers": {}, "missing_reasons": {}, "structural_event": False}
    expected_n = 6 if horizon is Horizon.INTRADAY else 4
    step = timedelta(minutes=5 if horizon is Horizon.INTRADAY else 60)
    try:
        if len(children) != expected_n:
            raise Unavailable("CHILD_COUNT_MISMATCH")
        if parent.source_id != children[0].source_id:
            raise Unavailable("PARENT_CHILD_SOURCE_MISMATCH")
        check_bars(children, decision_at, witness, step)
        asof(parent.available_at, decision_at, witness)
        if (parent.open_at != children[0].open_at
                or parent.close_at != children[-1].close_at
                or any(b.source_id != parent.source_id for b in children)
                or parent.o != children[0].o or parent.c != children[-1].c
                or parent.h != max(b.h for b in children)
                or parent.l != min(b.l for b in children)
                or parent.q != sum((b.q for b in children), DECIMAL_ZERO)):
            raise Unavailable("PARENT_CHILD_RECONCILIATION_FAILED")
    except Unavailable as exc:
        candidate["status"] = "INVALID"
        candidate["missing_reasons"] = {name: str(exc) for name, _ in specs}
        return candidate

    def ctx(key: str, n: int, minutes: int) -> Sequence[Candle]:
        return required_context(context, key, n, decision_at, witness, timedelta(minutes=minutes))

    def calc(name: str) -> Decimal:
        if name in ("30M_STRONG_CLOSE", "FOUR_H_STRONG_CLOSE"):
            k, b, w = close_parts(parent, direction)
            return (8*k+6*b+6*w)/20 if horizon is Horizon.INTRADAY else Decimal(".4")*k+Decimal(".3")*b+Decimal(".3")*w
        if name in ("SIX_5M_INTERNAL_QUALITY", "FOUR_1H_INTERNAL_QUALITY"):
            g,e,t = path_parts(children, direction)
            return (8*g+8*e+4*t)/20 if horizon is Horizon.INTRADAY else Decimal(".4")*g+Decimal(".4")*e+Decimal(".2")*t
        if name == "MOMENTUM_EARLY_TIMING":
            a = atr14_prev(ctx("30m", 15, 30))
            d = DECIMAL_ONE if direction is Direction.UP else -DECIMAL_ONE
            m = max(DECIMAL_ZERO, d*(parent.c-parent.o))/a
            past = ctx("5m", 39, 5)
            if past[-1].close_at != children[0].open_at:
                raise Unavailable("ONSET_HISTORY_NOT_ADJACENT")
            e = onset_timing(past, children, direction, impulse_state)
            return (fpos(m)+e)/2
        if name == "VOLUME_CONTINUITY":
            past = ctx("5m", 20, 5)
            if past[-1].close_at != children[0].open_at:
                raise Unavailable("VOLUME_BASELINE_NOT_ADJACENT")
            return volume_continuity(children, past)
        if name == "MTF_NEARBY_STRUCTURE":
            return (10*prior_range_alignment(ctx("1h", 21, 60), direction)
                    + 5*prior_range_alignment(ctx("4h", 21, 240), direction))/15
        if name == "MARKET_STRUCTURE":
            score, event, level_id = structure(
                ctx("structure4h", 8, 240), parent, direction, mode,
                market, decision_at, witness, consumed_levels)
            candidate["structural_event"] = event
            candidate["candidate_level_id"] = level_id
            return score
        if name == "DAILY_WEEKLY_CONTEXT":
            return (Decimal(".6")*context_movement(ctx("1d", 18, 1440), direction, mode)
                    + Decimal(".4")*context_movement(ctx("1w", 18, 10080), direction, mode))
        if name == "MOMENTUM_VOLUME":
            prior = ctx("4h", 20, 240)
            if prior[-1].close_at != parent.open_at:
                raise Unavailable("SWING_PRIOR_BAR_NOT_ADJACENT")
            a = atr14_prev(prior)
            avg = sum((b.q for b in prior[-20:]), DECIMAL_ZERO)/20
            if avg <= 0:
                raise Unavailable("SWING_VOLUME_REFERENCE_ZERO")
            d = DECIMAL_ONE if direction is Direction.UP else -DECIMAL_ONE
            m = max(DECIMAL_ZERO, d*(parent.c-parent.o))/a
            v = max(DECIMAL_ZERO, parent.q/avg-DECIMAL_ONE)
            return Decimal(".6")*fpos(m)+Decimal(".4")*fpos(v)
        if name == "LIQUIDITY_QUALITY":
            return liquidity(market, decision_at, witness)
        raise Unavailable("UNKNOWN_R2_GROUP")

    for name, _weight in specs:
        try:
            value = calc(name)
            if not value.is_finite() or not 0 <= value <= 1:
                raise Unavailable("NORMALIZER_OUT_OF_RANGE")
            candidate["normalizers"][name] = format(value, "f")
        except Unavailable as exc:
            candidate["normalizers"][name] = None
            candidate["missing_reasons"][name] = str(exc)
    return candidate
