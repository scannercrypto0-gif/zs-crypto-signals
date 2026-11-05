"""Offline research-only SQLite journal for ORDER-021.

A replaceable backend, NOT owner-Windows production custody. Uses stdlib
SQLite WAL+FULL synchronous writes and independent connection readback.
Never imports GitHub, any network client, schedule or sender.
"""
from __future__ import annotations

from contextlib import contextmanager, closing
import hashlib
import json
from pathlib import Path
import sqlite3

from .setup021 import canonical, CONFIG_SHA256


class ResearchStoreError(RuntimeError):
    pass


class SQLiteResearchJournal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS research_rows (
                    row_key TEXT PRIMARY KEY,
                    event_id TEXT UNIQUE,
                    partition TEXT NOT NULL CHECK(partition IN ('DEV','OOS')),
                    contract_sha TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    payload BLOB NOT NULL
                );
            """)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.path), timeout=3)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA busy_timeout=3000")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def append_readback(self, result):
        """One atomic immutable row, committed before readback; no overwrite."""
        if result.get("contract_sha256") != CONFIG_SHA256:
            raise ResearchStoreError("CONTRACT_MISMATCH")
        if result.get("partition") not in ("DEV", "OOS"):
            raise ResearchStoreError("PARTITION_INVALID")
        if result.get("status") not in ("RESEARCH_CANDIDATE", "DETECTED_SIGNAL"):
            raise ResearchStoreError("UNAUTHORIZED_RESULT_TYPE")
        event_id = result.get("event_id")
        if result["status"] == "DETECTED_SIGNAL" and not event_id:
            raise ResearchStoreError("EVENT_ID_REQUIRED")
        if result["status"] != "DETECTED_SIGNAL" and event_id is not None:
            raise ResearchStoreError("UNAUTHORIZED_EVENT_ID")
        raw = canonical(result)
        if len(raw) > 65536:
            raise ResearchStoreError("ROW_LIMIT_64K")
        check = hashlib.sha256(raw).hexdigest()
        key = result["row_key"]
        if not isinstance(key, str) or len(key) != 64:
            raise ResearchStoreError("INVALID_ROW_KEY")
        with self._connect() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "INSERT INTO research_rows(row_key,event_id,partition,contract_sha,digest,payload) VALUES (?,?,?,?,?,?)",
                    (key, event_id, result["partition"], CONFIG_SHA256, check, raw),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                conn.rollback()
                prior = conn.execute(
                    "SELECT digest,payload FROM research_rows WHERE row_key=? OR (? IS NOT NULL AND event_id=?)",
                    (key, event_id, event_id),
                ).fetchone()
                if prior and prior == (check, raw):
                    return "DUPLICATE_READBACK_CONFIRMED" if self.read_verified(key) == result else "READBACK_FAILURE"
                raise ResearchStoreError("DUPLICATE_CONFLICT")
            except Exception:
                conn.rollback()
                raise
        if self.read_verified(key) != result:
            raise ResearchStoreError("POST_COMMIT_READBACK_MISMATCH")
        return "COMMITTED_AND_READBACK_VERIFIED"

    def read_verified(self, key):
        """Read through a distinct connection and rehash exact committed bytes."""
        with self._connect() as conn:
            row = conn.execute("SELECT digest,payload,contract_sha FROM research_rows WHERE row_key=?", (key,)).fetchone()
        if row is None:
            raise ResearchStoreError("READBACK_MISSING")
        digest, raw, contract = row
        if contract != CONFIG_SHA256 or hashlib.sha256(raw).hexdigest() != digest:
            raise ResearchStoreError("READBACK_HASH_OR_CONTRACT_CHANGED")
        try:
            return json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ResearchStoreError("READBACK_INVALID_JSON") from exc

    def rows(self):
        with self._connect() as conn:
            keys = [x[0] for x in conn.execute("SELECT row_key FROM research_rows ORDER BY row_key")]
        return [self.read_verified(key) for key in keys]

    def backup_and_restore_verify(self, destination):
        """SQLite Online Backup API to separate DB, then verify every row/hash."""
        destination = Path(destination)
        if destination.resolve() == self.path.resolve() or destination.exists():
            raise ResearchStoreError("BACKUP_MUST_BE_NEW_SEPARATE_PATH")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as source, closing(sqlite3.connect(str(destination))) as target:
            source.backup(target)
        restored = SQLiteResearchJournal(destination)
        with restored._connect() as conn:
            valid = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if valid != "ok":
            raise ResearchStoreError("RESTORE_INTEGRITY_FAILURE")
        originals, copies = self.rows(), restored.rows()
        if originals != copies:
            raise ResearchStoreError("RESTORE_CONTENT_MISMATCH")
        return {
            "status": "OFFLINE_BACKUP_RESTORED_VERIFIED",
            "rows": len(copies),
            "payload_set_sha256": hashlib.sha256(canonical(copies)).hexdigest(),
            "native_owner_windows_proven": False,
            "production_backup_proven": False,
        }
