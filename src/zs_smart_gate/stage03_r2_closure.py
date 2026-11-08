"""Stage03 C1-C4: fail-closed component/rejection accounting for offline research.

This is a diagnostic adapter over ALREADY implemented Stage03 closed-receipt
and 03A/R2 contracts. It does not define N03 FULL_IMPULSE, settle semantic
decisions, approve a numeric normalizer, or qualify/publish a signal.
"""
from __future__ import annotations

import hashlib
import json
from typing import Mapping

from .stage03a_contracts import Horizon, V2_GROUPS
from .stage03_contract_alignment import group_alignment
from .stage03_r2_offline import Unavailable
from .stage03_r2_receipt_bundle import stage03_r2_from_closed_receipts

SCHEMA = "ZS03_C1C4_RESEARCH_COMPONENT_ACCOUNTING_V1"

_N_GROUPS = {
    Horizon.INTRADAY: (
        ("N01", "30M_STRONG_CLOSE"),
        ("N02", "SIX_5M_INTERNAL_QUALITY"),
        ("N03", "MOMENTUM_EARLY_TIMING"),
        ("N04", "VOLUME_CONTINUITY"),
        ("N05", "MTF_NEARBY_STRUCTURE"),
        ("N06", "LIQUIDITY_QUALITY"),
    ),
    Horizon.SWING: (
        ("N07", "MARKET_STRUCTURE"),
        ("N08", "FOUR_H_STRONG_CLOSE"),
        ("N09", "FOUR_1H_INTERNAL_QUALITY"),
        ("N10", "DAILY_WEEKLY_CONTEXT"),
        ("N11", "MOMENTUM_VOLUME"),
        ("N12", "LIQUIDITY_QUALITY"),
    ),
}

# These four are the STILL UNAPPROVED 03A/03C conceptual links.
# Holding them here is a record of prior decisions, NOT a new science gate.
_SEMANTIC_IDS = {
    (Horizon.INTRADAY, "SIX_5M_INTERNAL_QUALITY"): "SEM-I-01",
    (Horizon.INTRADAY, "VOLUME_CONTINUITY"): "SEM-I-02",
    (Horizon.SWING, "FOUR_1H_INTERNAL_QUALITY"): "SEM-S-01",
    (Horizon.SWING, "DAILY_WEEKLY_CONTEXT"): "SEM-S-02",
}


def _semantics() -> list[dict]:
    decisions = []
    for horizon in (Horizon.INTRADAY, Horizon.SWING):
        for row in group_alignment(horizon):
            key = (horizon, row["stage03a_group"])
            if key not in _SEMANTIC_IDS:
                continue
            decisions.append({
                "decision_id": _SEMANTIC_IDS[key],
                "horizon": horizon.value,
                "stage03a_group": key[1],
                "proposed_03c_concept": row["stage03c_concept"],
                "status": row["status"],
                "reason": row["reason"],
                "approved_mapping": row["mapped_03c_group"],
            })
    if len(decisions) != 4:
        raise RuntimeError("SEMANTIC_DECISION_ACCOUNTING_INCOMPLETE")
    return decisions


def _fingerprint(packet: dict) -> dict:
    blob = json.dumps(
        packet, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("ascii")
    packet["packet_sha256"] = hashlib.sha256(blob).hexdigest()
    return packet


def stage03_c1c4_research_from_closed_receipts(
    record: Mapping[str, object],
) -> dict:
    """One call: closed synthetic receipts -> research OR explicit rejection.

    Components with a computed value remain unqualified research candidates.
    Missing values retain the original per-group failure reason. Missing input
    produces a deterministic rejected envelope, not a fabricated candidate.
    """
    base = {
        "schema": SCHEMA,
        "stage03_closure": "OPEN_PM_OWNER_DECISION_REQUIRED",
        "source_scope": "SYNTHETIC_ONLY_NOT_REAL_PIT",
        "qualification_status": "NOT_EVALUATED",
        "score_status": "SCORE_UNAVAILABLE",
        "score": None,
        "signal_id": None,
        "publishable": False,
        "delivery_authorized": False,
        "market_requests": 0,
        "external_sends": 0,
        "semantic_decisions": _semantics(),
        "full_impulse_definition_status": "UNAPPROVED",
        "full_impulse_decision": "DECISION_REQUIRED",
    }
    try:
        research = stage03_r2_from_closed_receipts(record)
    except Unavailable as exc:
        base.update(
            status="REJECTED",
            research=None,
            research_status=None,
            rejected_input=True,
            rejection_reasons=[str(exc)],
            component_rows=[],
            unavailable_component_ids=[],
        )
        return _fingerprint(base)

    horizon = Horizon(research["r2"]["horizon"])
    normalizers = research["r2"]["normalizers"]
    missing = research["r2"]["missing_reasons"]
    research_rejected = research["status"] != "RESEARCH_CANDIDATE"
    rows = []
    missing_ids = []
    for number, name in _N_GROUPS[horizon]:
        value = normalizers.get(name)
        reason = missing.get(name)
        if value is None:
            missing_ids.append(number)
            status = "UNAVAILABLE"
            reasons = [reason or "NORMALIZER_VALUE_MISSING"]
        elif research_rejected:
            status = "REJECTED_INPUT_NO_COMPONENT_ACCEPTANCE"
            reasons = ["RESEARCH_INPUT_REJECTED"]
        elif (horizon, name) in _SEMANTIC_IDS:
            status = "SEMANTIC_DECISION_REQUIRED"
            reasons = [_SEMANTIC_IDS[horizon, name]]
        else:
            status = "RESEARCH_VALUE_PRESENT_NOT_ACCEPTED"
            reasons = []
        # Even available N03 would NOT prove an approved full-impulse event.
        if number == "N03" and value is not None and not research_rejected:
            status = "FULL_IMPULSE_DECISION_REQUIRED"
            reasons = list(dict.fromkeys(
                [*reasons, "FULL_IMPULSE_DEFINITION_UNAPPROVED"]
            ))
        rows.append({
            "indicator": number,
            "group": name,
            "horizon": horizon.value,
            "value": value if not research_rejected else None,
            "status": status,
            "reason_codes": reasons,
            "production_contribution": None,
        })
    if tuple(row["group"] for row in rows) != tuple(
        name for name, _ in V2_GROUPS[horizon]
    ):
        raise RuntimeError("C1C4_V2_GROUP_ORDER_DRIFT")

    reject_reasons = list(research["source_match_reasons"])
    if research_rejected and not reject_reasons:
        reject_reasons.append("STAGE03_RESEARCH_READINESS_REJECTED")
    base.update(
        status="REJECTED" if research_rejected else "RESEARCH_CANDIDATE",
        research_status=research["status"],
        research=research,
        rejected_input=research_rejected,
        rejection_reasons=reject_reasons,
        component_rows=rows,
        unavailable_component_ids=missing_ids,
        research_readiness_reasons=list(research["readiness_reason_codes"]),
        research_packet_sha256=research["packet_sha256"],
    )
    return _fingerprint(base)
