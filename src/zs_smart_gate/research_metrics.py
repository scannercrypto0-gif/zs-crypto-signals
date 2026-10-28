"""03B1 descriptive metrics ONLY. No score, qualification, probability or trading gates.

Versioned hypotheses with explicit directional price basis, units and PIT sources.
Zero ranges/path/volumes are unavailable, never silently replaced with zero.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Sequence

from .core import decimal, utc
from .mtf_contracts import CandleWindow
from .stage03a_contracts import Direction

VERSION = "03B1_DESCRIPTIVE_CANDIDATES_V1_UNAPPROVED"


@dataclass(frozen=True)
class Metric:
    name: str
    direction: Direction
    value: Decimal | None
    unit: str
    basis: str
    source_id: str
    source_close_at: datetime
    available_at: datetime
    status: str
    missing_reason: str | None = None
    version: str = VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_close_at", utc(self.source_close_at))
        object.__setattr__(self, "available_at", utc(self.available_at))
        if self.value is not None:
            object.__setattr__(self, "value", decimal(self.value))
        if self.status != "RESEARCH_METRIC_UNAPPROVED":
            raise ValueError("METRIC_APPROVAL_NOT_AUTHORIZED")
        if (self.value is None) != (self.missing_reason is not None):
            raise ValueError("METRIC_MISSINGNESS_NOT_EXPLICIT")

    def as_dict(self) -> dict:
        return {"name": self.name, "direction": self.direction.value,
                "value": str(self.value) if self.value is not None else None,
                "unit": self.unit, "basis": self.basis,
                "source_id": self.source_id,
                "source_close_at": self.source_close_at.isoformat(),
                "available_at": self.available_at.isoformat(),
                "status": self.status, "missing_reason": self.missing_reason,
                "version": self.version}


def describe(parent: CandleWindow, children: Sequence[CandleWindow],
             *, direction: Direction, decision_at: datetime) -> tuple[Metric, ...]:
    """Only call after Stage-03A strict reconcile PASS; defensively recheck PIT.

    Normalized fractions here describe observed candles, NOT V2 normalized
    score contributions; proposals require empirical testing and owner review.
    """
    decision_at = utc(decision_at)
    if not isinstance(direction, Direction):
        raise ValueError("DIRECTION_ENUM_REQUIRED")
    if parent.errors_at(decision_at) or not children or any(
        c.errors_at(decision_at) or c.source_id != parent.source_id for c in children
    ):
        raise ValueError("METRIC_INPUT_NOT_PIT_VALID")
    sign = Decimal(1) if direction is Direction.UP else Decimal(-1)
    rng = parent.high - parent.low
    move = parent.close - parent.open
    body = abs(move)
    parent_total_vol = sum((c.quote_volume for c in children), Decimal(0))
    # Purely descriptive. Gaps between child opens and previous closes are
    # already rejected by strict 03A alignment/aggregation, but path definition
    # explicitly sums each child's OPEN_TO_CLOSE displacement, not interbar gaps.
    path = sum((abs(c.close - c.open) for c in children), Decimal(0))
    net = sign * (children[-1].close - children[0].open)
    half = len(children) // 2
    first_volume = sum((c.quote_volume for c in children[:half]), Decimal(0))
    second_volume = sum((c.quote_volume for c in children[half:]), Decimal(0))
    directional_volume = sum((c.quote_volume for c in children
                              if sign * (c.close - c.open) > 0), Decimal(0))
    last_available = max(c.available_at for c in (parent, *children))

    def metric(name: str, value: Decimal | None, unit: str, basis: str,
               reason: str = "ZERO_DENOMINATOR") -> Metric:
        return Metric(name, direction, value, unit, basis, parent.source_id,
                      parent.close_at, last_available, "RESEARCH_METRIC_UNAPPROVED",
                      reason if value is None else None)

    return (
        metric("DIRECTIONAL_PARENT_CLOSE_LOCATION",
               ((parent.close - parent.low) if sign == 1
                else (parent.high - parent.close)) / rng if rng > 0 else None,
               "fraction_0_1", "UP:(close-low)/range; DOWN:(high-close)/range"),
        metric("SIGNED_PARENT_BODY_FRACTION",
               sign * move / rng if rng > 0 else None, "signed_fraction",
               "sign*(close-open)/(high-low)"),
        metric("ABS_PARENT_BODY_FRACTION",
               body / rng if rng > 0 else None, "fraction_0_1",
               "abs(close-open)/(high-low)"),
        metric("ADVERSE_WICK_FRACTION",
               ((parent.high-max(parent.open, parent.close)) if sign == 1
                else (min(parent.open, parent.close)-parent.low)) / rng if rng > 0 else None,
               "fraction_0_1", "UP:upper_wick/range; DOWN:lower_wick/range"),
        metric("SIGNED_CHILD_NET_TO_PATH",
               net / path if path > 0 else None, "signed_ratio",
               "sign*(last_child_close-first_child_open)/sum(abs(child_close-child_open))"),
        metric("SECOND_HALF_QUOTE_VOLUME_SHARE",
               second_volume / parent_total_vol if parent_total_vol > 0 else None,
               "fraction_0_1",
               "sum(second_half_child_quote_volume)/sum(all_child_quote_volume)"),
        metric("DIRECTION_FAVORABLE_QUOTE_VOLUME_SHARE",
               directional_volume / parent_total_vol if parent_total_vol > 0 else None,
               "fraction_0_1",
               "sum(quote_volume of child bodies in stated direction)/all_child_quote_volume"),
        metric("SECOND_MINUS_FIRST_QUOTE_VOLUME",
               second_volume - first_volume, "quote_asset_units",
               "sum(second_half_quote_volume)-sum(first_half_quote_volume)"),
    )
