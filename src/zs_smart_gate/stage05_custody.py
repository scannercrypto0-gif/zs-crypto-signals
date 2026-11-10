"""Windows-local application custody and source-bound Stage05 readback."""
from contextlib import closing
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType

from .e2e51 import analyze
from .stage05_contracts import ContractError, canonical, digest, ensure_event, parse_utc

KEY = re.compile(r"[a-z-]+/[0-9a-f]{64}\Z")


class LocalOutbox:
    """Atomic insert and digest readback, with no application update/delete path."""

    def __init__(self, path):
        self.path = Path(path)
        with closing(self._open()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, sha TEXT NOT NULL, payload BLOB NOT NULL)")
            for action in ("UPDATE", "DELETE"):
                db.execute(f"CREATE TRIGGER IF NOT EXISTS no_{action} BEFORE {action} ON records "
                           "BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END")

    def _open(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def read(self, key):
        if not KEY.fullmatch(key):
            raise ContractError("OUTBOX_KEY_INVALID")
        with closing(self._open()) as db:
            row = db.execute("SELECT sha,payload FROM records WHERE key=?", (key,)).fetchone()
        if row is None:
            return None
        if digest(row[1]) != row[0]:
            raise ContractError("OUTBOX_PAYLOAD_SHA_MISMATCH")
        return row[1]

    def create_if_absent(self, key, content):
        if not KEY.fullmatch(key) or not isinstance(content, bytes) or len(content) > 262144:
            raise ContractError("OUTBOX_RECORD_INVALID")
        with closing(self._open()) as db, db:
            cursor = db.execute("INSERT INTO records VALUES (?,?,?) ON CONFLICT(key) DO NOTHING",
                                (key, digest(content), content))
        if cursor.rowcount == 1 and self.read(key) != content:
            raise ContractError("OUTBOX_READBACK_MISMATCH")
        return cursor.rowcount == 1


class VerifiedUpstream:
    """Read back a prior journal row, then reproduce the real bounded decision.

    Only the existing public Spot rejection schema is admitted. An approved
    qualification evaluator needs its own versioned verifier before it can enter.
    """

    def __init__(self, journal, reviewed_refs):
        self.journal = journal
        # Deployment loads these pins from its separately reviewed evidence.
        self._reviewed_refs = MappingProxyType(dict(reviewed_refs))

    def read(self, identity, expected_sha):
        from .pre05_offline_chain import LocalChainJournal
        if type(self.journal) is not LocalChainJournal:
            raise ContractError("LOCAL_DECISION_JOURNAL_REQUIRED")
        if not re.fullmatch(r"[0-9a-f]{64}", identity) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            raise ContractError("UPSTREAM_REFERENCE_INVALID")
        if self._reviewed_refs.get(identity) != expected_sha:
            raise ContractError("UPSTREAM_REFERENCE_NOT_REVIEWED")
        row = self.journal.read_verified(identity)
        if digest(canonical(row)) != expected_sha:
            raise ContractError("UPSTREAM_READBACK_SHA_MISMATCH")
        try:
            event = row["stage05_event"]
            ensure_event(event)
            if (event["source_scope"] != "APPROVED_REAL_SOURCE"
                    or event["qualification_status"] != "REJECTED"
                    or event.get("qualification_authority") is not None
                    or event.get("qualification_evidence_sha256") is not None):
                raise ContractError("APPROVED_QUALIFICATION_EVALUATOR_UNAVAILABLE")
            decision = parse_utc(event["timestamps"]["decision_at"])
            source = row["source_receipts"]
            if digest(canonical(source)) != row["source_sha256"]:
                raise ContractError("UPSTREAM_SOURCE_SHA_MISMATCH")
            if event != analyze(source, int(decision.timestamp()*1000), synthetic=False):
                raise ContractError("UPSTREAM_CAUSAL_REPLAY_MISMATCH")
        except ContractError:
            raise
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise ContractError("UPSTREAM_CAUSAL_REPLAY_INVALID") from exc
        return event

    def snapshot(self, identity, expected_sha, symbol):
        event = self.read(identity, expected_sha)
        if event["symbol"] != symbol:
            return None
        return {"symbol": symbol, "as_of": event["timestamps"]["decision_at"],
                "indicators": event["indicators"], "score": None,
                "source_sha256": event["source_manifest_sha256"],
                "decision_sha256": digest(canonical(event)),
                "closed_at": event["timestamps"]["decision_candle_close_at"],
                "source_frame": event["candle_metadata"]["frame"],
                "source_scope": event["source_scope"], "decision": "RESEARCH_ONLY_REJECTED",
                "reason_codes": event["reject_reason_codes"]}
