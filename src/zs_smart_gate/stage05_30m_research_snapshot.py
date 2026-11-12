"""05C read-only adapter for verified R2 30m *research* rows.

This adapter never supplies an approved qualification, signal, score,
Telegram delivery authorization, or evidence of real market source trust.
"""
from __future__ import annotations

import re

from .stage03_r1_closed_parent import VERSION as R1_VERSION
from .stage03_r2_raw_features import VERSION as R2_VERSION
from .stage05_contracts import ContractError, canonical, digest, parse_utc

SCHEMA = "zs.stage05c.readonly-30m-research.v1"
FEATURE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_]{0,90}\Z")
ALLOWED = frozenset(("PRESENT", "UNKNOWN", "NOT_IMPLEMENTED", "INSUFFICIENT_HISTORY"))


def snapshot_from_r2(row: dict) -> dict:
    """Prepare a point-in-time 05C display snapshot, no fake scientific verdict."""
    if not isinstance(row, dict) or row.get("schema") != R1_VERSION:
        raise ContractError("INTERACTIVE30_R1_SCHEMA_REQUIRED")
    if (row.get("raw_feature_schema") != R2_VERSION
            or row.get("source_scope") != "SYNTHETIC_TEST_ONLY"
            or row.get("evaluation_status") != "POLICY_HOLD"
            or row.get("raw_30m_evaluation_eligible") is not True
            or row.get("qualification_state") != "UNKNOWN"
            or row.get("publishable") is not False
            or row.get("signal_id") is not None
            or row.get("score") is not None):
        raise ContractError("INTERACTIVE30_RESEARCH_ONLY_REQUIRED")
    identity = row.get("identity")
    if not isinstance(identity, dict) or identity.get("event_id") != row.get("event_id"):
        raise ContractError("INTERACTIVE30_IDENTITY_INVALID")
    symbol = identity.get("symbol")
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9]{3,20}USDT", symbol):
        raise ContractError("INTERACTIVE30_SYMBOL_INVALID")
    closed = parse_utc(identity.get("parent_close_at"), "PARENT_CLOSE")
    decision = parse_utc(row.get("decision_at"), "DECISION_AT")
    if closed > decision or closed.second or closed.minute % 30:
        raise ContractError("INTERACTIVE30_PARENT_WINDOW_INVALID")
    if not isinstance(row.get("source_manifest_sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", row["source_manifest_sha256"]):
        raise ContractError("INTERACTIVE30_SOURCE_SHA_INVALID")
    features = row.get("raw_features")
    if not isinstance(features, dict) or not features:
        raise ContractError("INTERACTIVE30_FEATURES_REQUIRED")
    expected = digest(canonical({
        "feature_version": R2_VERSION, "evaluation_version": R1_VERSION,
        "event_id": row["event_id"], "input_sha256": row["input_sha256"],
        "features": features,
    }))
    if row.get("raw_features_sha256") != expected:
        raise ContractError("INTERACTIVE30_FEATURE_SHA_INVALID")
    observations = []
    for name, feature in sorted(features.items()):
        if not isinstance(name, str) or not FEATURE_NAME.fullmatch(name):
            raise ContractError("INTERACTIVE30_FEATURE_NAME_INVALID")
        if not isinstance(feature, dict):
            raise ContractError("INTERACTIVE30_FEATURE_INVALID")
        status = feature.get("availability")
        value = feature.get("raw_value")
        if (status not in ALLOWED or feature.get("gate_result") != "NOT_EVALUATED"
                or not isinstance(feature.get("reason_codes"), list)
                or not feature["reason_codes"]):
            raise ContractError("INTERACTIVE30_FEATURE_POLICY_INVALID")
        if status == "PRESENT":
            if value is None or feature.get("as_of") is None:
                raise ContractError("INTERACTIVE30_PRESENT_VALUE_REQUIRED")
            if parse_utc(feature["as_of"]) > decision:
                raise ContractError("INTERACTIVE30_FEATURE_FUTURE")
        elif value is not None:
            raise ContractError("INTERACTIVE30_ABSENT_HAS_VALUE")
        elif feature.get("as_of") is not None and parse_utc(feature["as_of"]) > decision:
            raise ContractError("INTERACTIVE30_ABSENT_FUTURE")
        observations.append({
            "indicator_id": "R2_RAW_" + name.upper(),
            "raw_value": value, "value": value,
            "availability": status, "evaluation": "UNKNOWN", "threshold": None,
            "unit": feature.get("unit"), "timeframe": feature.get("timeframe"),
            "source": "SYNTHETIC_TEST_ONLY", "as_of": feature.get("as_of"),
            "version": R2_VERSION, "reason_codes": feature["reason_codes"],
        })
    return {
        "schema": SCHEMA, "symbol": symbol,
        "as_of": row["decision_at"], "closed_at": identity["parent_close_at"],
        "source_frame": "30m", "source_scope": "SYNTHETIC_TEST_ONLY",
        "source_sha256": row["source_manifest_sha256"],
        "decision_sha256": digest(canonical(row)),
        "indicators": observations, "score": None,
        "decision": "RESEARCH_30M_POLICY_HOLD",
        "reason_codes": ["NO_OWNER_APPROVED_NUMERIC_QUALIFICATION_POLICY",
                         "NOT_A_PRODUCTION_SIGNAL"],
        "signal_id": None,
    }
