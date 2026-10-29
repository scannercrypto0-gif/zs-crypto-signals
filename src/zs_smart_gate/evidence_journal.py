"""Disabled-by-default single-study evidence journal contract.

This module contains no GitHub client, credential loading, network access, or
runtime activation. A future backend must implement atomic create-if-absent and
capacity reservation, then undergo separate PM/owner security approval.
CAS/readback checks provide application-level integrity, not tamper-proof history.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Protocol

UTC = timezone.utc
MAX_STUDY_BYTES = 10 * 1024 * 1024
MAX_SPOOL_BYTES = 10 * 1024 * 1024
SPOOL_TTL = timedelta(hours=24)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_id(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("INVALID_JOURNAL_ID")
    return value


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("UTC_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)


class JournalBackend(Protocol):
    """Required semantics for a future approved backend; no implementation here."""

    def read(self, key: str) -> bytes | None: ...
    def create_if_absent(self, key: str, value: bytes) -> bool: ...
    def reserve_capacity(self, study_id: str, reservation_id: str, size: int,
                         limit: int) -> bool: ...


@dataclass(frozen=True)
class JournalResult:
    ok: bool
    status: str
    key: str | None = None
    sha256: str | None = None


class SingleStudyJournal:
    """One-study claim/receipt journal over an injected backend.

    Claim must be durably created and read back before any external attempt.
    Receipts are unique and content-addressed. The backend must atomically
    reserve per-study bytes and atomically create each unique key. This class
    never contacts GitHub and never enables a data source.
    """

    def __init__(self, study_id: str, backend: JournalBackend, now):
        self.study_id = _safe_id(study_id)
        self.backend = backend
        self.now = now

    def _key(self, kind: str, event_id: str) -> str:
        return f"studies/{self.study_id}/{kind}/{_safe_id(event_id)}.json"

    def _create_and_verify(self, key: str, body: bytes, reservation_id: str) -> JournalResult:
        digest = sha256_hex(body)
        try:
            if not self.backend.reserve_capacity(self.study_id, reservation_id,
                                                 len(body), MAX_STUDY_BYTES):
                return JournalResult(False, "STUDY_SIZE_LIMIT", key, digest)
            if not self.backend.create_if_absent(key, body):
                return JournalResult(False, "DUPLICATE_OR_CONFLICT", key, digest)
            readback = self.backend.read(key)
        except Exception:
            return JournalResult(False, "BACKEND_UNAVAILABLE", key, digest)
        if readback is None:
            return JournalResult(False, "READBACK_MISSING", key, digest)
        if sha256_hex(readback) != digest or readback != body:
            return JournalResult(False, "READBACK_MISMATCH", key, digest)
        return JournalResult(True, "VERIFIED", key, digest)

    def claim_before_attempts(self, study_id: str, event_id: str) -> bool:
        try:
            if _safe_id(study_id) != self.study_id:
                return False
            key = self._key("claims", event_id)
        except ValueError:
            return False
        try:
            if self.backend.read(key) is not None:
                return False
        except Exception:
            return False
        try:
            body = canonical_bytes({
                "schema": "zs-evidence-claim-v1",
                "study_id": self.study_id,
                "event_id": _safe_id(event_id),
                "claimed_at": _utc(self.now()).isoformat(),
                "external_attempts_authorized_by_this_record": False,
            })
        except Exception:
            return False
        return self._create_and_verify(key, body, "claim-" + event_id).ok

    def append_and_readback(self, event_id: str, payload: dict, checksum: str) -> bool:
        try:
            event_id = _safe_id(event_id)
            claim_key = self._key("claims", event_id)
            receipt_key = self._key("receipts", event_id)
        except ValueError:
            return False
        try:
            claim = self.backend.read(claim_key)
            existing = self.backend.read(receipt_key)
        except Exception:
            return False
        if claim is None or existing is not None:
            return False
        try:
            claim_record = json.loads(claim)
            if not isinstance(claim_record, dict):
                return False
            if (
                claim_record.get("schema") != "zs-evidence-claim-v1"
                or claim_record.get("study_id") != self.study_id
                or claim_record.get("event_id") != event_id
                or claim_record.get("external_attempts_authorized_by_this_record") is not False
                or not isinstance(claim_record.get("claimed_at"), str)
            ):
                return False
            _utc(datetime.fromisoformat(claim_record["claimed_at"]))
            payload_bytes = canonical_bytes(payload)
            if sha256_hex(payload_bytes) != checksum:
                return False
            body = canonical_bytes({
                "schema": "zs-evidence-receipt-v1",
                "study_id": self.study_id,
                "event_id": event_id,
                "recorded_at": _utc(self.now()).isoformat(),
                "payload_sha256": checksum,
                "payload": payload,
            })
        except Exception:
            return False
        return self._create_and_verify(receipt_key, body, "receipt-" + event_id).ok


@dataclass(frozen=True)
class SpoolItem:
    key: str
    body: bytes
    created_at: datetime


class BoundedSpool:
    """In-memory reference model for a bounded 24-hour outage spool.

    This is not persistent storage. Production D: spool persistence and deletion
    must be implemented and approved separately; expired data is never replayed.
    """

    def __init__(self, *, max_bytes: int = MAX_SPOOL_BYTES,
                 ttl: timedelta = SPOOL_TTL):
        if max_bytes < 1 or ttl.total_seconds() <= 0:
            raise ValueError("INVALID_SPOOL_LIMITS")
        self.max_bytes = max_bytes
        self.ttl = ttl
        self._items: dict[str, SpoolItem] = {}

    @property
    def size_bytes(self) -> int:
        return sum(len(item.body) for item in self._items.values())

    def put(self, key: str, body: bytes, *, now: datetime) -> bool:
        key = _safe_id(key)
        now = _utc(now)
        self.expire(now=now)
        if key in self._items or self.size_bytes + len(body) > self.max_bytes:
            return False
        self._items[key] = SpoolItem(key, bytes(body), now)
        return True

    def get_for_replay(self, key: str, *, now: datetime) -> bytes | None:
        now = _utc(now)
        self.expire(now=now)
        item = self._items.get(_safe_id(key))
        if item is None or now - item.created_at >= self.ttl:
            return None
        return item.body

    def expire(self, *, now: datetime) -> int:
        now = _utc(now)
        stale = [key for key, item in self._items.items()
                 if now - item.created_at >= self.ttl]
        for key in stale:
            del self._items[key]
        return len(stale)
