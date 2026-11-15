"""R0: new *research-only* 30m evaluation identity, independent of 5m discovery.

Additive to historical QV1 and zs.stage05.event.v1; neither is rewritten.
An evaluation event is not a Signal Event, and does not authorize dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from .core import utc
from .stage05_contracts import ContractError, canonical, digest

VERSION = "zs.r0.independent-30m-evaluation.v1"
VENUE = "BINANCE_SPOT"
SUBTYPES = frozenset(("GENERAL_30M", "CONTINUATION_30M", "REVERSAL_30M"))
SYMBOL = re.compile(r"[A-Z0-9]{3,20}USDT\Z")
FROZEN_SETUP_VERSION = "ORDER021_SETUP_V1_1_FROZEN"


def stamp(value: datetime) -> str:
    return utc(value).isoformat(timespec="microseconds" if utc(value).microsecond
                                else "seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class DiscoveryReference:
    """Optional evidence from frozen Setup v1.1, never a qualification prerequisite."""

    state: str
    source_rule_version: str = FROZEN_SETUP_VERSION
    subtype: str = "5M_BREAKOUT_SUBTYPE"

    def __post_init__(self) -> None:
        if (self.source_rule_version != FROZEN_SETUP_VERSION
                or self.subtype != "5M_BREAKOUT_SUBTYPE"
                or self.state not in ("DETECTED_SETUP", "NO_BREAKOUT",
                                      "NO_FALSE_TO_TRUE_TRANSITION")):
            raise ContractError("R0_DISCOVERY_REFERENCE_INVALID")

    def as_dict(self) -> dict:
        return {"state": self.state, "source_rule_version": self.source_rule_version,
                "subtype": self.subtype}


@dataclass(frozen=True)
class EvaluationIdentity:
    """Stable economic-window key, NOT a source-receipt hash.

    Same 30m close + subtype across retries => same key; different close or
    explicitly distinct bounded research setup family => different key.
    Subtypes do not attest real structural independence or qualification.
    """

    symbol: str
    parent_close_at: datetime
    discriminator: str = "GENERAL_30M"
    venue: str = VENUE
    direction: str = "UP"
    horizon: str = "INTRADAY"

    def __post_init__(self) -> None:
        if (self.venue != VENUE or self.direction != "UP" or self.horizon != "INTRADAY"
                or not isinstance(self.symbol, str) or not SYMBOL.fullmatch(self.symbol)
                or self.discriminator not in SUBTYPES):
            raise ContractError("R0_EVALUATION_IDENTITY_INVALID")
        close = utc(self.parent_close_at)
        if (close.second or close.microsecond or close.minute % 30
                or close.hour < 0):
            raise ContractError("R0_PARENT_CLOSE_NOT_ALIGNED")
        object.__setattr__(self, "parent_close_at", close)

    @property
    def key(self) -> str:
        return digest(canonical([VERSION, self.venue, self.symbol, self.direction,
                                 self.horizon, stamp(self.parent_close_at),
                                 self.discriminator]))

    def as_dict(self) -> dict:
        return {
            "schema": VERSION, "event_id": "eval30-" + self.key,
            "candidate_id": "cand30-" + self.key,
            "event_kind": "RAW_30M_EVALUATION", "venue": self.venue,
            "symbol": self.symbol, "direction": self.direction, "horizon": self.horizon,
            "parent_close_at": stamp(self.parent_close_at),
            "event_discriminator": self.discriminator,
            "qualification_state": "UNKNOWN", "signal_id": None,
        }
