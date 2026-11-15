"""Stage06A bounded, offline-only chronological outcome research.

No orders, transport, data fetching, signal issuance, or historical fill claims.
The earliest assessable bar opens at/after the measured signal availability.
A hit means the bar's range touched a level; exact intrabar fill time is unknown.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Sequence


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("an explicit timezone-aware UTC datetime is required")
    return value


def _price(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise ValueError("prices must be positive finite Decimal values")
    return value


@dataclass(frozen=True)
class TradeLevels:
    direction: str  # LONG or SHORT; SHORT is analysis only, never a trading instruction
    entry: Decimal
    stop: Decimal
    target: Decimal

    def validate(self) -> None:
        _price(self.entry)
        _price(self.stop)
        _price(self.target)
        if self.direction == "LONG":
            valid = self.stop < self.entry < self.target
        elif self.direction == "SHORT":
            valid = self.target < self.entry < self.stop
        else:
            raise ValueError("unsupported direction")
        if not valid:
            raise ValueError("entry/stop/target price ordering is invalid")


@dataclass(frozen=True)
class ClosedBar:
    open_at: datetime
    close_at: datetime
    available_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    closed: bool = True

    def validate(self) -> None:
        a, b, c = _utc(self.open_at), _utc(self.close_at), _utc(self.available_at)
        if not a < b <= c or not self.closed:
            raise ValueError("bar must be finalized, ordered, and source-available")
        for value in (self.open, self.high, self.low, self.close):
            _price(value)
        if not (self.low <= self.open <= self.high and self.low <= self.close <= self.high):
            raise ValueError("OHLC boundaries are inconsistent")


@dataclass(frozen=True)
class Outcome:
    status: str
    as_of: datetime
    examined_bars: int
    entry_bar_open_at: datetime | None = None
    exit_bar_open_at: datetime | None = None
    note: str = ""


def evaluate_outcome(
    plan: TradeLevels,
    signal_available_at: datetime,
    as_of: datetime,
    bars: Sequence[ClosedBar],
) -> Outcome:
    """Evaluate only strictly observed closed bars; no synthetic intrabar ordering.

    Bars straddling signal availability are excluded: outcomes apply to the
    first *complete* post-availability bar onward, not to the signal's full life.
    No-entry means no entry in this explicitly examined and contiguous window.
    """
    plan.validate()
    signal_available_at, as_of = _utc(signal_available_at), _utc(as_of)
    if as_of < signal_available_at:
        raise ValueError("as_of predates signal availability")

    eligible: list[ClosedBar] = []
    previous: ClosedBar | None = None
    straddling = 0
    for bar in bars:
        bar.validate()
        if previous is not None and bar.open_at < previous.close_at:
            raise ValueError("out-of-order or overlapping bars")
        previous = bar
        if bar.open_at < signal_available_at:
            if bar.close_at > signal_available_at:
                straddling += 1
            continue
        if bar.close_at > as_of or bar.available_at > as_of:
            return Outcome("UNAVAILABLE_FUTURE_BAR", as_of, len(eligible), note="bar not known by as_of")
        eligible.append(bar)

    if not eligible:
        return Outcome("INSUFFICIENT_HISTORY", as_of, 0, note="no complete post-availability bar")

    entered_at: datetime | None = None
    last_close: datetime | None = None
    for index, bar in enumerate(eligible, 1):
        if last_close is not None and bar.open_at != last_close:
            return Outcome("DATA_GAP", as_of, index - 1, entered_at, note="missing candle interval")
        last_close = bar.close_at
        entry_touch = bar.low <= plan.entry <= bar.high
        stop_touch = bar.low <= plan.stop <= bar.high
        target_touch = bar.low <= plan.target <= bar.high
        if entered_at is None:
            if not entry_touch:
                continue
            entered_at = bar.open_at
            if stop_touch or target_touch:
                return Outcome("AMBIGUOUS_ENTRY_BAR", as_of, index, entered_at,
                               note="entry/exit order within a single candle is unobservable")
            continue
        if stop_touch and target_touch:
            return Outcome("AMBIGUOUS_EXIT_BAR", as_of, index, entered_at, bar.open_at,
                           "stop/target order within a single candle is unobservable")
        if stop_touch:
            return Outcome("STOP_TOUCHED", as_of, index, entered_at, bar.open_at,
                           "range touch; not a proven executed fill")
        if target_touch:
            return Outcome("TARGET_TOUCHED", as_of, index, entered_at, bar.open_at,
                           "range touch; not a proven executed fill")

    suffix = f"; excluded {straddling} availability-straddling bar(s)" if straddling else ""
    if entered_at is not None:
        return Outcome("OPEN_UNRESOLVED", as_of, len(eligible), entered_at,
                       note="no observed exit in scoped window" + suffix)
    return Outcome("NO_ENTRY", as_of, len(eligible), note="within observed full-bar window only" + suffix)
