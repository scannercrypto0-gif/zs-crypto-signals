"""Durable bounded market-wide research cursor. Explicit foreground calls only."""
from collections import Counter
from contextlib import closing
import json
import sqlite3

from .marketwide_research import evaluate
from .stage05_contracts import canonical, digest


class PauseScan(RuntimeError):
    """A technical stop, never an assertion of valid full coverage."""


class ScanLedger:
    def __init__(self, path):
        self.path = path
        with closing(self._open()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    scan TEXT PRIMARY KEY, snapshot BLOB NOT NULL, boundary INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (
                    scan TEXT NOT NULL, symbol TEXT NOT NULL, state TEXT NOT NULL, result BLOB, result_sha256 TEXT,
                    PRIMARY KEY(scan, symbol));
                CREATE TABLE IF NOT EXISTS events (
                    symbol TEXT NOT NULL, boundary INTEGER NOT NULL, scan TEXT NOT NULL,
                    PRIMARY KEY(symbol, boundary));
                CREATE TABLE IF NOT EXISTS rotation (singleton INTEGER PRIMARY KEY, symbol TEXT NOT NULL);
                INSERT OR IGNORE INTO rotation VALUES(1, '');
            """)

    def _open(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    @staticmethod
    def _verify_snapshot(snapshot):
        raw = {k: v for k, v in snapshot.items() if k != "snapshot_sha256"}
        if digest(canonical(raw)) != snapshot["snapshot_sha256"]:
            raise ValueError("SNAPSHOT_HASH_MISMATCH")

    def register(self, snapshot, boundary):
        self._verify_snapshot(snapshot)
        pin = snapshot["snapshot_sha256"]
        if type(boundary) is not int or boundary % 1800000:
            raise ValueError("BOUNDARY_INVALID")
        scan = digest(canonical([pin, boundary]))
        raw = canonical(snapshot)
        with closing(self._open()) as db:
            db.execute("INSERT OR IGNORE INTO snapshots VALUES(?,?,?)", (scan, raw, boundary))
            if db.execute("SELECT snapshot,boundary FROM snapshots WHERE scan=?", (scan,)).fetchone() != (raw, boundary):
                raise ValueError("SNAPSHOT_IDENTITY_CONFLICT")
        return scan

    def claim(self, scan):
        with closing(self._open()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                snapshot, boundary = db.execute("SELECT snapshot,boundary FROM snapshots WHERE scan=?", (scan,)).fetchone()
                snapshot = json.loads(snapshot)
                self._verify_snapshot(snapshot)
                rows = [r for r in snapshot["rows"] if r["eligible"]]
                used = {r[0] for r in db.execute("SELECT symbol FROM events WHERE boundary=?", (boundary,))}
                last, = db.execute("SELECT symbol FROM rotation WHERE singleton=1").fetchone()
                queued = sorted((r for r in rows if r["symbol"] not in used),
                                key=lambda r: (r["symbol"] <= last, r["symbol"]))
                item = queued[0] if queued else None
                if item:
                    db.execute("INSERT INTO events VALUES(?,?,?)", (item["symbol"], boundary, scan))
                    db.execute("INSERT INTO attempts VALUES(?,?,?,NULL,NULL)", (scan, item["symbol"], "CLAIMED"))
                    db.execute("UPDATE rotation SET symbol=? WHERE singleton=1", (item["symbol"],))
                db.execute("COMMIT")
                return item
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def finish(self, scan, symbol, state, result):
        with closing(self._open()) as db:
            changed = db.execute(
                "UPDATE attempts SET state=?, result=?, result_sha256=? WHERE scan=? AND symbol=? AND state='CLAIMED'",
                (state, canonical(result), digest(canonical(result)), scan, symbol)).rowcount
            if changed != 1:
                raise ValueError("CLAIM_CONFLICT_OR_REPLAY")

    def chunk(self, scan, fetch, *, max_pairs, healthy, stop_reason=None):
        if type(max_pairs) is not int or not 1 <= max_pairs <= 4:
            raise ValueError("CHUNK_LIMIT_1_TO_4")
        stopped = None
        for _ in range(max_pairs):
            # Recheck time/budget before every claim; caller must also guard each GET.
            if not healthy():
                # Optional caller diagnostic; health gate is still authoritative.
                stopped = (stop_reason() if stop_reason is not None else None) or "CLOCK_SOURCE_OR_BUDGET_UNHEALTHY"
                break
            item = self.claim(scan)
            if item is None:
                break
            try:
                packet = fetch(item)
                with closing(self._open()) as db:
                    boundary, = db.execute("SELECT boundary FROM snapshots WHERE scan=?", (scan,)).fetchone()
                if packet["symbol"] != item["symbol"] or packet["boundary_ms"] != boundary:
                    raise ValueError("FETCH_IDENTITY_MISMATCH")
                result = evaluate(packet)
                self.finish(scan, item["symbol"], "EVALUATED", result)
            except PauseScan as exc:
                # Preserve the one explicit window-expiry diagnostic, without
                # mislabeling unrelated transport pauses as clock problems.
                stopped = str(exc) or "QUOTA_CONNECTIVITY_OR_DEADLINE"
                self.finish(scan, item["symbol"], "PAUSED", [])
                break
            except (ValueError, KeyError, TypeError):
                self.finish(scan, item["symbol"], "DATA_INVALID", [])
        return self.report(scan, stopped=stopped)

    def report(self, scan, *, stopped=None):
        with closing(self._open()) as db:
            raw, boundary = db.execute("SELECT snapshot,boundary FROM snapshots WHERE scan=?", (scan,)).fetchone()
            reserved_elsewhere = {row[0] for row in db.execute(
                "SELECT symbol FROM events WHERE boundary=? AND scan<>?", (boundary, scan))}
            attempts = list(db.execute("SELECT symbol,state,result,result_sha256 FROM attempts WHERE scan=? ORDER BY symbol", (scan,)))
        snapshot = json.loads(raw)
        self._verify_snapshot(snapshot)
        eligible = sum(r["eligible"] for r in snapshot["rows"])
        per_symbol = []
        counts = Counter()
        valid = 0
        for symbol, state, raw_result, pin in attempts:
            if ((raw_result is None and pin is not None)
                    or (raw_result is not None and digest(raw_result) != pin)):
                raise ValueError("DURABLE_RESULT_HASH_MISMATCH")
            results = json.loads(raw_result) if raw_result is not None else []
            passed = len(results) == 2 and all(r["source_validated"] for r in results)
            valid += passed
            counts.update(r["direction"] + ":" + r["status"] for r in results)
            per_symbol.append(dict(symbol=symbol, state=state, results=results))
        if not eligible or valid != eligible:
            zero = "ZERO_SIGNALS_DUE_TO_INCOMPLETE_SCAN"
        else:
            zero = "ZERO_SIGNALS_DUE_TO_POLICY_BLOCK"
        attempted_symbols = {row[0] for row in attempts}
        unscanned = [
            dict(symbol=r["symbol"],
                 reason="DUPLICATE_PAIR_BOUNDARY_RESERVED" if r["symbol"] in reserved_elsewhere else "QUEUED_UNSCANNED")
            for r in snapshot["rows"] if r["eligible"] and r["symbol"] not in attempted_symbols
        ]
        return dict(
            scan_id=scan, snapshot_sha256=snapshot["snapshot_sha256"], boundary_ms=boundary,
            inventory_scope=snapshot["scope"], discovered=len(snapshot["rows"]),
            active=sum(r["active"] for r in snapshot["rows"]), eligible=eligible,
            excluded=dict(sorted(Counter(reason for r in snapshot["rows"] for reason in r["reasons"]).items())),
            queued=sum(r["reason"] == "QUEUED_UNSCANNED" for r in unscanned),
            unscanned_symbols=unscanned, attempted=len(attempts), source_validated=valid,
            directionally_evaluated=2*valid,
            counts=dict(sorted(counts.items())), actual_evaluations=per_symbol,
            not_scanned=eligible-valid, coverage_pct=round(100 * valid / eligible, 4) if eligible else None,
            coverage="MARKET_COVERAGE_VERIFIED" if eligible and valid == eligible else "MARKET_COVERAGE_PARTIAL",
            stopped_reason=stopped, stopped_due_to_quota=stopped == "QUOTA_CONNECTIVITY_OR_DEADLINE",
            stale_or_invalid=sum(r["state"] == "DATA_INVALID" or any(
                x["status"] == "DATA_INVALID" for x in r["results"]) for r in per_symbol),
            interrupted_or_paused=sum(r["state"] in ("CLAIMED", "PAUSED") for r in per_symbol),
            production_signals=0, zero_signal_reason=zero,
            detector_zero_reason=(
                "ZERO_SIGNALS_WITH_FULL_VALID_COVERAGE"
                if eligible and valid == eligible and not any(
                    x["status"] != "NO_TRIGGER" for row in per_symbol for x in row["results"])
                else "DETECTOR_CANDIDATES_OR_INCOMPLETE_SCAN"),
            qualification="QV1_REAL_POLICY_BLOCKED", live_e2e="LIVE_E2E_NOT_PROVEN",
        )
