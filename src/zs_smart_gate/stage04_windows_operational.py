"""Stage04 Windows operational custody candidate: durable append-only SQLite ledger.

Owner design: Windows is intended operational canonical at release; GitHub keeps
source/governance and permitted historical research evidence. This code does NOT
claim production readiness until independent Windows backup/restore, permissions,
encrypted external media, quotas and operational failure drills are evidenced.

No network, Telegram, production dispatch, trading, or implicit migrations.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3

from .stage03_research_handoff import verify_handoff
from .stage05_contracts import ContractError, canonical, digest, ensure_event

SCHEMA = "zs.stage04.windows-operational-journal.v1"
BACKUP_SCHEMA = "zs.stage04.windows-backup.v1"
KEY = re.compile(r"(?:research|stage05)/[A-Za-z0-9._:-]{3,128}\Z")
MAX_RECORD_BYTES = 256 * 1024
MAX_BACKUP_BYTES = 256 * 1024 * 1024
SECRET_FIELD = re.compile(r"token|secret|password|authorization|api.?key|private.?key", re.I)
TOKEN_VALUE = re.compile(r"[0-9]{5,15}:[A-Za-z0-9_-]{20,80}")


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_payload(key: str, content: bytes) -> None:
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise ContractError("WINDOWS_JOURNAL_KEY_INVALID")
    if not isinstance(content, bytes) or not 1 <= len(content) <= MAX_RECORD_BYTES:
        raise ContractError("WINDOWS_JOURNAL_SIZE_INVALID")
    try:
        row = json.loads(content.decode("utf-8"))
        if canonical(row) != content:
            raise ContractError("WINDOWS_JOURNAL_NONCANONICAL")
        def scrub(node):
            if isinstance(node, dict):
                for field, value in node.items():
                    if SECRET_FIELD.search(field):
                        raise ContractError("WINDOWS_JOURNAL_SECRET_FIELD")
                    scrub(value)
            elif isinstance(node, list):
                for value in node:
                    scrub(value)
            elif isinstance(node, str) and TOKEN_VALUE.search(node):
                raise ContractError("WINDOWS_JOURNAL_SECRET_VALUE")
        scrub(row)
        if key.startswith("research/"):
            verify_handoff(row)
        elif key.startswith("stage05/"):
            # A syntactically valid Stage05 v1 event is NOT trusted real approval.
            ensure_event(row)
        else:
            raise ContractError("WINDOWS_JOURNAL_NAMESPACE_INVALID")
    except ContractError:
        raise
    except (UnicodeError, ValueError, TypeError, KeyError):
        raise ContractError("WINDOWS_JOURNAL_INVALID_JSON") from None


@dataclass(frozen=True)
class BackupReceipt:
    backup_sha256: str
    record_count: int
    byte_count: int
    integrity: str
    external_volume_verified: bool
    encrypted_volume_verified: bool = False
    production_recovery_approved: bool = False


class WindowsOperationalJournal:
    """A single-owner SQLite ledger; *application* append-only, not WORM.

    Paths are explicit: no secrets or default user directory and no GitHub
    credentials. Each append is an independent SQLite transaction with
    synchronous=FULL and an application readback; duplicate conflicts stop.
    The database file itself remains subject to privileged rewriting.
    """

    def __init__(self, path):
        self.path = Path(path)
        if not self.path.parent.is_dir() or self.path.exists() and self.path.is_symlink():
            raise ContractError("WINDOWS_JOURNAL_PARENT_OR_SYMLINK_INVALID")
        with closing(self._open()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS custody (
                record_key TEXT PRIMARY KEY,
                sha256 TEXT NOT NULL,
                payload BLOB NOT NULL,
                payload_size INTEGER NOT NULL
            )""")
            for action in ("UPDATE", "DELETE"):
                db.execute("CREATE TRIGGER IF NOT EXISTS custody_no_" + action.lower() +
                           " BEFORE " + action + " ON custody "
                           "BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END")

    def _open(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def create_if_absent(self, key: str, content: bytes) -> bool:
        _validate_payload(key, content)
        with closing(self._open()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT sha256,payload FROM custody WHERE record_key=?",
                                 (key,)).fetchone()
                if row is not None:
                    if row[0] != digest(content) or row[1] != content:
                        raise ContractError("WINDOWS_JOURNAL_IDENTITY_CONFLICT")
                    db.execute("COMMIT")
                    return False
                db.execute("INSERT INTO custody VALUES(?,?,?,?)",
                           (key, digest(content), content, len(content)))
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        if self.read(key) != content:
            raise ContractError("WINDOWS_JOURNAL_READBACK_MISMATCH")
        return True

    def read(self, key: str) -> bytes | None:
        if not isinstance(key, str) or not KEY.fullmatch(key):
            raise ContractError("WINDOWS_JOURNAL_KEY_INVALID")
        with closing(self._open()) as db:
            row = db.execute("SELECT sha256,payload,payload_size FROM custody "
                             "WHERE record_key=?", (key,)).fetchone()
        if row is None:
            return None
        checksum, content, size = row
        if size != len(content) or digest(content) != checksum:
            raise ContractError("WINDOWS_JOURNAL_CORRUPT_RECORD")
        _validate_payload(key, content)
        return content

    def verify_all(self) -> tuple[int, int]:
        with closing(self._open()) as db:
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ContractError("WINDOWS_JOURNAL_SQLITE_INTEGRITY_FAIL")
            rows = db.execute("SELECT record_key FROM custody ORDER BY record_key").fetchall()
        total = 0
        for (key,) in rows:
            value = self.read(key)
            total += len(value)
        return len(rows), total

    def make_backup(self, destination, *, expected_external_volume=False) -> BackupReceipt:
        """SQLite online consistent snapshot, not a verified off-device disaster drill.

        Destination must not exist (nor its sidecar). Independent backup means
        externally protected/encrypted volume and separate raw SHA pin; external
        volume is reported as an observation, never self-approved by this method.
        """
        target = Path(destination)
        if (target.exists() or Path(str(target)+".manifest.json").exists()
                or not target.parent.is_dir() or target.is_symlink()
                or target.resolve() == self.path.resolve()):
            raise ContractError("WINDOWS_BACKUP_TARGET_EXISTS_OR_INVALID")
        # Do not claim external recovery merely because a different path exists.
        cross_volume = os.stat(self.path.parent).st_dev != os.stat(target.parent).st_dev
        if expected_external_volume and not cross_volume:
            raise ContractError("WINDOWS_BACKUP_EXTERNAL_VOLUME_NOT_PROVEN")
        before = self.verify_all()
        tmp = target.with_name(target.name + ".unfinished")
        if tmp.exists():
            raise ContractError("WINDOWS_BACKUP_UNFINISHED_EXISTS")
        try:
            with closing(self._open()) as source:
                with closing(sqlite3.connect(tmp)) as out:
                    source.backup(out)
            if tmp.stat().st_size > MAX_BACKUP_BYTES:
                raise ContractError("WINDOWS_BACKUP_SIZE_QUOTA")
            os.replace(tmp, target)
            backup_sha = _sha_file(target)
            records = verify_backup(target, backup_sha)
            if records != before:
                raise ContractError("WINDOWS_BACKUP_SNAPSHOT_MISMATCH")
            # Cross-volume detection is best-effort only. No encryption proof.
            with Path(str(target) + ".manifest.json").open("x", encoding="utf-8") as f:
                f.write(json.dumps({
                    "schema": BACKUP_SCHEMA, "sha256": backup_sha,
                    "record_count": before[0], "payload_bytes": before[1],
                    "independent_storage": "UNVERIFIED" if not cross_volume else "DIFFERENT_VOLUME_ONLY",
                    "encrypted_media": "UNVERIFIED", "production_restore": "NOT_TESTED",
                }, sort_keys=True, separators=(",", ":")))
            return BackupReceipt(backup_sha, *before, "SQLITE_AND_SHA_READBACK_PASS",
                                 cross_volume)
        except Exception:
            # An existing completed backup is never silently deleted or replaced.
            if tmp.exists():
                tmp.unlink()
            raise

    @classmethod
    def restore_to_new_path(cls, backup_path, expected_sha256: str, new_path):
        """Strictly new path; no in-place overwrite of an existing journal."""
        source = Path(backup_path)
        dest = Path(new_path)
        if dest.exists() or dest.is_symlink() or not dest.parent.is_dir():
            raise ContractError("WINDOWS_RESTORE_TARGET_EXISTS_OR_INVALID")
        verify_backup(source, expected_sha256)
        tmp = dest.with_name(dest.name + ".unfinished")
        if tmp.exists():
            raise ContractError("WINDOWS_RESTORE_UNFINISHED_EXISTS")
        try:
            with source.open("rb") as inp, tmp.open("xb") as out:
                shutil.copyfileobj(inp, out)
                out.flush()
                os.fsync(out.fileno())
            if _sha_file(tmp) != expected_sha256:
                raise ContractError("WINDOWS_RESTORE_COPY_HASH_MISMATCH")
            os.replace(tmp, dest)
            journal = cls(dest)
            journal.verify_all()
            return journal
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise


def verify_backup(path, expected_sha256: str) -> tuple[int, int]:
    """Use an independently pinned SHA, never merely trust a sibling manifest."""
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ContractError("WINDOWS_BACKUP_PIN_REQUIRED")
    p = Path(path)
    if not p.is_file() or _sha_file(p) != expected_sha256:
        raise ContractError("WINDOWS_BACKUP_SHA_MISMATCH")
    try:
        uri = p.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ContractError("WINDOWS_BACKUP_SQLITE_INTEGRITY_FAIL")
            rows = db.execute("SELECT record_key,sha256,payload,payload_size FROM custody").fetchall()
        count = 0
        total = 0
        for key, sha, payload, length in rows:
            _validate_payload(key, payload)
            if digest(payload) != sha or len(payload) != length:
                raise ContractError("WINDOWS_BACKUP_ROW_SHA_MISMATCH")
            total += length
            count += 1
        return count, total
    except ContractError:
        raise
    except (sqlite3.Error, ValueError, TypeError, OSError):
        raise ContractError("WINDOWS_BACKUP_SQLITE_INVALID") from None
