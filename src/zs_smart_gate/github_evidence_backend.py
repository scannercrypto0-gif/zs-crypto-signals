"""Opt-in GitHub Contents API backend for the bounded evidence journal.

Inert by default. Tests inject an in-memory transport and never contact GitHub.
Git history and CAS/readback are application-level controls, not WORM protection.
"""
from __future__ import annotations
import base64
from dataclasses import dataclass
import json
import re
from typing import Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from .evidence_journal import MAX_STUDY_BYTES, canonical_bytes, sha256_hex

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RECORD = re.compile(r"^studies/([A-Za-z0-9][A-Za-z0-9._-]{0,127})/(claims|receipts)/([A-Za-z0-9][A-Za-z0-9._-]{0,127})\.json$")

class GitHubStorageError(RuntimeError):
    """Sanitized failure; never includes credentials or response body."""

class ContentsTransport(Protocol):
    def get_file(self, path: str, branch: str) -> tuple[bytes, str] | None: ...
    def put_file(self, path: str, body: bytes, branch: str, sha: str | None, message: str) -> bool: ...

class GitHubContentsTransport:
    """Minimal REST transport. Construct only after separately approved activation."""
    def __init__(self, repository: str, token: str, *, timeout: float = 5.0):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("INVALID_REPOSITORY")
        if not token or "\n" in token or "\r" in token:
            raise ValueError("TOKEN_REQUIRED")
        if timeout <= 0 or timeout > 15:
            raise ValueError("INVALID_TIMEOUT")
        self.repository, self._token, self.timeout = repository, token, timeout

    def _headers(self):
        return {"Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + self._token,
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "zs-single-study-evidence-journal"}

    def get_file(self, path: str, branch: str) -> tuple[bytes, str] | None:
        url = "https://api.github.com/repos/" + self.repository + "/contents/" + quote(path, safe="/") + "?ref=" + quote(branch, safe="")
        try:
            with urlopen(Request(url, headers=self._headers(), method="GET"), timeout=self.timeout) as response:
                status, raw = response.status, response.read()
        except HTTPError as exc:
            if exc.code == 404:
                return None
            raise GitHubStorageError("GITHUB_READ_HTTP_" + str(exc.code)) from None
        except (URLError, TimeoutError, OSError):
            raise GitHubStorageError("GITHUB_TRANSPORT_UNAVAILABLE") from None
        if status != 200:
            raise GitHubStorageError("GITHUB_READ_HTTP_" + str(status))
        try:
            record = json.loads(raw)
            if record.get("encoding") != "base64" or not isinstance(record.get("content"), str):
                raise ValueError
            content = base64.b64decode(record["content"], validate=True)
            sha = record["sha"]
            if not isinstance(sha, str) or not sha:
                raise ValueError
            return content, sha
        except Exception:
            raise GitHubStorageError("GITHUB_READ_RESPONSE_INVALID") from None

    def put_file(self, path: str, body: bytes, branch: str, sha: str | None, message: str) -> bool:
        url = "https://api.github.com/repos/" + self.repository + "/contents/" + quote(path, safe="/")
        payload = {"message": "evidence journal: " + message[:80],
                   "content": base64.b64encode(body).decode("ascii"), "branch": branch}
        if sha is not None:
            payload["sha"] = sha
        headers = self._headers()
        headers["Content-Type"] = "application/json"
        request = Request(url, data=json.dumps(payload, separators=(",", ":")).encode("utf-8"), headers=headers, method="PUT")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if response.status not in (200, 201):
                    raise GitHubStorageError("GITHUB_WRITE_HTTP_" + str(response.status))
                try:
                    result = json.loads(response.read())
                    if (not isinstance(result, dict)
                        or not isinstance(result.get("content"), dict)
                        or not isinstance(result["content"].get("sha"), str)
                        or not result["content"]["sha"]
                        or not isinstance(result.get("commit"), dict)
                        or not isinstance(result["commit"].get("sha"), str)
                        or not result["commit"]["sha"]):
                        raise ValueError
                except (ValueError, TypeError, KeyError):
                    raise GitHubStorageError("GITHUB_WRITE_RESPONSE_INVALID") from None
                return True
        except HTTPError as exc:
            if exc.code in (409, 422):
                return False
            raise GitHubStorageError("GITHUB_WRITE_HTTP_" + str(exc.code)) from None
        except (URLError, TimeoutError, OSError):
            raise GitHubStorageError("GITHUB_TRANSPORT_UNAVAILABLE") from None

