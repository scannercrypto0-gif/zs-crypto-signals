"""Read-only Stage-03A/03C V2 *concept* compatibility audit.

A matched heading and weight are NOT a normalized feature, approval, or
permission to score. Ambiguous group scope is explicitly unmapped. No values
are translated; both accepted historical contract versions remain unchanged.
"""
from __future__ import annotations

from types import MappingProxyType

from .stage03a_contracts import Direction, Horizon, V2_GROUPS, unavailable_score
from .stage03c_score_contracts import VERSION as SCORE_03C_VERSION, WEIGHTS, score_v2

# (03C conceptual heading, equivalent *heading*?, explanation).
# Source: MASTER v1.16 "Scoring — V2 Initial Research Weights"; ambiguous
# "quality"/"path", continuity vs all volume, and generic higher context stay
# UNMAPPED until a scoped owner-approved semantic/normalization definition.
_CONCEPT_LINKS = MappingProxyType({
    Horizon.INTRADAY: MappingProxyType({
        "30M_STRONG_CLOSE": ("strong_close", True, "SAME_30M_CLOSE_CONCEPT"),
        "SIX_5M_INTERNAL_QUALITY": ("internal_path", False, "QUALITY_VS_PATH_SCOPE_UNRESOLVED"),
        "MOMENTUM_EARLY_TIMING": ("momentum_timing", True, "SAME_MOMENTUM_TIMING_CONCEPT"),
        "VOLUME_CONTINUITY": ("volume", False, "CONTINUITY_VS_RVOL_VOLUME_SCOPE_UNRESOLVED"),
        "MTF_NEARBY_STRUCTURE": ("mtf_structure", True, "SAME_NEARBY_MTF_CONCEPT"),
        "LIQUIDITY_QUALITY": ("liquidity", True, "SAME_LIQUIDITY_CONCEPT"),
    }),
    Horizon.SWING: MappingProxyType({
        "MARKET_STRUCTURE": ("market_structure", True, "SAME_MARKET_STRUCTURE_CONCEPT"),
        "FOUR_H_STRONG_CLOSE": ("strong_close", True, "SAME_4H_CLOSE_CONCEPT"),
        "FOUR_1H_INTERNAL_QUALITY": ("internal_path", False, "QUALITY_VS_PATH_SCOPE_UNRESOLVED"),
        "DAILY_WEEKLY_CONTEXT": ("higher_context", False, "DAILY_WEEKLY_VS_HIGHER_SCOPE_UNRESOLVED"),
        "MOMENTUM_VOLUME": ("momentum_volume", True, "SAME_MOMENTUM_VOLUME_CONCEPT"),
        "LIQUIDITY_QUALITY": ("liquidity", True, "SAME_LIQUIDITY_CONCEPT"),
    }),
})


def group_alignment(horizon: Horizon) -> tuple[dict, ...]:
    """Validate coverage and weights against both versions, fail on contract drift.

    Returned names are diagnostic only. No mapping of numerical inputs exists.
    A false "concept_equivalent" deliberately exposes a proposed heading,
    not an approved mapping.
    """
    if not isinstance(horizon, Horizon):
        raise ValueError("HORIZON_ENUM_REQUIRED")
    groups = V2_GROUPS[horizon]
    links = _CONCEPT_LINKS[horizon]
    weights = WEIGHTS[horizon.value]
    if len(groups) != 6 or sum(weight for _, weight in groups) != 100:
        raise ValueError("03A_GROUP_WEIGHT_CONTRACT_DRIFT")
    if set(links) != {name for name, _ in groups}:
        raise ValueError("03A_GROUP_CONTRACT_DRIFT")
    if set(weights) != {candidate for candidate, _, _ in links.values()}:
        raise ValueError("03C_GROUP_CONTRACT_DRIFT")
    if len(set(candidate for candidate, _, _ in links.values())) != 6:
        raise ValueError("AMBIGUOUS_CONCEPT_CORRESPONDENCE")
    rows = []
    for name, weight in groups:
        proposed, equivalent, reason = links[name]
        if type(weight) is not int or type(weights[proposed]) is not int or weights[proposed] != weight:
            raise ValueError("03A_03C_WEIGHT_CONTRACT_DRIFT")
        rows.append({
            "stage03a_group": name,
            "stage03c_concept": proposed,
            "mapped_03c_group": proposed if equivalent else None,
            "weight": weight,
            "status": ("MAPPED_CONCEPT_ONLY" if equivalent
                       else "UNMAPPED_OWNER_DECISION_REQUIRED"),
            "reason": reason,
            "normalization_status": "NOT_APPROVED",
        })
    return tuple(rows)


def unavailable_contract_packet(horizon: Horizon, direction: Direction) -> dict:
    """Use 03A's unavailable V2 and 03C's *empty* input only.

    Even a caller supplying complete unapproved normalized_groups elsewhere
    cannot obtain a numeric result through this integration. No 03C research
    event key, alternate signal ID, or qualifying transition is created.
    """
    if not isinstance(direction, Direction):
        raise ValueError("DIRECTION_ENUM_REQUIRED")
    links = group_alignment(horizon)
    a = unavailable_score(horizon, direction)
    c = score_v2(horizon.value, {})  # Contract-only: NO raw/descriptive inputs.
    if (a.status != "SCORE_UNAVAILABLE" or a.total is not None
            or c.status != "SCORE_UNAVAILABLE" or c.score is not None
            or c.contributions or c.as_dict()["publishable"]
            or len(c.missing_reasons) != len(links)):
        raise ValueError("UNAVAILABLE_SCORE_CONTRACT_MISMATCH")
    missing = (
        *a.missing_reasons,
        *(reason for reason in c.missing_reasons),
        *(("UNMAPPED_CONCEPT:" + row["stage03a_group"])
          for row in links if row["mapped_03c_group"] is None),
        "NORMALIZATION_PROVENANCE_NOT_APPROVED",
    )
    return {
        "status": c.status,
        "score": None,
        "stage03a_version": a.score_version,
        "stage03c_version": SCORE_03C_VERSION,
        "direction": direction.value,
        "horizon": horizon.value,
        "alignment": [dict(row) for row in links],
        "missing_reasons": list(dict.fromkeys(missing)),
        "qualification_status": "NOT_EVALUATED",
        "provenance_policy": "UNAPPROVED",
        "publishable": False,
    }
