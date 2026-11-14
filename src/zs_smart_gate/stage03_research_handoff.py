"""Stage03→Stage04 research-only handoff. Never an approved Stage05 event.

This adapter joins the already-accepted offline R1/R2 feature receipt to an
additive, content-addressed research payload without changing legacy schemas.
It has no transport, clock, token, approval registry, or notification capability.
"""
from __future__ import annotations

from .stage03_r1_closed_parent import VERSION as R1_VERSION
from .stage03_r2_raw_features import VERSION as R2_VERSION
from .stage05_contracts import ContractError, SHA, canonical, digest, parse_utc

VERSION = "zs.stage03.research-custody-handoff.v1"
REQUIRED = frozenset((
    "schema", "source_scope", "event_id", "candidate_id", "parent_close_at",
    "input_sha256", "source_manifest_sha256", "raw_feature_schema",
    "raw_features_sha256", "raw_features", "evaluation_status",
    "qualification_state", "signal_id", "delivery_authorized", "payload_sha256",
))


def _feature_digest(row: dict) -> str:
    return digest(canonical({
        "feature_version": R2_VERSION, "evaluation_version": R1_VERSION,
        "event_id": row["event_id"], "input_sha256": row["input_sha256"],
        "features": row["raw_features"],
    }))


def make_handoff(row: dict) -> dict:
    """Convert a synthetic R2 research row; fail closed."""
    return _make_handoff(row, "SYNTHETIC_TEST_ONLY")


def make_recorded_spot_handoff(raw: bytes, expected_sha256: str) -> dict:
    """Verify the pinned public capture before admitting its research result."""
    from .stage03_30m_universe import replay_spot_capture

    return _make_handoff(replay_spot_capture(raw, expected_sha256)["row"], "RECORDED_PUBLIC_SPOT")


def _make_handoff(row: dict, scope: str) -> dict:
    if not isinstance(row, dict) or row.get("schema") != R1_VERSION:
        raise ContractError("STAGE03_HANDOFF_R1_SCHEMA_REQUIRED")
    if (row.get("source_scope") != scope
            or row.get("raw_feature_schema") != R2_VERSION
            or row.get("qualification_state") != "UNKNOWN"
            or row.get("signal_id") is not None
            or row.get("publishable") is not False
            or row.get("stage05_event_v1_compatible") is not False
            or row.get("raw_features_status") != "RESEARCH_MEASURED"
            or row.get("evaluation_status") != "POLICY_HOLD"
            or row.get("raw_30m_evaluation_eligible") is not True):
        raise ContractError("STAGE03_HANDOFF_NOT_ADMITTED_RESEARCH")
    if (not isinstance(row.get("identity"), dict)
            or row["identity"].get("event_id") != row.get("event_id")
            or row["identity"].get("candidate_id") != row.get("candidate_id")
            or row["identity"].get("signal_id") is not None
            or row["identity"].get("parent_close_at") is None):
        raise ContractError("STAGE03_HANDOFF_IDENTITY_MISMATCH")
    try:
        parse_utc(row["identity"]["parent_close_at"])
        for field in ("input_sha256", "source_manifest_sha256", "raw_features_sha256"):
            if not isinstance(row[field], str) or not SHA.fullmatch(row[field]):
                raise ContractError("STAGE03_HANDOFF_SHA_INVALID")
        if not isinstance(row.get("raw_features"), dict) or not row["raw_features"]:
            raise ContractError("STAGE03_HANDOFF_FEATURES_REQUIRED")
        if row["raw_features_sha256"] != _feature_digest(row):
            raise ContractError("STAGE03_HANDOFF_FEATURE_HASH_MISMATCH")
        for feature in row["raw_features"].values():
            if not isinstance(feature, dict) or feature.get("gate_result") != "NOT_EVALUATED":
                raise ContractError("STAGE03_HANDOFF_APPROVED_GATE_FORBIDDEN")
            if feature.get("availability") not in (
                    "PRESENT", "INSUFFICIENT_HISTORY", "UNKNOWN", "NOT_IMPLEMENTED"):
                raise ContractError("STAGE03_HANDOFF_FEATURE_STATE_INVALID")
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError("STAGE03_HANDOFF_INVALID_INPUT") from None
    out = {
        "schema": VERSION, "source_scope": scope,
        "event_id": row["event_id"], "candidate_id": row["candidate_id"],
        "parent_close_at": row["identity"]["parent_close_at"],
        "input_sha256": row["input_sha256"],
        "source_manifest_sha256": row["source_manifest_sha256"],
        "raw_feature_schema": R2_VERSION,
        "raw_features_sha256": row["raw_features_sha256"],
        "raw_features": row["raw_features"],
        "evaluation_status": "POLICY_HOLD",
        "qualification_state": "UNKNOWN",
        "signal_id": None, "delivery_authorized": False,
    }
    out["payload_sha256"] = digest(canonical(out))
    return out


def verify_handoff(value: dict) -> bool:
    """Integrity of a research envelope; NOT truth/authority of source market."""
    if not isinstance(value, dict) or set(value) != REQUIRED:
        raise ContractError("STAGE03_HANDOFF_FIELDS_INVALID")
    if (value.get("schema") != VERSION
            or value.get("source_scope") not in ("SYNTHETIC_TEST_ONLY", "RECORDED_PUBLIC_SPOT")
            or value.get("evaluation_status") != "POLICY_HOLD"
            or value.get("qualification_state") != "UNKNOWN"
            or value.get("signal_id") is not None
            or value.get("delivery_authorized") is not False
            or value.get("raw_feature_schema") != R2_VERSION):
        raise ContractError("STAGE03_HANDOFF_AUTHORITY_INVALID")
    if any(not isinstance(value.get(k), str) or not SHA.fullmatch(value[k])
           for k in ("input_sha256", "source_manifest_sha256",
                     "raw_features_sha256", "payload_sha256")):
        raise ContractError("STAGE03_HANDOFF_HASH_INVALID")
    parse_utc(value["parent_close_at"])
    if (not isinstance(value["raw_features"], dict) or not value["raw_features"]
            or any(not isinstance(row, dict) or row.get("gate_result") != "NOT_EVALUATED"
                   for row in value["raw_features"].values())):
        raise ContractError("STAGE03_HANDOFF_FEATURES_INVALID")
    raw = {k: v for k, v in value.items() if k != "payload_sha256"}
    if digest(canonical(raw)) != value["payload_sha256"]:
        raise ContractError("STAGE03_HANDOFF_RECORD_HASH_MISMATCH")
    return True
