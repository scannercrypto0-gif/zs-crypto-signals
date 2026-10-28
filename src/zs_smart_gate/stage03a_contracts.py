"""Stage 03A: typed schema-only lifecycle, identity, V2 and Spot plan.

No qualification formula, score aggregation, event publication, Telegram, or
persistent dedup is authorized. Prototype identity is deterministic *in memory*;
Stage 04 must durably assign/recover signal_id before any real delivery.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
import hashlib
import json

from .core import ResearchCandidate, decimal, utc
from .mtf_contracts import Reconciliation


class Lifecycle(str, Enum):
    RAW_OBSERVATION = "RAW_OBSERVATION"
    EARLY_WATCH = "EARLY_WATCH"
    RESEARCH_CANDIDATE = "RESEARCH_CANDIDATE"
    QUALIFIED_SIGNAL = "QUALIFIED_SIGNAL"  # reserved, not issuable in Stage 03A
    REJECTED = "REJECTED"
    INVALID = "INVALID"


class Direction(str, Enum):
    UP = "UP"
    DOWN = "DOWN"


class Horizon(str, Enum):
    INTRADAY = "INTRADAY"
    SWING = "SWING"


STAGE_03A_SCHEMA = "03A.1"
V2_GROUPS = {
    Horizon.INTRADAY: (
        ("30M_STRONG_CLOSE", 20),
        ("SIX_5M_INTERNAL_QUALITY", 20),
        ("MOMENTUM_EARLY_TIMING", 20),
        ("VOLUME_CONTINUITY", 20),
        ("MTF_NEARBY_STRUCTURE", 15),
        ("LIQUIDITY_QUALITY", 5),
    ),
    Horizon.SWING: (
        ("MARKET_STRUCTURE", 35),
        ("FOUR_H_STRONG_CLOSE", 15),
        ("FOUR_1H_INTERNAL_QUALITY", 15),
        ("DAILY_WEEKLY_CONTEXT", 15),
        ("MOMENTUM_VOLUME", 15),
        ("LIQUIDITY_QUALITY", 5),
    ),
}
V2_VERSION = {Horizon.INTRADAY: "INTRADAY_V2_RESEARCH_UNCALIBRATED",
              Horizon.SWING: "SWING_V2_RESEARCH_UNCALIBRATED"}


@dataclass(frozen=True)
class ScoreGroup:
    name: str
    maximum: int
    raw_value: Decimal | None = None
    normalized_value: Decimal | None = None
    contribution: Decimal | None = None
    missing_reason: str = "NUMERIC_FORMULA_NOT_APPROVED"

    def __post_init__(self) -> None:
        for name in ("raw_value", "normalized_value", "contribution"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, decimal(getattr(self, name)))
        if self.normalized_value is not None and not 0 <= self.normalized_value <= 1:
            raise ValueError("SCORE_GROUP_NORMALIZATION_OUT_OF_RANGE")
        if self.contribution is not None and not 0 <= self.contribution <= self.maximum:
            raise ValueError("SCORE_GROUP_CONTRIBUTION_OUT_OF_RANGE")
        if self.contribution is not None and self.normalized_value is None:
            raise ValueError("UNPROVEN_SCORE_GROUP_CONTRIBUTION")


@dataclass(frozen=True)
class ScoreV2:
    horizon: Horizon
    direction: Direction
    score_version: str
    groups: tuple[ScoreGroup, ...]
    status: str = "SCORE_UNAVAILABLE"
    total: None = None
    missing_reasons: tuple[str, ...] = ("NUMERIC_NORMALIZATION_UNAPPROVED",)

    def __post_init__(self) -> None:
        if self.score_version != V2_VERSION[self.horizon]:
            raise ValueError("SCORE_VERSION_HORIZON_MISMATCH")
        if tuple((x.name, x.maximum) for x in self.groups) != V2_GROUPS[self.horizon]:
            raise ValueError("SCORE_GROUPS_OR_WEIGHTS_CHANGED")
        if sum(x.maximum for x in self.groups) != 100:
            raise ValueError("SCORE_MAXIMUM_NOT_100")
        if self.status != "SCORE_UNAVAILABLE" or self.total is not None:
            raise ValueError("STAGE_03A_CANNOT_ISSUE_NUMERIC_SCORE")
        if not self.missing_reasons:
            raise ValueError("SCORE_MISSING_REASONS_REQUIRED")

    def as_dict(self) -> dict:
        return {
            "score_version": self.score_version, "horizon": self.horizon.value,
            "direction": self.direction.value, "status": self.status,
            "total": None, "maximum": 100, "probability": None,
            "missing_reasons": list(self.missing_reasons),
            "groups": [{"name": x.name, "maximum": x.maximum,
                        "raw_value": str(x.raw_value) if x.raw_value is not None else None,
                        "normalized_value": str(x.normalized_value) if x.normalized_value is not None else None,
                        "contribution": str(x.contribution) if x.contribution is not None else None,
                        "missing_reason": x.missing_reason} for x in self.groups],
        }


def unavailable_score(horizon: Horizon, direction: Direction) -> ScoreV2:
    groups = tuple(ScoreGroup(name, maximum) for name, maximum in V2_GROUPS[horizon])
    return ScoreV2(horizon, direction, V2_VERSION[horizon], groups)


@dataclass(frozen=True)
class EventIdentity:
    asset_id: str
    horizon: Horizon
    direction: Direction
    setup_type: str
    decision_candle_close_at: datetime
    rule_version: str
    event_discriminator: str
    detection_event_key: str
    schema_version: str = STAGE_03A_SCHEMA
    signal_id: None = None  # not issued until Stage 04/05 durable lifecycle

    @classmethod
    def research_key(cls, *, symbol: str, horizon: Horizon, direction: Direction,
                     setup_type: str, decision_candle_close_at: datetime,
                     rule_version: str, event_discriminator: str) -> "EventIdentity":
        """Dedupe *key proposal*, not durable assign-once signal_id or emission."""
        decision_candle_close_at = utc(decision_candle_close_at)
        if (not symbol or not symbol.endswith("USDT") or
                not setup_type or not rule_version or not event_discriminator):
            raise ValueError("INCOMPLETE_EVENT_IDENTITY")
        asset = "BINANCE:SPOT:" + symbol
        fields = [STAGE_03A_SCHEMA, asset, horizon.value, direction.value,
                  setup_type, decision_candle_close_at.isoformat(),
                  rule_version, event_discriminator]
        payload = json.dumps(fields, ensure_ascii=True, separators=(",", ":"))
        key = "RESEARCH-KEY-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return cls(asset, horizon, direction, setup_type, decision_candle_close_at,
                   rule_version, event_discriminator, key)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_candle_close_at", utc(self.decision_candle_close_at))
        if self.signal_id is not None:
            raise ValueError("STAGE_03A_CANNOT_ASSIGN_SIGNAL_ID")

    def as_dict(self) -> dict:
        return {
            "schema_version": self.schema_version, "asset_id": self.asset_id,
            "horizon": self.horizon.value, "direction": self.direction.value,
            "setup_type": self.setup_type,
            "decision_candle_close_at": self.decision_candle_close_at.isoformat(),
            "rule_version": self.rule_version, "event_discriminator": self.event_discriminator,
            "detection_event_key": self.detection_event_key, "signal_id": None,
        }


@dataclass(frozen=True)
class ResearchEvent:
    """Immutable PIT candidate observation, never a qualified live Signal."""
    identity: EventIdentity
    candidate_id: str
    status: Lifecycle
    decision_at: datetime
    candidate: ResearchCandidate
    reconciliation: Reconciliation
    score: ScoreV2
    reason_codes: tuple[str, ...]
    schema_version: str = STAGE_03A_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_at", utc(self.decision_at))
        if self.status not in (Lifecycle.RESEARCH_CANDIDATE, Lifecycle.REJECTED, Lifecycle.INVALID):
            raise ValueError("NO_LIVE_SIGNAL_TRANSITION_IN_STAGE_03A")
        if not self.candidate_id or not self.reason_codes:
            raise ValueError("RESEARCH_EVENT_REASONS_AND_CANDIDATE_ID_REQUIRED")
        if (self.candidate.symbol != self.identity.asset_id.removeprefix("BINANCE:SPOT:")
                or self.candidate.decision_at != self.decision_at
                or self.reconciliation.decision_at != self.decision_at
                or self.identity.decision_candle_close_at != self.reconciliation.parent_close_at
                or self.identity.decision_candle_close_at > self.decision_at
                or self.reconciliation.parent_timeframe != (
                    "30m" if self.identity.horizon == Horizon.INTRADAY else "4h")):
            raise ValueError("PIT_CANDIDATE_OR_WINDOW_IDENTITY_MISMATCH")
        if (self.identity.direction != self.score.direction or
                self.identity.horizon != self.score.horizon):
            raise ValueError("SCORE_HORIZON_DIRECTION_MISMATCH")
        if self.status == Lifecycle.RESEARCH_CANDIDATE and (
            self.candidate.status != "ELIGIBLE" or self.reconciliation.status != "PASS"):
            raise ValueError("CANNOT_PROMOTE_INVALID_RESEARCH")

    def as_dict(self) -> dict:
        return {
            "schema_version": self.schema_version, "candidate_id": self.candidate_id,
            "identity": self.identity.as_dict(), "status": self.status.value,
            "decision_at": self.decision_at.isoformat(),
            "candidate": self.candidate.as_dict(),
            "window": self.reconciliation.as_dict(), "score": self.score.as_dict(),
            "reason_codes": list(self.reason_codes),
            "publishable": False, "delivery_authorized": False,
        }


def bind_research_candidate(*, candidate: ResearchCandidate,
                            identity: EventIdentity, reconciliation: Reconciliation,
                            candidate_id: str) -> ResearchEvent:
    """Real Stage-01 core candidate → Stage-03A *contract only* E2E."""
    if candidate.status == "ELIGIBLE" and reconciliation.status == "PASS":
        state = Lifecycle.RESEARCH_CANDIDATE
        reasons = ("RESEARCH_ONLY_NOT_QUALIFIED", "STAGE_03B_FORMULAS_UNAPPROVED")
    else:
        state = Lifecycle.INVALID if reconciliation.status != "PASS" else Lifecycle.REJECTED
        reasons = ("NOT_PUBLISHABLE",) + candidate.eligibility_reasons + candidate.candle_errors + reconciliation.reason_codes
    return ResearchEvent(identity, candidate_id, state, candidate.decision_at, candidate,
                         reconciliation, unavailable_score(identity.horizon, identity.direction),
                         reasons)


class ResearchKeyRegistry:
    """Ephemeral fixture/reference dedup semantics, NOT a durable store/outbox."""

    def __init__(self) -> None:
        self._seen: dict[str, EventIdentity] = {}

    def observe(self, identity: EventIdentity) -> str:
        prior = self._seen.get(identity.detection_event_key)
        if prior is not None:
            if prior != identity:
                raise ValueError("IDENTITY_KEY_COLLISION")
            return "DUPLICATE_RETRY"
        self._seen[identity.detection_event_key] = identity
        return "NEW_RESEARCH_EVENT"


@dataclass(frozen=True)
class TradePlan:
    """Stage 03A default: typed Spot research-only plan with null levels."""
    signal_id: str | None
    direction: Direction
    plan_version: str = "03A_RESEARCH_ONLY"
    plan_status: str = "RESEARCH_ONLY"
    trade_action: str = "OBSERVE_ONLY"
    entry_zone_low: Decimal | None = None
    entry_zone_high: Decimal | None = None
    stop_loss: Decimal | None = None
    tp1: Decimal | None = None
    tp2: Decimal | None = None
    tp3: Decimal | None = None
    entry_expiry_at_utc: datetime | None = None
    calculation_method_version: str | None = None
    tick_size: Decimal | None = None
    lot_size: Decimal | None = None
    min_notional: Decimal | None = None
    fee_model: str | None = None
    slippage_assumption: Decimal | None = None
    price_source: str | None = None
    reason_codes: tuple[str, ...] = ("PLAN_ALGORITHM_NOT_APPROVED",)
    trade_plan_id: str | None = None

    def __post_init__(self) -> None:
        if self.plan_status != "RESEARCH_ONLY":
            raise ValueError("TRADE_READY_REQUIRES_APPROVED_ALGORITHM")
        if self.trade_action not in ("OBSERVE_ONLY", "BUY_SPOT", "SELL_OWNED_SPOT"):
            raise ValueError("FUTURES_OR_AUTO_TRADE_ACTION_PROHIBITED")
        if self.trade_action == "BUY_SPOT" and self.direction != Direction.UP:
            raise ValueError("TRADE_DIRECTION_ACTION_MISMATCH")
        if self.trade_action == "SELL_OWNED_SPOT" and self.direction != Direction.DOWN:
            raise ValueError("TRADE_DIRECTION_ACTION_MISMATCH")
        if any(getattr(self, name) is not None for name in (
            "entry_zone_low", "entry_zone_high", "stop_loss", "tp1", "tp2", "tp3")):
            raise ValueError("UNVALIDATED_TRADE_LEVELS_MUST_BE_NULL")
        for name in ("tick_size", "lot_size", "min_notional", "slippage_assumption"):
            val = getattr(self, name)
            if val is not None:
                d = decimal(val)
                if d < 0:
                    raise ValueError("INVALID_SPOT_PRECISION_OR_COST")
                object.__setattr__(self, name, d)
        if self.entry_expiry_at_utc is not None:
            object.__setattr__(self, "entry_expiry_at_utc", utc(self.entry_expiry_at_utc))
        if not self.reason_codes:
            raise ValueError("RESEARCH_ONLY_REASONS_REQUIRED")

    def as_dict(self) -> dict:
        return {
            "signal_id": self.signal_id, "trade_plan_id": self.trade_plan_id,
            "plan_version": self.plan_version, "plan_status": self.plan_status,
            "direction": self.direction.value, "trade_action": self.trade_action,
            "entry_zone_low": None, "entry_zone_high": None, "stop_loss": None,
            "tp1": None, "tp2": None, "tp3": None,
            "entry_expiry_at_utc": (self.entry_expiry_at_utc.isoformat()
                                    if self.entry_expiry_at_utc else None),
            "calculation_method_version": self.calculation_method_version,
            "tick_size": str(self.tick_size) if self.tick_size is not None else None,
            "lot_size": str(self.lot_size) if self.lot_size is not None else None,
            "min_notional": str(self.min_notional) if self.min_notional is not None else None,
            "fee_model": self.fee_model,
            "slippage_assumption": (str(self.slippage_assumption)
                                    if self.slippage_assumption is not None else None),
            "price_source": self.price_source, "reason_codes": list(self.reason_codes),
            "manual_spot_only": True, "trade_ready": False,
        }


@dataclass(frozen=True)
class SwingPivot:
    pivot_id: str
    timeframe: str
    formed_at: datetime
    confirmed_at: datetime
    available_at: datetime
    level: Decimal
    side: str
    source_id: str

    def __post_init__(self) -> None:
        for name in ("formed_at", "confirmed_at", "available_at"):
            object.__setattr__(self, name, utc(getattr(self, name)))
        object.__setattr__(self, "level", decimal(self.level))
        if not self.pivot_id or not self.source_id or self.timeframe not in ("1h", "4h", "1d"):
            raise ValueError("INVALID_PIVOT_IDENTITY")
        if self.side not in ("HIGH", "LOW") or self.level <= 0:
            raise ValueError("INVALID_PIVOT_LEVEL_OR_SIDE")
        if not self.formed_at <= self.confirmed_at <= self.available_at:
            raise ValueError("FUTURE_CONFIRMED_PIVOT_TIME_ORDER")

    def known_at(self, decision_at: datetime) -> bool:
        return self.available_at <= utc(decision_at)


@dataclass(frozen=True)
class StructureEvidence:
    """Declarative BOS/CHoCH claim; no pivot search or breakout math here."""
    event_type: str
    pivot: SwingPivot
    break_candle_close_at: datetime
    observed_at: datetime
    decision_at: datetime
    confirmed_close: bool
    status: str

    def __post_init__(self) -> None:
        for name in ("break_candle_close_at", "observed_at", "decision_at"):
            object.__setattr__(self, name, utc(getattr(self, name)))
        if self.event_type not in ("BOS", "CHoCH"):
            raise ValueError("UNKNOWN_STRUCTURE_EVENT")
        if self.status != "UNVERIFIED_RESEARCH_CONTRACT":
            raise ValueError("STAGE_03A_CANNOT_CONFIRM_BOS_CHOCH")
        if not self.confirmed_close or self.break_candle_close_at > self.observed_at:
            raise ValueError("BREAK_NOT_CLOSED_AT_OBSERVATION")
        if self.observed_at > self.decision_at:
            raise ValueError("BREAK_FUTURE_AT_DECISION")
        if not self.pivot.known_at(self.break_candle_close_at):
            raise ValueError("PIVOT_NOT_KNOWN_BEFORE_BREAK")
        if not self.pivot.known_at(self.decision_at):
            raise ValueError("PIVOT_FUTURE_AT_DECISION")
