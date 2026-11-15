"""Stage04 custody-neutral fixture and recovery boundary for research handoffs.

Neither GitHub evidence branches nor Windows SQLite is promoted to an approved
canonical production backend by this module. Existing Stage04 receipts remain
untouched. No network, filesystem, secrets, or production transport permitted.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .stage03_research_handoff import verify_handoff
from .stage05_contracts import ContractError, SHA, canonical, digest

VERSION = "zs.stage04.custody-neutral-research.v1"
MAX_FIXTURE_RECORDS = 8
MAX_FIXTURE_BYTES = 256 * 1024  # bounded test fixture budget, NOT live quota
SECRET_KEYS = re.compile(r"token|password|secret|private.key|api.key|authorization|chat.id", re.I)
TELEGRAM_TOKEN = re.compile(r"[0-9]{5,15}:[A-Za-z0-9_-]{20,80}")
ID = re.compile(r"eval30-[a-f0-9]{64}\Z")


def _deny_secrets(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if not isinstance(k, str) or SECRET_KEYS.search(k):
                raise ContractError("STAGE04_PRIVATE_FIELD_FORBIDDEN")
            _deny_secrets(v)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _deny_secrets(value)
    elif isinstance(node, str) and TELEGRAM_TOKEN.search(node):
        raise ContractError("STAGE04_TOKEN_VALUE_FORBIDDEN")


def build_fixture_bundle(handoffs: tuple[dict, ...]) -> dict:
    """Content-addressed proposed manifest. This is NOT a backend decision."""
    if (not isinstance(handoffs, tuple)
            or not 1 <= len(handoffs) <= MAX_FIXTURE_RECORDS):
        raise ContractError("STAGE04_FIXTURE_RECORD_QUOTA")
    payloads = {}
    inventory = []
    used = 0
    for handoff in sorted(handoffs, key=lambda h: h.get("event_id", "")):
        verify_handoff(handoff)
        _deny_secrets(handoff)
        key = handoff["event_id"]
        if not isinstance(key, str) or not ID.fullmatch(key) or key in payloads:
            raise ContractError("STAGE04_DUPLICATE_OR_INVALID_EVENT")
        raw = canonical(handoff)
        used += len(raw)
        if used > MAX_FIXTURE_BYTES:
            raise ContractError("STAGE04_FIXTURE_BYTE_QUOTA")
        payloads[key] = raw
        inventory.append({
            "event_id": key, "sha256": digest(raw),
            "size_bytes": len(raw), "source_manifest_sha256": handoff["source_manifest_sha256"],
            "source_scope": "SYNTHETIC_TEST_ONLY",
        })
    manifest = {
        "schema": VERSION, "inventory": inventory,
        "canonical_backend": "OWNER_DECISION_PENDING",
        "authority_conflict": "MAIN_V1_36_WINDOWS_RUNTIME_VS_HISTORICAL_GITHUB_ONLY",
        "github_evidence": "HISTORICAL_APPLICATION_ONLY",
        "windows_sqlite": "BOUNDED_LOCAL_JOURNAL_NOT_VERIFIED_PERMANENT",
        "retention": "REVIEW_ONLY_NO_AUTOMATIC_DELETE",
        "secrets": "FORBIDDEN",
        "outage_policy": "UNKNOWN_NO_BLIND_RETRY",
        "replay_policy": "VERIFY_EXISTING_BYTES_THEN_EXPLICIT_RESUME",
        "fixture_record_limit": MAX_FIXTURE_RECORDS,
        "fixture_byte_limit": MAX_FIXTURE_BYTES,
        "byte_count": used,
        "eligible_for_real_dispatch": False,
        "restore_status": "NOT_PROVEN",
    }
    return {"manifest": manifest, "manifest_sha256": digest(canonical(manifest)),
            "payloads": payloads}


def validate_bundle(bundle: dict) -> bool:
    if not isinstance(bundle, dict) or set(bundle) != {
            "manifest", "manifest_sha256", "payloads"}:
        raise ContractError("STAGE04_BUNDLE_FIELDS_INVALID")
    m = bundle["manifest"]
    if (not isinstance(m, dict) or m.get("schema") != VERSION
            or m.get("canonical_backend") != "OWNER_DECISION_PENDING"
            or m.get("eligible_for_real_dispatch") is not False
            or m.get("restore_status") != "NOT_PROVEN"
            or m.get("retention") != "REVIEW_ONLY_NO_AUTOMATIC_DELETE"
            or m.get("outage_policy") != "UNKNOWN_NO_BLIND_RETRY"):
        raise ContractError("STAGE04_BUNDLE_NOT_RESEARCH_ONLY")
    if (not isinstance(bundle["manifest_sha256"], str)
            or not SHA.fullmatch(bundle["manifest_sha256"])
            or digest(canonical(m)) != bundle["manifest_sha256"]):
        raise ContractError("STAGE04_MANIFEST_SHA_MISMATCH")
    entries, payloads = m.get("inventory"), bundle.get("payloads")
    if (not isinstance(entries, list)
            or not isinstance(payloads, dict)
            or not 1 <= len(entries) <= MAX_FIXTURE_RECORDS
            or len(entries) != len(payloads)):
        raise ContractError("STAGE04_MANIFEST_INVENTORY_INVALID")
    total = 0
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
                "event_id", "sha256", "size_bytes",
                "source_manifest_sha256", "source_scope"}:
            raise ContractError("STAGE04_MANIFEST_ENTRY_INVALID")
        key = entry["event_id"]
        if not isinstance(key, str) or not ID.fullmatch(key) or key in seen:
            raise ContractError("STAGE04_MANIFEST_DUPLICATE")
        seen.add(key)
        raw = payloads.get(key)
        if not isinstance(raw, bytes) or digest(raw) != entry["sha256"]:
            raise ContractError("STAGE04_PAYLOAD_HASH_MISMATCH")
        if len(raw) != entry["size_bytes"]:
            raise ContractError("STAGE04_PAYLOAD_SIZE_MISMATCH")
        total += len(raw)
        import json
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError):
            raise ContractError("STAGE04_PAYLOAD_JSON_INVALID") from None
        verify_handoff(payload)
        _deny_secrets(payload)
        if (canonical(payload) != raw or payload["event_id"] != key
                or payload["source_manifest_sha256"] != entry["source_manifest_sha256"]
                or entry["source_scope"] != "SYNTHETIC_TEST_ONLY"):
            raise ContractError("STAGE04_PAYLOAD_MANIFEST_CONFLICT")
    if (total != m.get("byte_count") or total > MAX_FIXTURE_BYTES
            or m.get("fixture_byte_limit") != MAX_FIXTURE_BYTES
            or m.get("fixture_record_limit") != MAX_FIXTURE_RECORDS):
        raise ContractError("STAGE04_FIXTURE_CAPACITY_MISMATCH")
    return True


class MemoryFixtureStore:
    """Only allowed simulated backend. Does not represent durable storage."""

    def __init__(self, *, fail_after=None):
        self.data: dict[str, bytes] = {}
        self.fail_after = fail_after
        self.inserts = 0

    def put_once(self, key: str, value: bytes) -> bool:
        if self.fail_after is not None and self.inserts >= self.fail_after:
            raise IOError("SIMULATED_FIXTURE_OUTAGE")
        if key in self.data:
            if self.data[key] != value:
                raise ContractError("STAGE04_APPEND_ONLY_CONFLICT")
            return False
        self.data[key] = value
        self.inserts += 1
        return True

    def read(self, key: str) -> bytes | None:
        return self.data.get(key)


@dataclass(frozen=True)
class FixtureReceipt:
    status: str
    records_verified: int
    manifest_sha256: str
    canonical_backend_approved: bool = False


def _keys(bundle: dict) -> list[tuple[str, bytes]]:
    root = "fixture-research/" + bundle["manifest_sha256"] + "/"
    return [(root+"manifest.json", canonical(bundle["manifest"])), *[
        (root+"records/"+entry["event_id"]+".json", bundle["payloads"][entry["event_id"]])
        for entry in bundle["manifest"]["inventory"]
    ]]


def persist_fixture_once(store: MemoryFixtureStore, bundle: dict) -> FixtureReceipt:
    """Crash/outage uncertainty is reported, never silently retried here."""
    if type(store) is not MemoryFixtureStore:
        raise ContractError("STAGE04_ONLY_IN_MEMORY_FIXTURE_ALLOWED")
    validate_bundle(bundle)
    checked = 0
    for key, raw in _keys(bundle):
        try:
            store.put_once(key, raw)
            if store.read(key) != raw:
                raise ContractError("STAGE04_FIXTURE_READBACK_CONFLICT")
        except Exception:
            return FixtureReceipt("UNKNOWN_PARTIAL_OR_CONFLICT", checked,
                                  bundle["manifest_sha256"])
        checked += 1
    return FixtureReceipt("VERIFIED_FIXTURE_ONLY_NOT_PERMANENT", checked,
                          bundle["manifest_sha256"])


def restore_fixture(store: MemoryFixtureStore, bundle: dict) -> FixtureReceipt:
    """Byte readback only, no claim of GitHub or Windows disaster recovery."""
    if type(store) is not MemoryFixtureStore:
        raise ContractError("STAGE04_ONLY_IN_MEMORY_FIXTURE_ALLOWED")
    validate_bundle(bundle)
    checked = 0
    for key, expected in _keys(bundle):
        try:
            observed = store.read(key)
        except Exception:
            return FixtureReceipt("UNKNOWN_READ_OUTAGE", checked, bundle["manifest_sha256"])
        if observed is None:
            return FixtureReceipt("INCOMPLETE_FIXTURE", checked, bundle["manifest_sha256"])
        if observed != expected:
            return FixtureReceipt("FAIL_FIXTURE_BYTE_CONFLICT", checked,
                                  bundle["manifest_sha256"])
        checked += 1
    return FixtureReceipt("VERIFIED_FIXTURE_ONLY_NOT_PERMANENT", checked,
                          bundle["manifest_sha256"])
