"""Stage-04 evidence packet over the ACCEPTED claim/receipt GitHub journal.

No network, filesystem or credentials on import. An injected journal is the only
writer; a distinct injected Contents transport independently re-reads records.
Application CAS/readback is not WORM or permission-enforced history protection.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Mapping

from .evidence_journal import (MAX_STUDY_BYTES, SingleStudyJournal,
                               canonical_bytes, sha256_hex, study_capacity)
from .github_evidence_backend import ContentsTransport, verify_snapshot

RECORD_SCHEMA = "zs-stage04-evidence-record-v1"
MANIFEST_SCHEMA = "zs-stage04-evidence-manifest-v1"
MAX_CONTENTS_BYTES = 900_000  # Stay below GitHub Contents' full-API 1 MiB boundary.
MAX_PACKET_RECORDS = 128
RECORD_KINDS = frozenset((
    "source_snapshot", "research_candidate", "scan_cycle",
    "decision_context", "experiment_manifest", "later_outcome",
))
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE = frozenset((
    "token", "access_token", "api_key", "authorization", "password",
    "private_key", "secret", "github_token",
))
UTC = timezone.utc


@dataclass(frozen=True)
class EvidenceResult:
    ok: bool
    status: str
    records_checked: int = 0
    manifest_sha256: str | None = None
    failed_event: str | None = None


def _id(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("INVALID_EVIDENCE_IDENTIFIER")
    return value


def _date(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("UTC_TIMESTAMP_REQUIRED")
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise ValueError
        return parsed.astimezone(UTC)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("UTC_TIMESTAMP_REQUIRED") from None


def _safe_json(value: object) -> None:
    def check(node: object):
        if isinstance(node, dict):
            for key, child in node.items():
                if not isinstance(key, str):
                    raise ValueError("NON_STRING_JSON_KEY")
                lowered = key.lower()
                if lowered in _SENSITIVE:
                    raise ValueError("SENSITIVE_FIELD_REJECTED")
                if (lowered in ("score", "signal_id", "source_publication_at",
                                "clock_uncertainty_ms")
                        and child is not None):
                    raise ValueError("UNVERIFIED_PRODUCTION_OR_PIT_VALUE")
                if (lowered in ("publishable", "delivery_authorized", "qualified_signal")
                        and child is not False and child is not None):
                    raise ValueError("UNVERIFIED_PRODUCTION_OR_PIT_VALUE")
                if lowered == "pit_status" and child != "PIT_UNVERIFIED":
                    raise ValueError("UNVERIFIED_PRODUCTION_OR_PIT_VALUE")
                if lowered == "score_status" and child != "SCORE_UNAVAILABLE":
                    raise ValueError("UNVERIFIED_PRODUCTION_OR_PIT_VALUE")
                check(child)
        elif isinstance(node, (tuple, list)):
            for child in node:
                check(child)
    check(value)
    try:
        json.dumps(value, allow_nan=False, ensure_ascii=False)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("NON_JSON_OR_NONFINITE_PAYLOAD") from None


def make_record(*, study_id: str, event_id: str, record_type: str,
                source_id: str, received_at: str, available_at: str,
                payload: dict, candidate_status: str = "NOT_EVALUATED") -> dict:
    """Only factual research states; NEVER a score, signal or trade instruction."""
    _id(study_id)
    if _id(event_id) == "manifest":
        raise ValueError("RESERVED_MANIFEST_EVENT")
    if record_type not in RECORD_KINDS:
        raise ValueError("UNKNOWN_EVIDENCE_KIND")
    if not isinstance(source_id, str) or not source_id.strip() or len(source_id) > 256:
        raise ValueError("SOURCE_ID_REQUIRED")
    if _date(received_at) > _date(available_at):
        raise ValueError("RECEIPT_AFTER_AVAILABILITY")
    if candidate_status not in (
        "NOT_EVALUATED", "RAW_OBSERVATION", "RESEARCH_CANDIDATE",
        "INVALID", "REJECTED",
    ):
        raise ValueError("PRODUCTION_OR_UNKNOWN_STATE_FORBIDDEN")
    if not isinstance(payload, dict):
        raise ValueError("RECORD_PAYLOAD_OBJECT_REQUIRED")
    _safe_json(payload)
    result = {
        "schema": RECORD_SCHEMA,
        "study_id": study_id, "event_id": event_id, "record_type": record_type,
        "source_id": source_id,
        "received_at": received_at, "available_at": available_at,
        "source_publication_at": None, "clock_uncertainty_ms": None,
        "pit_status": "PIT_UNVERIFIED",
        "qualification_status": "NOT_EVALUATED",
        "candidate_status": candidate_status,
        "score_status": "SCORE_UNAVAILABLE",
        "score": None, "signal_id": None, "publishable": False,
        "delivery_authorized": False,
        "payload": payload,
    }
    if len(canonical_bytes(result)) > MAX_CONTENTS_BYTES - 4096:
        raise ValueError("CONTENTS_RECORD_SIZE_LIMIT")
    return result


def _check_record(record: object, study_id: str, event_id: str) -> None:
    if not isinstance(record, dict) or record.get("schema") != RECORD_SCHEMA:
        raise ValueError("RECORD_SCHEMA_MISMATCH")
    if record.get("study_id") != study_id or record.get("event_id") != event_id:
        raise ValueError("RECORD_ID_MISMATCH")
    if set(record) != {
        "schema", "study_id", "event_id", "record_type", "source_id",
        "received_at", "available_at", "source_publication_at",
        "clock_uncertainty_ms", "pit_status", "qualification_status",
        "candidate_status", "score_status", "score", "signal_id",
        "publishable", "delivery_authorized", "payload",
    }:
        raise ValueError("UNEXPECTED_RECORD_FIELDS")
    if record.get("record_type") not in RECORD_KINDS:
        raise ValueError("RECORD_TYPE_MISMATCH")
    if not isinstance(record.get("source_id"), str) or not record["source_id"].strip():
        raise ValueError("RECORD_SOURCE_MISSING")
    if _date(record.get("received_at")) > _date(record.get("available_at")):
        raise ValueError("RECORD_TIME_INVALID")
    required = {
        "source_publication_at": None, "clock_uncertainty_ms": None,
        "pit_status": "PIT_UNVERIFIED",
        "qualification_status": "NOT_EVALUATED",
        "score_status": "SCORE_UNAVAILABLE", "score": None,
        "signal_id": None, "publishable": False, "delivery_authorized": False,
    }
    if any(record.get(k, object()) != v for k, v in required.items()):
        raise ValueError("UNAPPROVED_SCIENTIFIC_OR_PRODUCTION_STATE")
    if record.get("candidate_status") not in (
        "NOT_EVALUATED", "RAW_OBSERVATION", "RESEARCH_CANDIDATE",
        "INVALID", "REJECTED",
    ) or not isinstance(record.get("payload"), dict):
        raise ValueError("INVALID_RESEARCH_PAYLOAD")
    _safe_json(record)
    if len(canonical_bytes(record)) > MAX_CONTENTS_BYTES - 4096:
        raise ValueError("CONTENTS_RECORD_SIZE_LIMIT")


def prepare_manifest(study_id: str, records: Mapping[str, dict],
                     *, created_at: str) -> dict:
    """Freeze a SHA-256 inventory before ANY claim/receipt; review is not deletion."""
    study_id = _id(study_id)
    created = _date(created_at)
    if not isinstance(records, Mapping) or not 1 <= len(records) <= MAX_PACKET_RECORDS:
        raise ValueError("INVALID_PACKET_RECORD_COUNT")
    entries = []
    for event_id, record in sorted(records.items()):
        event_id = _id(event_id)
        _check_record(record, study_id, event_id)
        entries.append({
            "event_id": event_id,
            "record_type": record["record_type"],
            "sha256": sha256_hex(canonical_bytes(record)),
            "size_bytes": len(canonical_bytes(record)),
        })
    manifest = {
        "schema": MANIFEST_SCHEMA, "study_id": study_id,
        "created_at": created.isoformat(),
        "retention_review_at": (created + timedelta(days=30)).isoformat(),
        "retention_action": "REVIEW_ONLY_NO_AUTOMATIC_DELETE",
        "max_study_bytes": study_capacity(study_id),
        "evidence_branch_policy": "DEDICATED_NON_MAIN",
        "server_enforced_worm": False,
        "source_publication_status": "UNKNOWN",
        "independent_utc_status": "UNKNOWN",
        "pit_status": "PIT_UNVERIFIED",
        "score_status": "SCORE_UNAVAILABLE",
        "entries": entries,
    }
    if len(canonical_bytes(manifest)) > MAX_CONTENTS_BYTES - 4096:
        raise ValueError("MANIFEST_CONTENTS_SIZE_LIMIT")
    return manifest


def _validate_manifest(study_id: str, manifest: object) -> list[dict]:
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("INVALID_STAGE04_MANIFEST")
    if manifest.get("study_id") != study_id:
        raise ValueError("MANIFEST_STUDY_MISMATCH")
    if set(manifest) != {
        "schema", "study_id", "created_at", "retention_review_at",
        "retention_action", "max_study_bytes", "evidence_branch_policy",
        "server_enforced_worm", "source_publication_status",
        "independent_utc_status", "pit_status", "score_status", "entries",
    }:
        raise ValueError("UNEXPECTED_MANIFEST_FIELDS")
    _safe_json(manifest)
    at = _date(manifest.get("created_at"))
    if manifest.get("retention_review_at") != (at + timedelta(days=30)).isoformat():
        raise ValueError("MANIFEST_REVIEW_POLICY_INVALID")
    for key, value in {
        "retention_action": "REVIEW_ONLY_NO_AUTOMATIC_DELETE",
        "max_study_bytes": study_capacity(study_id),
        "evidence_branch_policy": "DEDICATED_NON_MAIN",
        "server_enforced_worm": False,
        "source_publication_status": "UNKNOWN",
        "independent_utc_status": "UNKNOWN",
        "pit_status": "PIT_UNVERIFIED", "score_status": "SCORE_UNAVAILABLE",
    }.items():
        if manifest.get(key, object()) != value:
            raise ValueError("MANIFEST_POLICY_MISMATCH")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_PACKET_RECORDS:
        raise ValueError("MANIFEST_ENTRIES_INVALID")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "event_id", "record_type", "sha256", "size_bytes"
        }:
            raise ValueError("MANIFEST_ENTRY_INVALID")
        event_id = _id(entry.get("event_id"))
        if event_id == "manifest" or event_id in seen:
            raise ValueError("DUPLICATE_MANIFEST_EVENT")
        seen.add(event_id)
        if (entry.get("record_type") not in RECORD_KINDS
                or not isinstance(entry.get("sha256"), str)
                or not _SHA.fullmatch(entry["sha256"])
                or type(entry.get("size_bytes")) is not int
                or entry["size_bytes"] < 1
                or entry["size_bytes"] > MAX_CONTENTS_BYTES):
            raise ValueError("MANIFEST_ENTRY_INVALID")
    if len(canonical_bytes(manifest)) > MAX_CONTENTS_BYTES - 4096:
        raise ValueError("MANIFEST_CONTENTS_SIZE_LIMIT")
    return entries


def persist_packet(journal: SingleStudyJournal, manifest: dict,
                   records: Mapping[str, dict]) -> EvidenceResult:
    """One shot only. Ambiguous write/readback yields UNKNOWN; NEVER retry blindly."""
    try:
        study_id = journal.study_id
        entries = _validate_manifest(study_id, manifest)
        if set(records) != {e["event_id"] for e in entries}:
            raise ValueError("MANIFEST_INVENTORY_MISMATCH")
        for entry in entries:
            record = records[entry["event_id"]]
            _check_record(record, study_id, entry["event_id"])
            raw = canonical_bytes(record)
            if len(raw) != entry["size_bytes"] or sha256_hex(raw) != entry["sha256"]:
                raise ValueError("MANIFEST_CHECKSUM_MISMATCH")
        all_payloads = [manifest, *(records[e["event_id"]] for e in entries)]
        # Include claim+receipt overhead conservatively; reserve_capacity enforces
        # true bytes. This is only an early refusal, not an accounting guarantee.
        if sum(len(canonical_bytes(x)) + 800 for x in all_payloads) > study_capacity(study_id):
            raise ValueError("STUDY_CAPACITY_PREFLIGHT")
        digest = sha256_hex(canonical_bytes(manifest))
    except (ValueError, TypeError, KeyError):
        return EvidenceResult(False, "REJECTED_INVALID_PACKET")
    completed = 0
    for event_id, payload in [("manifest", manifest), *[
        (e["event_id"], records[e["event_id"]]) for e in entries
    ]]:
        try:
            if not journal.claim_before_attempts(study_id, event_id):
                return EvidenceResult(False, "UNKNOWN_PARTIAL_OR_CONFLICT",
                                      completed, digest, event_id)
            checksum = sha256_hex(canonical_bytes(payload))
            if not journal.append_and_readback(event_id, payload, checksum):
                return EvidenceResult(False, "UNKNOWN_PARTIAL_OR_CONFLICT",
                                      completed, digest, event_id)
        except Exception:
            return EvidenceResult(False, "UNKNOWN_PARTIAL_OR_CONFLICT",
                                  completed, digest, event_id)
        completed += 1
    return EvidenceResult(True, "WRITE_READBACK_VERIFIED_APPLICATION_ONLY",
                          completed, digest)


def restore_from_remote(*, study_id: str, branch: str, transport: ContentsTransport,
                        expected_manifest_sha256: str) -> EvidenceResult:
    """Fresh network/clone-like re-fetch of index+all listed claims/receipts.

    Requires the independently pinned manifest digest from the write receipt.
    Without GitHub branch protection, a privileged writer can still rewrite
    history and data; this verifies only observed bytes, not WORM.
    """
    try:
        study_id = _id(study_id)
        if not isinstance(branch, str) or not branch.startswith("evidence-"):
            raise ValueError("DEDICATED_EVIDENCE_BRANCH_REQUIRED")
        if not isinstance(expected_manifest_sha256, str) or not _SHA.fullmatch(expected_manifest_sha256):
            raise ValueError("EXPECTED_MANIFEST_SHA256_REQUIRED")
    except (TypeError, ValueError):
        return EvidenceResult(False, "BLOCKED_RESTORE_SCOPE")
    prefix = "studies/" + study_id + "/"
    try:
        first = transport.get_file(prefix + "receipts/manifest.json", branch)
        if first is None:
            return EvidenceResult(False, "BLOCKED_MANIFEST_RECEIPT_MISSING")
        outer = json.loads(first[0])
        manifest = outer["payload"]
        entries = _validate_manifest(study_id, manifest)
        digest = sha256_hex(canonical_bytes(manifest))
        if digest != expected_manifest_sha256:
            return EvidenceResult(False, "FAIL_MANIFEST_HASH_MISMATCH", 0, digest)
        event_ids = ("manifest", *(e["event_id"] for e in entries))
        paths = [prefix + "_journal_index.json"]
        for event_id in event_ids:
            paths += [prefix + "claims/" + event_id + ".json",
                      prefix + "receipts/" + event_id + ".json"]
        files = {}
        for path in paths:
            result = transport.get_file(path, branch)
            if result is None:
                return EvidenceResult(False, "BLOCKED_RESTORE_FILE_MISSING",
                                      len(files), digest)
            files[path] = result[0]
        journal_report = verify_snapshot(study_id, files)
        if not journal_report.ok:
            return EvidenceResult(False, "FAIL_" + journal_report.status,
                                  journal_report.records_checked, digest)
        # Claims must precede receipts in the journal's own UTC chronology.
        for event_id in event_ids:
            claim = json.loads(files[prefix + "claims/" + event_id + ".json"])
            receipt = json.loads(files[prefix + "receipts/" + event_id + ".json"])
            if _date(claim.get("claimed_at")) > _date(receipt.get("recorded_at")):
                return EvidenceResult(False, "FAIL_CLAIM_AFTER_RECEIPT",
                                      journal_report.records_checked, digest)
        for entry in entries:
            path = prefix + "receipts/" + entry["event_id"] + ".json"
            receipt = json.loads(files[path])
            record = receipt["payload"]
            _check_record(record, study_id, entry["event_id"])
            raw = canonical_bytes(record)
            if (record["record_type"] != entry["record_type"]
                    or len(raw) != entry["size_bytes"]
                    or sha256_hex(raw) != entry["sha256"]):
                return EvidenceResult(False, "FAIL_MANIFEST_RECORD_MISMATCH",
                                      journal_report.records_checked, digest)
        # Verify manifest receipt is the same document used to derive the paths.
        if canonical_bytes(json.loads(files[prefix + "receipts/manifest.json"])["payload"]) != canonical_bytes(manifest):
            return EvidenceResult(False, "FAIL_MANIFEST_RACE", journal_report.records_checked, digest)
        return EvidenceResult(True, "RESTORE_VERIFIED_APPLICATION_ONLY",
                              journal_report.records_checked, digest)
    except (KeyError, ValueError, TypeError, UnicodeError):
        return EvidenceResult(False, "FAIL_CORRUPT_REMOTE_EVIDENCE")
    except Exception:
        return EvidenceResult(False, "BLOCKED_REMOTE_UNAVAILABLE")
