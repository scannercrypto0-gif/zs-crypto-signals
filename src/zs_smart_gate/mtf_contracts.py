"""STAGE-03A: immutable point-in-time multi-timeframe evidence contracts.

NOT qualification, a production signal, technical indicator or Binance ingestion.
The caller must supply explicit per-source OHLCV tolerances (no guessed exchange
rounding rules). A closed candle alone is insufficient: it must be *available*
when the immutable decision snapshot was created. All close times are exclusive.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Sequence

from .core import Candle, decimal, utc

DURATIONS = {
    "5m": timedelta(minutes=5),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
    "1w": timedelta(days=7),
}
CHILD_CONTRACT = {"30m": ("5m", 6), "4h": ("1h", 4)}


@dataclass(frozen=True)
class CandleWindow:
    timeframe: str
    open_at: datetime
    close_at: datetime
    received_at: datetime
    available_at: datetime
    source_id: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    base_volume: Decimal
    quote_volume: Decimal
    validity_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("open_at", "close_at", "received_at", "available_at"):
            object.__setattr__(self, name, utc(getattr(self, name)))
        for name in ("open", "high", "low", "close", "base_volume", "quote_volume"):
            object.__setattr__(self, name, decimal(getattr(self, name)))
        if self.timeframe not in DURATIONS:
            raise ValueError("UNSUPPORTED_TIMEFRAME")
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("MISSING_SOURCE_ID")
        if not isinstance(self.validity_reasons, tuple) or any(
            not isinstance(x, str) or not x for x in self.validity_reasons
        ):
            raise ValueError("INVALID_REASON_CODES")

    @classmethod
    def from_five_minute(cls, candle: Candle, *, source_id: str) -> "CandleWindow":
        return cls("5m", candle.open_at, candle.close_at, candle.received_at,
                   candle.available_at, source_id, candle.open, candle.high, candle.low,
                   candle.close, candle.base_volume, candle.quote_volume)

    def errors_at(self, decision_at: datetime) -> tuple[str, ...]:
        decision_at = utc(decision_at)
        errors = list(self.validity_reasons)
        duration = DURATIONS[self.timeframe]
        # UTC epoch alignment also handles day/week rollover without using local TZ.
        if self.close_at - self.open_at != duration or self.open_at >= self.close_at:
            errors.append("INVALID_DURATION")
        seconds = int(self.open_at.timestamp())
        if self.open_at.microsecond or seconds % int(duration.total_seconds()):
            errors.append("INVALID_UTC_ALIGNMENT")
        if self.high < self.low or self.low <= 0 or not (
            self.low <= self.open <= self.high and self.low <= self.close <= self.high
        ):
            errors.append("INVALID_OHLC")
        if self.base_volume < 0 or self.quote_volume < 0:
            errors.append("INVALID_VOLUME")
        if self.received_at < self.close_at or self.available_at < self.received_at:
            errors.append("NOT_CLOSED_OR_RECEIPT_ORDER")
        if self.close_at > decision_at or self.received_at > decision_at or self.available_at > decision_at:
            errors.append("FUTURE_OR_UNAVAILABLE_AT_DECISION")
        return tuple(dict.fromkeys(errors))


@dataclass(frozen=True)
class ReconciliationTolerance:
    """Absolute numerical tolerance is *explicit* per price/BASE/QUOTE source pair."""

    price: Decimal
    base_volume: Decimal
    quote_volume: Decimal
    policy_id: str

    def __post_init__(self) -> None:
        for name in ("price", "base_volume", "quote_volume"):
            value = decimal(getattr(self, name))
            if value < 0:
                raise ValueError("NEGATIVE_TOLERANCE")
            object.__setattr__(self, name, value)
        if not isinstance(self.policy_id, str) or not self.policy_id:
            raise ValueError("MISSING_TOLERANCE_POLICY_ID")


@dataclass(frozen=True)
class Reconciliation:
    parent_timeframe: str
    decision_at: datetime
    status: str
    reason_codes: tuple[str, ...]
    child_count: int
    tolerance_policy_id: str

    def as_dict(self) -> dict:
        return {"parent_timeframe": self.parent_timeframe,
                "decision_at": self.decision_at.isoformat(),
                "status": self.status, "reason_codes": list(self.reason_codes),
                "child_count": self.child_count,
                "tolerance_policy_id": self.tolerance_policy_id}


def reconcile(parent: CandleWindow, children: Sequence[CandleWindow],
              decision_at: datetime, *, tolerance: ReconciliationTolerance) -> Reconciliation:
    """Integrity only: cannot determine strong close, BOS, or qualified signal."""
    decision_at = utc(decision_at)
    if parent.timeframe not in CHILD_CONTRACT:
        raise ValueError("NO_CHILD_CONTRACT_FOR_TIMEFRAME")
    child_frame, expected = CHILD_CONTRACT[parent.timeframe]
    reasons: list[str] = []
    if len(children) != expected:
        reasons.append("CHILD_COUNT_MISMATCH")
    reasons.extend("PARENT_" + x for x in parent.errors_at(decision_at))
    previous_end = parent.open_at
    seen = set()
    for i, child in enumerate(children):
        if child.timeframe != child_frame:
            reasons.append("CHILD_TIMEFRAME_MISMATCH")
        if child.source_id != parent.source_id:
            # Explicit: cross-source volume reconciliation tolerances are not approved.
            reasons.append("MIXED_SOURCES_UNVERIFIED")
        if (child.open_at, child.close_at) in seen:
            reasons.append("DUPLICATE_CHILD")
        seen.add((child.open_at, child.close_at))
        if child.open_at != previous_end:
            reasons.append("GAP_OR_OVERLAP_OR_OUT_OF_ORDER")
        previous_end = child.close_at
        reasons.extend(f"CHILD_{i}_{x}" for x in child.errors_at(decision_at))
    if not children or children[0].open_at != parent.open_at or children[-1].close_at != parent.close_at:
        reasons.append("PARENT_CHILD_WINDOW_MISMATCH")
    if len(children) == expected and not reasons:
        aggregate = {
            "open": children[0].open,
            "close": children[-1].close,
            "high": max(x.high for x in children),
            "low": min(x.low for x in children),
            "base_volume": sum((x.base_volume for x in children), Decimal("0")),
            "quote_volume": sum((x.quote_volume for x in children), Decimal("0")),
        }
        for name, value in aggregate.items():
            margin = (tolerance.price if name in ("open", "close", "high", "low")
                      else getattr(tolerance, name))
            if abs(getattr(parent, name) - value) > margin:
                reasons.append(name.upper() + "_AGGREGATION_MISMATCH")
    return Reconciliation(
        parent.timeframe, decision_at, "PASS" if not reasons else "INVALID",
        tuple(dict.fromkeys(reasons)), len(children), tolerance.policy_id)


def available_closed_context(candles: Sequence[CandleWindow], *,
                             timeframe: str, decision_at: datetime) -> CandleWindow | None:
    """Return latest closed *known* context, never the freshest future/delayed bar."""
    decision_at = utc(decision_at)
    if timeframe not in ("1h", "4h", "1d", "1w"):
        raise ValueError("UNSUPPORTED_CONTEXT_FRAME")
    valid = [bar for bar in candles if bar.timeframe == timeframe and not bar.errors_at(decision_at)]
    return max(valid, key=lambda bar: bar.close_at) if valid else None
