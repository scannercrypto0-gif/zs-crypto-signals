"""Stage 03C research-only V2 score contract.

This module deliberately consumes normalized feature values; it does not
invent feature formulas, qualify signals, create Signal IDs, or enable delivery.
A numeric score is emitted only when every preregistered group is present.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Mapping

VERSION = "SMART_GATE_V2_SCORE_CONTRACT_0.1"
WEIGHTS: dict[str, dict[str, int]] = {
    "INTRADAY": {
        "strong_close": 20,
        "internal_path": 20,
        "momentum_timing": 20,
        "volume": 20,
        "mtf_structure": 15,
        "liquidity": 5,
    },
    "SWING": {
        "market_structure": 35,
        "strong_close": 15,
        "internal_path": 15,
        "higher_context": 15,
        "momentum_volume": 15,
        "liquidity": 5,
    },
}


def _number(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("BOOLEAN_FEATURE_NOT_ALLOWED")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("FEATURE_VALUE_NOT_NUMERIC") from exc
    if not number.is_finite():
        raise ValueError("FEATURE_VALUE_NOT_FINITE")
    return number


@dataclass(frozen=True)
class ScoreResult:
    status: str
    horizon: str
    score: str | None
    contributions: dict[str, str]
    missing_reasons: tuple[str, ...]
    contract_version: str = VERSION
    score_kind: str = "RESEARCH_DISCOVERY_STRENGTH_NOT_PROBABILITY"

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "horizon": self.horizon,
            "score": self.score,
            "contributions": dict(self.contributions),
            "missing_reasons": list(self.missing_reasons),
            "contract_version": self.contract_version,
            "score_kind": self.score_kind,
            "qualification_status": "NOT_EVALUATED",
            "publishable": False,
        }


def score_v2(horizon: str, normalized_groups: Mapping[str, object]) -> ScoreResult:
    """Score complete normalized groups; never redistribute missing weight.

    Every supplied normalized group must be within [0, 1]. A missing group
    yields SCORE_UNAVAILABLE with no numeric score or partial contribution.
    Extra groups are rejected to prevent silent contract drift.
    """
    if not isinstance(horizon, str) or horizon not in WEIGHTS:
        raise ValueError("UNSUPPORTED_HORIZON")
    if not isinstance(normalized_groups, Mapping):
        raise ValueError("FEATURE_GROUPS_MAPPING_REQUIRED")

    weights = WEIGHTS[horizon]
    expected = set(weights)
    supplied = set(normalized_groups)
    extra = sorted(supplied - expected)
    if extra:
        raise ValueError("UNEXPECTED_FEATURE_GROUPS:" + ",".join(extra))

    missing = tuple("MISSING_GROUP:" + key for key in sorted(expected - supplied))
    if missing:
        return ScoreResult("SCORE_UNAVAILABLE", horizon, None, {}, missing)

    values: dict[str, Decimal] = {}
    for key in weights:
        value = _number(normalized_groups[key])
        if value < 0 or value > 1:
            raise ValueError("FEATURE_OUT_OF_RANGE:" + key)
        values[key] = value

    contributions = {
        key: (Decimal(weight) * values[key]).quantize(Decimal("0.01"))
        for key, weight in weights.items()
    }
    total = sum(contributions.values(), Decimal("0"))
    # All components are exact decimal arithmetic and all weights sum to 100.
    return ScoreResult(
        "SCORED_RESEARCH_ONLY", horizon, str(total.quantize(Decimal("0.01"))),
        {key: str(value) for key, value in contributions.items()}, (),
    )


def detection_event_key(*, rule_version: str, market: str, symbol: str,
                        direction: str, horizon: str, setup_type: str,
                        decision_close_utc: str, discriminator: str = "") -> str:
    """Stable research event key; callers must supply a canonical UTC timestamp."""
    parts = (rule_version, market, symbol, direction, horizon, setup_type,
             decision_close_utc, discriminator)
    if any(not isinstance(part, str) or not part.strip() for part in parts[:7]):
        raise ValueError("EVENT_IDENTITY_FIELD_REQUIRED")
    if direction not in {"UP", "DOWN"}:
        raise ValueError("INVALID_DIRECTION")
    if horizon not in WEIGHTS:
        raise ValueError("UNSUPPORTED_HORIZON")
    canonical = json.dumps(parts, ensure_ascii=True, separators=(",", ":"))
    return "evt_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def assert_delivery_blocked(score: ScoreResult) -> None:
    """Guardrail for this stage: a score result is never a production signal."""
    if score.status not in {"SCORE_UNAVAILABLE", "SCORED_RESEARCH_ONLY"}:
        raise ValueError("UNKNOWN_SCORE_STATUS")
    if score.score_kind != "RESEARCH_DISCOVERY_STRENGTH_NOT_PROBABILITY":
        raise ValueError("SCORE_SEMANTICS_MISMATCH")
    # Intentionally always raises: delivery belongs to a later accepted phase.
    raise PermissionError("PHASE_03C_RESEARCH_ONLY_DELIVERY_NOT_AUTHORIZED")
