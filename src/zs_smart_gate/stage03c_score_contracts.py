"""Stage 03C research-only V2 score contract.

This module consumes normalized feature values; it does not invent feature
formulas, qualify signals, create production Signal IDs, or enable delivery.
A numeric score is emitted only when every preregistered group is present.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import hashlib
import json
import re
from types import MappingProxyType
from typing import Mapping

VERSION = "SMART_GATE_V2_SCORE_CONTRACT_0.2"
# Contributions remain exact Decimal products. Only the final displayed score
# is rounded, once, to 0.01 using ROUND_HALF_EVEN. This is part of VERSION.
SCORE_QUANTUM = Decimal("0.01")
SCORE_ROUNDING = ROUND_HALF_EVEN
_CANONICAL_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)

# Both levels are read-only so a caller cannot mutate the contract at runtime.
WEIGHTS: Mapping[str, Mapping[str, int]] = MappingProxyType({
    "INTRADAY": MappingProxyType({
        "strong_close": 20,
        "internal_path": 20,
        "momentum_timing": 20,
        "volume": 20,
        "mtf_structure": 15,
        "liquidity": 5,
    }),
    "SWING": MappingProxyType({
        "market_structure": 35,
        "strong_close": 15,
        "internal_path": 15,
        "higher_context": 15,
        "momentum_volume": 15,
        "liquidity": 5,
    }),
})


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


def _canonical_utc_timestamp(value: str) -> str:
    """Parse an ISO-8601 timestamp with timezone and normalize it to UTC Z."""
    if not isinstance(value, str) or not _CANONICAL_TIMESTAMP_PATTERN.fullmatch(value):
        raise ValueError("INVALID_DECISION_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as exc:
        raise ValueError("INVALID_DECISION_TIMESTAMP") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("DECISION_TIMESTAMP_TIMEZONE_REQUIRED")
    utc_value = parsed.astimezone(timezone.utc)
    timespec = "microseconds" if utc_value.microsecond else "seconds"
    return utc_value.isoformat(timespec=timespec).replace("+00:00", "Z")


@dataclass(frozen=True)
class ScoreResult:
    status: str
    horizon: str
    score: str | None
    contributions: Mapping[str, str]
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

    Contributions are exact Decimal products (weight × normalized value).
    Only the final score is rounded to two decimal places with ROUND_HALF_EVEN.
    A missing group yields SCORE_UNAVAILABLE; extra groups are rejected.
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

    exact_contributions = {
        key: Decimal(weight) * values[key]
        for key, weight in weights.items()
    }
    exact_total = sum(exact_contributions.values(), Decimal("0"))
    displayed_total = exact_total.quantize(SCORE_QUANTUM, rounding=SCORE_ROUNDING)
    return ScoreResult(
        "SCORED_RESEARCH_ONLY",
        horizon,
        str(displayed_total),
        MappingProxyType({key: format(value.normalize(), "f") for key, value in exact_contributions.items()}),
        (),
    )


def detection_event_key(*, rule_version: str, market: str, symbol: str,
                        direction: str, horizon: str, setup_type: str,
                        decision_close_utc: str, discriminator: str = "") -> str:
    """Stable research event key; timezone offsets are normalized to UTC."""
    parts = (rule_version, market, symbol, direction, horizon, setup_type,
             _canonical_utc_timestamp(decision_close_utc), discriminator)
    if any(not isinstance(part, str) or not part.strip() for part in parts[:6]):
        raise ValueError("EVENT_IDENTITY_FIELD_REQUIRED")
    if not isinstance(discriminator, str):
        raise ValueError("INVALID_EVENT_DISCRIMINATOR")
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
