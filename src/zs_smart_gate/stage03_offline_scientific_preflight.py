"""Bounded offline Stage03 G0 *scientific* preflight; never PIT authority.

Reuses accepted Stage01/03A/03B1/03C qualification readiness. Checks context
provenance and optional pivot availability the existing candidate-only path
cannot inspect. A synthetic fixture is NEVER proof of independent source time
or a license to qualify, score, publish, persist, or deliver a signal.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, Sequence

from .core import Candle, MarketSnapshot, utc
from .mtf_contracts import CandleWindow, ReconciliationTolerance, available_closed_context
from .stage03a_contracts import Direction, Horizon, ResearchKeyRegistry, SwingPivot
from .stage03_qualification_readiness import assess_readiness

VERSION = "03_G0_SCIENTIFIC_PREFLIGHT_OFFLINE_V1"
_CONTEXT = {
    Horizon.INTRADAY: ("1h", "4h"),
    Horizon.SWING: ("1d", "1w"),
}


def scientific_g0_preflight(*, symbol: str, horizon: Horizon, direction: Direction,
                            parent: CandleWindow, children: Sequence[CandleWindow],
                            core_5m: Sequence[Candle], market: MarketSnapshot,
                            decision_at: datetime, tolerance: ReconciliationTolerance,
                            event_discriminator: str,
                            context_windows: Mapping[str, Sequence[CandleWindow]] | None = None,
                            pivots: Sequence[SwingPivot] = (),
                            registry: ResearchKeyRegistry | None = None,
                            normalized_groups: Mapping[str, object] | None = None) -> dict:
    """Read-only feasibility audit with explicit scientific UNKNOWN.

    Parent/child/core/candidate logic stays in accepted assess_readiness.
    Contexts are checked against the parent source, not silently chosen from
    mixed feeds. A previous known closed context may be used when a newer
    bar is still open/late; the newer bar is *never* read as known.
    Pivots remain unverified placeholders, not BOS/CHoCH evidence.
    """
    decision_at = utc(decision_at)
    row = assess_readiness(
        symbol=symbol, horizon=horizon, direction=direction, parent=parent,
        children=children, core_5m=core_5m, market=market,
        decision_at=decision_at, tolerance=tolerance,
        event_discriminator=event_discriminator, registry=registry,
        normalized_groups=normalized_groups,
    )
    if (row["qualification_status"] != "NOT_EVALUATED"
            or row["score_status"] != "SCORE_UNAVAILABLE"
            or row["score"] is not None or row["signal_id"] is not None
            or row["publishable"] or row["delivery_authorized"]):
        raise ValueError("G0_BASELINE_DELIVERY_OR_SCORE_VIOLATION")

    if context_windows is None:
        context_windows = {}
    if not isinstance(context_windows, Mapping):
        raise ValueError("CONTEXT_WINDOWS_MAPPING_REQUIRED")
    if not isinstance(pivots, (tuple, list)) or not all(
        isinstance(pivot, SwingPivot) for pivot in pivots
    ):
        raise ValueError("TYPED_PIVOTS_REQUIRED")

    reasons = []
    required = _CONTEXT[horizon]
    unexpected = set(context_windows) - set(required)
    if unexpected:
        reasons.append("UNEXPECTED_CONTEXT_FRAME")
    inspected = {}
    for frame in required:
        windows = context_windows.get(frame, ())
        if not isinstance(windows, (tuple, list)) or not all(
            isinstance(bar, CandleWindow) for bar in windows
        ):
            raise ValueError("TYPED_CONTEXT_WINDOWS_REQUIRED")
        detail = {"frame": frame, "source_id": None, "close_at": None,
                  "available_at": None, "status": "UNAVAILABLE"}
        if not windows:
            reasons.append("MISSING_CONTEXT:" + frame)
        elif any(bar.timeframe != frame for bar in windows):
            reasons.append("CONTEXT_TIMEFRAME_MISMATCH:" + frame)
        elif any(bar.source_id != parent.source_id for bar in windows):
            # Refuse a mixed pool even when one row happens to fit.
            reasons.append("CONTEXT_SOURCE_MISMATCH:" + frame)
        else:
            selected = available_closed_context(
                windows, timeframe=frame, decision_at=decision_at)
            if selected is None:
                reasons.append("CONTEXT_NOT_CLOSED_OR_UNAVAILABLE:" + frame)
            else:
                detail.update({
                    "source_id": selected.source_id,
                    "close_at": selected.close_at.isoformat(),
                    "available_at": selected.available_at.isoformat(),
                    "status": "CLOSED_AVAILABLE_CONTRACT_ONLY",
                })
        inspected[frame] = detail

    pivot_reasons = []
    for pivot in pivots:
        if pivot.source_id != parent.source_id:
            pivot_reasons.append("PIVOT_SOURCE_MISMATCH")
        if not pivot.known_at(decision_at):
            pivot_reasons.append("PIVOT_FUTURE_AT_DECISION")
    reasons.extend(pivot_reasons)

    # Neither MarketSnapshot nor CandleWindow attests exchange publication time,
    # an independent UTC clock, or a bound on market/context staleness.
    # A local receipt timestamp is necessary, not sufficient, for scientific PIT.
    reasons.extend((
        "SOURCE_PUBLICATION_TIME_UNKNOWN",
        "INDEPENDENT_CLOCK_UNCERTAINTY_UNKNOWN",
        "MARKET_SOURCE_RECEIPT_UNVERIFIED",
        "FRESHNESS_POLICY_NOT_APPROVED",
        "NORMALIZATION_AND_QUALIFICATION_NOT_APPROVED",
        "OUTCOME_OVERLAP_INDEPENDENCE_UNVERIFIED",
    ))
    reasons = list(dict.fromkeys((*row["reason_codes"], *reasons)))
    valid_inputs = (
        row["status"] == "RESEARCH_CANDIDATE"
        and not unexpected and not pivot_reasons
        and all(item["status"] == "CLOSED_AVAILABLE_CONTRACT_ONLY"
                for item in inspected.values())
    )
    # This is a grouping DIMENSION for analysis, never a production key.
    # UP/DOWN and retries on one parent share the same group.
    parent_window_cluster = {
        "asset_id": row["identity"]["asset_id"],
        "horizon": horizon.value,
        "parent_open_at": parent.open_at.isoformat(),
        "parent_close_at": parent.close_at.isoformat(),
    }
    return {
        "version": VERSION,
        "code_input_status": ("SOFTWARE_CONTRACTS_VALID_ON_SYNTHETIC_INPUT"
                              if valid_inputs else "SOFTWARE_INPUTS_INVALID_OR_INCOMPLETE"),
        "scientific_g0": "NO_GO_PIT_UNVERIFIED",
        "qualification_status": "NOT_EVALUATED",
        "score_status": "SCORE_UNAVAILABLE", "score": None,
        "signal_id": None, "publishable": False, "delivery_authorized": False,
        "candidate_status": row["status"],
        "context": inspected,
        "pivot_count_descriptive_only": len(pivots),
        "structure_status": "UNVERIFIED_RESEARCH_CONTRACT",
        "source_publication_time": None,
        "clock_uncertainty_ms": None,
        "market_snapshot_observed_at": market.observed_at.isoformat(),
        "market_receipt_and_publication_verified": False,
        "freshness_policy": "UNAPPROVED",
        "parent_window_cluster": parent_window_cluster,
        "independence_status": "UNKNOWN_OUTCOME_OVERLAP_AND_COHORT",
        "dedup_status_ephemeral_only": row["dedup_status"],
        "reason_codes": reasons,
        "candidate_evidence": row,
    }
