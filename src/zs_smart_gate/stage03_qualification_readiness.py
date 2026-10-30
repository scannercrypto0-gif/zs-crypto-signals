"""Offline Stage-03 qualification readiness using accepted 01/03A/03B1 contracts.

No source fetch, normalization formula, score-03C import, persistence, publication,
production signal ID, Telegram, clock attestation, scheduler or trading.
PR #15's 03C scorer remains a separate unmerged dependency.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, Sequence

from .core import Candle, MarketSnapshot, build_candidate, utc, validate_candles
from .mtf_contracts import (CandleWindow, ReconciliationTolerance, reconcile)
from .research_metrics import describe
from .stage03a_contracts import (Direction, EventIdentity, Horizon, Lifecycle,
                                 ResearchKeyRegistry, V2_GROUPS, bind_research_candidate)

VERSION = "03_QUALIFICATION_READINESS_OFFLINE_V1"
_FRAMES = {Horizon.INTRADAY: ("30m", "5m", 6),
           Horizon.SWING: ("4h", "1h", 4)}
_PRICES_AND_VOLUMES = ("open", "high", "low", "close", "base_volume", "quote_volume")


def assess_readiness(*, symbol: str, horizon: Horizon, direction: Direction,
                     parent: CandleWindow, children: Sequence[CandleWindow],
                     core_5m: Sequence[Candle], market: MarketSnapshot,
                     decision_at: datetime, tolerance: ReconciliationTolerance,
                     event_discriminator: str, registry: ResearchKeyRegistry | None = None,
                     normalized_groups: Mapping[str, object] | None = None) -> dict:
    """Single offline research snapshot, never an eligible production signal.

    Parent/children are independently fetched, source-tagged windows; core_5m
    is a 21-bar Stage-01 input without source identifiers. No unapproved
    numerical freshness, structure, or normalization threshold is inferred.
    The optional registry only provides *ephemeral* duplicate diagnostics.
    """
    if not isinstance(horizon, Horizon) or not isinstance(direction, Direction):
        raise ValueError("HORIZON_DIRECTION_ENUM_REQUIRED")
    if not isinstance(parent, CandleWindow) or not isinstance(market, MarketSnapshot):
        raise ValueError("TYPED_SOURCE_INPUT_REQUIRED")
    if not isinstance(tolerance, ReconciliationTolerance):
        raise ValueError("EXPLICIT_TOLERANCE_REQUIRED")
    if not isinstance(children, (tuple, list)) or not all(
        isinstance(x, CandleWindow) for x in children
    ):
        raise ValueError("CHILD_WINDOWS_REQUIRED")
    if not isinstance(core_5m, (tuple, list)) or not all(
        isinstance(x, Candle) for x in core_5m
    ):
        raise ValueError("CORE_CANDLES_REQUIRED")
    if registry is not None and not isinstance(registry, ResearchKeyRegistry):
        raise ValueError("EPHEMERAL_REGISTRY_REQUIRED")
    if normalized_groups is not None and not isinstance(normalized_groups, Mapping):
        raise ValueError("NORMALIZED_GROUP_MAPPING_REQUIRED")
    decision_at = utc(decision_at)
    identity = EventIdentity.research_key(
        symbol=symbol, horizon=horizon, direction=direction,
        setup_type="OFFLINE_QUALIFICATION_READINESS_UNAPPROVED",
        decision_candle_close_at=parent.close_at, rule_version=VERSION,
        event_discriminator=event_discriminator)

    reasons: list[str] = []
    parent_frame, child_frame, count = _FRAMES[horizon]
    evidence = None
    if parent.timeframe != parent_frame:
        reasons.append("PARENT_HORIZON_MISMATCH")
    else:
        evidence = reconcile(parent, children, decision_at, tolerance=tolerance)
        if evidence.status != "PASS":
            reasons.extend("MTF_" + code for code in evidence.reason_codes)

    core_errors = validate_candles(core_5m, decision_at)
    reasons.extend("CORE_" + code for code in core_errors)
    if len(core_5m) == 21:
        if core_5m[-1].close_at != parent.close_at:
            reasons.append("CORE_CLOSE_NOT_PARENT_ALIGNED")
        if core_5m[0].open_at < parent.open_at and horizon is Horizon.SWING:
            reasons.append("SWING_CORE_OUTSIDE_PARENT_WINDOW")
        if horizon is Horizon.INTRADAY and len(children) == count:
            for child, core in zip(children, core_5m[-count:]):
                if (child.open_at != core.open_at or child.close_at != core.close_at
                    or any(getattr(child, field) != getattr(core, field)
                           for field in _PRICES_AND_VOLUMES)):
                    reasons.append("INTRADAY_CORE_CHILD_SOURCE_MISMATCH")
                    break

    if market.symbol != symbol:
        reasons.append("MARKET_SYMBOL_MISMATCH")
    if market.observed_at > decision_at:
        reasons.append("MARKET_SNAPSHOT_FROM_FUTURE")
    elif market.observed_at < parent.close_at:
        reasons.append("MARKET_SNAPSHOT_PRE_PARENT_CLOSE")

    if normalized_groups is not None:
        known = {name for name, _ in V2_GROUPS[horizon]}
        if any(not isinstance(key, str) or key not in known
               for key in normalized_groups):
            reasons.append("UNKNOWN_NORMALIZED_GROUP")
        # Even declared group names carry no approved normalization formula.
        reasons.append("NORMALIZATION_INPUT_NOT_APPROVED")

    status = Lifecycle.INVALID.value if reasons else Lifecycle.RAW_OBSERVATION.value
    candidate = None
    event = None
    metrics = []
    dedup = None
    if not reasons:
        candidate = build_candidate(market, core_5m, decision_at)
        event = bind_research_candidate(
            candidate=candidate, identity=identity, reconciliation=evidence,
            candidate_id="03-OFFLINE-" + identity.detection_event_key)
        status = event.status.value
        if event.status is Lifecycle.RESEARCH_CANDIDATE:
            metrics = [metric.as_dict() for metric in describe(
                parent, children, direction=direction, decision_at=decision_at)]
            dedup = registry.observe(identity) if registry is not None else "UNTRACKED_EPHEMERAL"
        else:
            reasons.extend(event.reason_codes)

    if status == Lifecycle.RESEARCH_CANDIDATE.value:
        reasons.extend(("QUALIFICATION_FORMULAS_NOT_APPROVED",
                        "NORMALIZATION_FORMULAS_NOT_APPROVED",
                        "FRESHNESS_POLICY_NOT_APPROVED",
                        "CLOCK_AUTHORITY_NOT_VERIFIED",
                        "DURABLE_SIGNAL_ID_NOT_ASSIGNED"))
    reasons = list(dict.fromkeys(reasons))
    return {
        "version": VERSION, "raw_state": Lifecycle.RAW_OBSERVATION.value,
        "status": status, "qualification_status": "NOT_EVALUATED",
        "provisional_qualified_signal": None,
        "reason_codes": reasons,
        "identity": identity.as_dict(), "dedup_status": dedup,
        "reconciliation": evidence.as_dict() if evidence is not None else None,
        "candidate": candidate.as_dict() if candidate is not None else None,
        "research_event": event.as_dict() if event is not None else None,
        "research_metrics": {direction.value: metrics} if metrics else {},
        "score_status": "SCORE_UNAVAILABLE", "score": None,
        "stage03c_dependency": "UNMERGED_NO_SCORE_INPUT_INTEGRATION",
        "source_publication_time": None, "clock_uncertainty_ms": None,
        "signal_id": None, "publishable": False, "delivery_authorized": False,
        "trade_plan_status": "RESEARCH_ONLY",
        "durable_dedup_authority": False,
    }