@dataclass(frozen=True)
class RestoreReport:
    ok: bool
    status: str
    records_checked: int

def verify_snapshot(study_id: str, files: Mapping[str, bytes]) -> RestoreReport:
    """Validate a fresh-clone snapshot in memory; no network/filesystem access."""
    if not isinstance(study_id, str) or not _ID.fullmatch(study_id):
        return RestoreReport(False, "INVALID_STUDY_ID", 0)
    claims, receipts, checked = {}, {}, 0
    index_path = "studies/" + study_id + "/_journal_index.json"
    index = None
    for path, body in files.items():
        if path == index_path:
            try:
                index = json.loads(body)
                if not isinstance(index, dict) or canonical_bytes(index) != body:
                    return RestoreReport(False, "INVALID_CAPACITY_INDEX", checked)
                reservations = index.get("reservations")
                if index.get("schema") != "zs-evidence-capacity-v1" or index.get("study_id") != study_id or not isinstance(reservations, dict):
                    return RestoreReport(False, "INVALID_CAPACITY_INDEX", checked)
                if any(not isinstance(n, int) or isinstance(n, bool) or n < 0 for n in reservations.values()):
                    return RestoreReport(False, "INVALID_CAPACITY_INDEX", checked)
                if sum(reservations.values()) > MAX_STUDY_BYTES:
                    return RestoreReport(False, "CAPACITY_INDEX_OVER_LIMIT", checked)
                continue
            except Exception:
                return RestoreReport(False, "INVALID_CAPACITY_INDEX", checked)
        match = _RECORD.fullmatch(path) if isinstance(path, str) else None
        if not match or match.group(1) != study_id:
            return RestoreReport(False, "UNEXPECTED_PATH", checked)
        kind, event_id = match.group(2), match.group(3)
        try:
            record = json.loads(body)
            if not isinstance(record, dict) or canonical_bytes(record) != body:
                return RestoreReport(False, "NON_CANONICAL_RECORD", checked)
        except Exception:
            return RestoreReport(False, "INVALID_JSON", checked)
        if record.get("study_id") != study_id or record.get("event_id") != event_id:
            return RestoreReport(False, "RECORD_ID_MISMATCH", checked)
        if kind == "claims":
            if record.get("schema") != "zs-evidence-claim-v1" or record.get("external_attempts_authorized_by_this_record") is not False:
                return RestoreReport(False, "INVALID_CLAIM", checked)
            claims[event_id] = record
        else:
            if record.get("schema") != "zs-evidence-receipt-v1":
                return RestoreReport(False, "INVALID_RECEIPT_SCHEMA", checked)
            digest = record.get("payload_sha256")
            if not isinstance(digest, str) or sha256_hex(canonical_bytes(record.get("payload"))) != digest:
                return RestoreReport(False, "PAYLOAD_CHECKSUM_MISMATCH", checked)
            receipts[event_id] = record
        checked += 1
    if index is None:
        return RestoreReport(False, "CAPACITY_INDEX_MISSING", checked)
    if set(receipts) - set(claims):
        return RestoreReport(False, "RECEIPT_WITHOUT_CLAIM", checked)
    if set(claims) - set(receipts):
        return RestoreReport(False, "CLAIM_WITHOUT_RECEIPT", checked)
    expected_reservations = {}
    for event_id, body in ((event, files["studies/" + study_id + "/claims/" + event + ".json"]) for event in claims):
        expected_reservations["claim-" + event_id] = len(body)
    for event_id, body in ((event, files["studies/" + study_id + "/receipts/" + event + ".json"]) for event in receipts):
        expected_reservations["receipt-" + event_id] = len(body)
    for reservation_id, size in expected_reservations.items():
        if index["reservations"].get(reservation_id) != size:
            return RestoreReport(False, "CAPACITY_RESERVATION_MISMATCH", checked)
    if set(index["reservations"]) != set(expected_reservations):
        return RestoreReport(False, "ORPHAN_CAPACITY_RESERVATION", checked)
    return RestoreReport(True, "RESTORE_VERIFIED", checked)

class GitHubEvidenceBackend:
    """Single-study backend; no transport use unless explicitly enabled."""
    def __init__(self, study_id: str, *, branch: str, transport: ContentsTransport | None = None,
                 enabled: bool = False, max_study_bytes: int = MAX_STUDY_BYTES):
        if not isinstance(study_id, str) or not _ID.fullmatch(study_id):
            raise ValueError("INVALID_STUDY_ID")
        if not branch or branch == "main" or branch.startswith("refs/"):
            raise ValueError("DEDICATED_NON_MAIN_BRANCH_REQUIRED")
        if not 1 <= max_study_bytes <= MAX_STUDY_BYTES:
            raise ValueError("INVALID_STUDY_CAP")
        if enabled and transport is None:
            raise ValueError("TRANSPORT_REQUIRED")
        self.study_id, self.branch, self.transport = study_id, branch, transport
        self.enabled, self.max_study_bytes = enabled, max_study_bytes

    def _ready(self):
        if not self.enabled or self.transport is None:
            raise GitHubStorageError("BACKEND_DISABLED")

    def _record_path(self, key: str) -> str:
        match = _RECORD.fullmatch(key) if isinstance(key, str) else None
        if not match or match.group(1) != self.study_id:
            raise ValueError("INVALID_RECORD_PATH")
        return key

    def read(self, key: str) -> bytes | None:
        self._ready()
        result = self.transport.get_file(self._record_path(key), self.branch)
        return None if result is None else result[0]

    def create_if_absent(self, key: str, value: bytes) -> bool:
        self._ready()
        key = self._record_path(key)
        if not isinstance(value, bytes):
            raise TypeError("BYTES_REQUIRED")
        if self.transport.get_file(key, self.branch) is not None:
            return False
        # Concurrent creates must be rejected by the Contents API conflict response.
        return self.transport.put_file(key, value, self.branch, None, "create-if-absent")

    def reserve_capacity(self, study_id: str, reservation_id: str, size: int, limit: int) -> bool:
        self._ready()
        if study_id != self.study_id or not isinstance(reservation_id, str) or not _ID.fullmatch(reservation_id):
            return False
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            return False
        if limit != self.max_study_bytes or size > limit:
            return False
        path = "studies/" + self.study_id + "/_journal_index.json"
        current = self.transport.get_file(path, self.branch)
        if current is None:
            index, sha = {"schema": "zs-evidence-capacity-v1", "study_id": self.study_id, "reservations": {}}, None
        else:
            raw, sha = current
            try:
                index = json.loads(raw)
                if (not isinstance(index, dict) or index.get("schema") != "zs-evidence-capacity-v1"
                    or index.get("study_id") != self.study_id or not isinstance(index.get("reservations"), dict)):
                    return False
            except Exception:
                return False
        reservations = index["reservations"]
        if reservation_id in reservations:
            return reservations[reservation_id] == size
        if any(not isinstance(n, int) or isinstance(n, bool) or n < 0 for n in reservations.values()):
            return False
        if sum(reservations.values()) + size > limit:
            return False
        updated = dict(index)
        updated["reservations"] = dict(reservations)
        updated["reservations"][reservation_id] = size
        # Single compare-and-swap attempt. Conflict fails closed; never retries market work.
        return self.transport.put_file(path, canonical_bytes(updated), self.branch, sha, "reserve-capacity")
