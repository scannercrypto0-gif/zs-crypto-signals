"""PRE05: one-source, synthetic-only Stage00→04 research chain.

Stage00 is an explicitly attributed CLOSED synthetic receipt bundle, not a
public-market or independent publisher receipt. The selected Stage01 scanner
bars and Stage02 frozen Setup bars are exactly the same original 5m records
which enter Stage03 03A/R2. Stage04 uses a LOCAL SQLite application journal
only; it neither contacts GitHub nor claims GitHub canary/WORM equivalence.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import hashlib
import json
import re
import sqlite3

from .scanner import build_universe, inspect_candles
from .setup021 import evaluate as evaluate_setup
from .stage03_r2_closure import stage03_c1c4_research_from_closed_receipts

SCHEMA = "ZS_PRE05_SINGLE_SOURCE_OFFLINE_CHAIN_V1"
UTC_TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)\Z")
CASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class ChainRejected(ValueError):
    """A known source/edge mismatch; never a production opportunity."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def instant(value, field):
    if not isinstance(value, str) or not UTC_TIME.fullmatch(value):
        raise ChainRejected("EXPLICIT_UTC_REQUIRED:" + field)
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ChainRejected("INVALID_UTC:" + field) from exc
    if stamp.utcoffset() != timedelta(0):
        raise ChainRejected("EXPLICIT_UTC_REQUIRED:" + field)
    return stamp


def _source_klines(record):
    """Return the SAME 22 closed raw 5m records from the 03A/R2 source."""
    try:
        parent = record["parent"]
        ctx = record["context"]["5m"]
        children = record["children"]
        core = record["core_5m"]
    except (KeyError, TypeError) as exc:
        raise ChainRejected("SOURCE_WINDOW_FIELDS_MISSING") from exc
    if not all(isinstance(x, (list, tuple)) for x in (ctx, children, core)):
        raise ChainRejected("SOURCE_WINDOW_SEQUENCE_REQUIRED")
    if (len(ctx) < 16 or len(children) != 6 or len(core) != 21
            or list(core[-6:]) != list(children)
            or list(core[:15]) != list(ctx[-15:])):
        raise ChainRejected("STAGE01_03_WINDOW_JOIN_MISMATCH")
    bars = list(ctx[-16:]) + list(children)
    source_id = parent.get("source_id") if isinstance(parent, dict) else None
    if not isinstance(source_id, str) or not source_id.startswith("SYNTHETIC:"):
        raise ChainRejected("SYNTHETIC_SOURCE_PROVENANCE_REQUIRED")
    if (parent.get("timeframe") != "30m"
            or record.get("horizon") != "INTRADAY"
            or record.get("direction") != "UP"):
        raise ChainRejected("FROZEN_SETUP_INTRADAY_UP_SCOPE_REQUIRED")
    if record.get("symbol") not in ("BTCUSDT", "ETHUSDT"):
        raise ChainRejected("FROZEN_SETUP_SYMBOL_NOT_ALLOWED")
    decision = instant(record.get("decision_at"), "DECISION")
    first = None
    output = []
    prev = None
    for b in bars:
        if not isinstance(b, dict):
            raise ChainRejected("SOURCE_5M_ROW_NOT_OBJECT")
        if b.get("source_id") != source_id or b.get("timeframe") != "5m":
            raise ChainRejected("SOURCE_ID_OR_FRAME_CONFLICT")
        opened = instant(b.get("open_at"), "OPEN")
        closed = instant(b.get("close_at"), "CLOSE")
        received = instant(b.get("received_at"), "RECEIVED")
        available = instant(b.get("available_at"), "AVAILABLE")
        if (closed-opened != timedelta(minutes=5) or
                opened.minute % 5 or opened.second or opened.microsecond or
                (prev is not None and opened != prev) or
                not closed <= received <= available <= decision):
            raise ChainRejected("SOURCE_5M_GAP_FUTURE_OR_UNCLOSED")
        prev = closed
        if first is None:
            first = opened
        values = []
        for key in ("open", "high", "low", "close", "base_volume", "quote_volume"):
            val = b.get(key)
            if not isinstance(val, str) or not val.strip():
                raise ChainRejected("ORIGINAL_DECIMAL_STRING_REQUIRED:" + key)
            try:
                num = Decimal(val)
            except (ValueError, ArithmeticError) as exc:
                raise ChainRejected("INVALID_DECIMAL:" + key) from exc
            if not num.is_finite():
                raise ChainRejected("INVALID_DECIMAL:" + key)
            values.append(val)
        o, h, lo, c, base, quote = values
        opening_ms = int(opened.timestamp() * 1000)
        closing_ms = int(closed.timestamp() * 1000) - 1
        output.append([opening_ms, o, h, lo, c, base, closing_ms,
                       quote, 0, "0", "0", "0"])
    if (instant(parent.get("open_at"), "PARENT_OPEN") !=
            instant(children[0].get("open_at"), "CHILD_OPEN") or
            instant(parent.get("close_at"), "PARENT_CLOSE") != prev):
        raise ChainRejected("PARENT_CHILD_TIMELINE_MISMATCH")
    return output, source_id, decision


def _market_item(record, exchange_info, decision):
    """Use only the supplied distinct book and ticker receipts, never merge times."""
    book = record["book"]
    ticker = record["ticker24"]
    sym = record["symbol"]
    if (book.get("symbol") != sym or ticker.get("symbol") != sym
            or ticker.get("payload", {}).get("symbol") != sym
            or ticker.get("endpoint") != "/api/v3/ticker/24hr"):
        raise ChainRejected("MARKET_SYMBOL_OR_ENDPOINT_CONFLICT")
    book_receipt = book["receipt"]
    ticker_receipt = ticker["receipt"]
    book_at = instant(book_receipt.get("observed_at"), "BOOK_OBSERVED")
    if (instant(book_receipt.get("available_at"), "BOOK_AVAILABLE") > decision
            or instant(ticker_receipt.get("available_at"), "TICKER_AVAILABLE") > decision):
        raise ChainRejected("MARKET_RECEIPT_FROM_FUTURE")
    try:
        universe = build_universe(
            exchange_info,
            [{"symbol": sym, "quoteVolume": ticker["payload"]["quoteVolume"]}],
            [{"symbol": sym, "bidPrice": book["bid"], "askPrice": book["ask"]}],
            book_at,
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise ChainRejected("STAGE00_UNIVERSE_INVALID") from exc
    matches = [item for item in universe if item.symbol == sym]
    if len(matches) != 1:
        raise ChainRejected("STAGE00_EXCHANGE_IDENTITY_MISSING")
    return matches[0]


def chain_result(*, receipt_record, exchange_info, partition="DEV"):
    """Run source→scanner→frozen Setup→03A/R2 once, without network/storage.

    Rejected input yields no fake candidate or persisted observation. A frozen
    Setup DETECTED_SIGNAL remains INTERNAL; it is NEVER a production signal.
    """
    base = dict(schema=SCHEMA, status="REJECTED", stages_completed=[],
                source_scope="SYNTHETIC_ONLY_NOT_REAL_PIT",
                rejection_reasons=[], qualified=False, publishable=False,
                score=None, signal_id=None, delivery_authorized=False,
                market_requests=0, external_sends=0,
                stage04_store="NOT_ATTEMPTED")
    try:
        if not isinstance(receipt_record, dict) or not isinstance(exchange_info, dict):
            raise ChainRejected("SOURCE_OBJECTS_REQUIRED")
        source_digest = fingerprint({
            "receipt_record": receipt_record, "exchange_info": exchange_info,
        })
        raw, source_id, decision = _source_klines(receipt_record)
        base["stages_completed"].append("00_SYNTHETIC_CLOSED_SOURCE")
        item = _market_item(receipt_record, exchange_info, decision)
        if item.status != "ELIGIBLE" or item.market is None:
            raise ChainRejected("STAGE01_UNIVERSE_INELIGIBLE:" + item.status)
        base["stages_completed"].append("00_EXPLICIT_SOURCE_MARKET_RECEIPTS")
        scan = inspect_candles(item, raw[-21:],
                               instant(receipt_record["parent"]["available_at"], "PARENT_AVAILABLE"),
                               decision, 0.0)
        if scan.status != "PASS":
            raise ChainRejected("STAGE01_SCANNER_REJECTED:" +
                                (scan.reasons[0] if scan.reasons else "UNKNOWN"))
        base["stages_completed"].append("01_SCANNER")
        setup = evaluate_setup(
            symbol=receipt_record["symbol"], klines=raw, market=item.market,
            received_at=instant(receipt_record["parent"]["available_at"], "PARENT_AVAILABLE"),
            decision_at=decision, partition=partition,
        )
        if (setup["status"] not in ("RESEARCH_CANDIDATE", "DETECTED_SIGNAL")
                or setup["score"] is not None or setup["publishable"]
                or setup["qualified"]):
            raise ChainRejected("STAGE02_UNAUTHORIZED_PROMOTION")
        # A RESEARCH_CANDIDATE can also be a REJECTED setup observation.
        # Only the explicitly classified normal nontrigger / causal-trigger
        # cases may traverse the 02→03 edge; never a timing/source reject.
        accepted_setup_reasons = {
            "CLOSED_CAUSAL_TRIGGER", "NO_BREAKOUT",
            "NO_FALSE_TO_TRUE_TRANSITION",
        }
        if (len(setup["reason_codes"]) != 1 or
                setup["reason_codes"][0] not in accepted_setup_reasons):
            raise ChainRejected("STAGE02_FAIL_CLOSED:" +
                                setup["reason_codes"][0])
        base["stages_completed"].append("02_SETUP_V1_1_INTERNAL_CANDIDATE")
        research = stage03_c1c4_research_from_closed_receipts(receipt_record)
        if research["status"] != "RESEARCH_CANDIDATE":
            raise ChainRejected("STAGE03_RESEARCH_REJECTED:" +
                                (research["rejection_reasons"][0]
                                 if research["rejection_reasons"] else "UNKNOWN"))
        if (research["score"] is not None or research["signal_id"] is not None
                or research["publishable"] or research["delivery_authorized"]):
            raise ChainRejected("STAGE03_PRODUCTION_BOUNDARY_VIOLATION")
        n03 = next(row for row in research["component_rows"]
                   if row["indicator"] == "N03")
        if n03["status"] != "UNAVAILABLE" or n03["value"] is not None:
            raise ChainRejected("N03_NUMERIC_UNAUTHORIZED")
        if any(row["approved_mapping"] is not None
               for row in research["semantic_decisions"]):
            raise ChainRejected("SEM_NUMERIC_MAPPING_UNAUTHORIZED")
        base["stages_completed"].append("03_RESEARCH_COMPONENT_LEDGER")
        base.update(
            status="RESEARCH_ONLY_READY_FOR_LOCAL_APPLICATION_JOURNAL",
            source_sha256=source_digest,
            source_id=source_id,
            symbol=receipt_record["symbol"],
            decision_at=decision.isoformat(),
            stage01_status=scan.status,
            stage02_status=setup["status"],
            stage02_internal_event_id=setup["event_id"],
            stage02_row_key=setup["row_key"],
            stage02_input_sha256=setup["input_sha256"],
            stage03_packet_sha256=research["packet_sha256"],
            stage03_status=research["status"],
            stage03_n03_status=n03["status"],
            stage03_n03_reason_codes=n03["reason_codes"],
            stage03_semantic_mapping="FOUR_UNMAPPED_SCOPED_NON_EQUIVALENCE",
        )
    except (ChainRejected, KeyError, TypeError, ValueError, IndexError,
            ArithmeticError) as exc:
        reason = str(exc) if isinstance(exc, ChainRejected) else "SOURCE_SCHEMA_OR_NUMERIC_INVALID"
        base["rejection_reasons"] = [reason]
    return base


class LocalChainJournal:
    """Windows-compatible application SQLite readback, not GitHub or WORM."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connection()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS chain_receipts(
                identity TEXT PRIMARY KEY,
                digest TEXT NOT NULL,
                payload BLOB NOT NULL)""")
            db.commit()

    def _connection(self):
        db = sqlite3.connect(str(self.path), timeout=3)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA busy_timeout=3000")
        return db

    def read_verified(self, identity):
        with closing(self._connection()) as db:
            row = db.execute("SELECT digest,payload FROM chain_receipts WHERE identity=?",
                             (identity,)).fetchone()
        if row is None:
            raise ChainRejected("LOCAL_READBACK_MISSING")
        digest, raw = row
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ChainRejected("LOCAL_PAYLOAD_DIGEST_MISMATCH")
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ChainRejected("LOCAL_PAYLOAD_INVALID") from exc
        if (payload.get("schema") != SCHEMA or payload.get("signal_id") is not None
                or payload.get("publishable") or payload.get("qualified")):
            raise ChainRejected("LOCAL_RESEARCH_ONLY_INVARIANT_FAILED")
        return payload

    def append_readback(self, value):
        if (value.get("status") != "RESEARCH_ONLY_READY_FOR_LOCAL_APPLICATION_JOURNAL"
                or value.get("signal_id") is not None or value.get("score") is not None
                or value.get("publishable") or value.get("delivery_authorized")):
            raise ChainRejected("LOCAL_JOURNAL_RESEARCH_ONLY_REQUIRED")
        identity = fingerprint({
            "source_id": value["source_id"], "symbol": value["symbol"],
            "decision_at": value["decision_at"],
        })
        raw = canonical(value)
        digest = hashlib.sha256(raw).hexdigest()
        if len(raw) > 131072:
            raise ChainRejected("LOCAL_RECORD_TOO_LARGE")
        with closing(self._connection()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute("INSERT INTO chain_receipts(identity,digest,payload) VALUES(?,?,?)",
                           (identity, digest, raw))
                db.commit()
                outcome = "LOCAL_SQLITE_COMMITTED_READBACK"
            except sqlite3.IntegrityError:
                db.rollback()
                outcome = "LOCAL_SQLITE_DUPLICATE_IDENTICAL"
            except BaseException:
                db.rollback()
                raise
        if self.read_verified(identity) != value:
            raise ChainRejected("LOCAL_DUPLICATE_CONFLICT_OR_READBACK_FAILURE")
        return identity, outcome

    def backup_restore_verify(self, destination):
        destination = Path(destination)
        if destination.exists() or destination.resolve() == self.path.resolve():
            raise ChainRejected("RESTORE_REQUIRES_DISTINCT_NEW_PATH")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connection()) as source, closing(sqlite3.connect(str(destination))) as target:
            source.backup(target)
        restored = LocalChainJournal(destination)
        with closing(self._connection()) as original:
            keys = [row[0] for row in original.execute("SELECT identity FROM chain_receipts ORDER BY identity")]
            check = original.execute("PRAGMA integrity_check").fetchone()[0]
        with closing(restored._connection()) as copy:
            copy_keys = [row[0] for row in copy.execute("SELECT identity FROM chain_receipts ORDER BY identity")]
            copy_check = copy.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok" or copy_check != "ok" or keys != copy_keys:
            raise ChainRejected("LOCAL_RESTORE_STRUCTURE_MISMATCH")
        if [self.read_verified(k) for k in keys] != [restored.read_verified(k) for k in keys]:
            raise ChainRejected("LOCAL_RESTORE_CONTENT_MISMATCH")
        return {"status": "LOCAL_SQLITE_APPLICATION_RESTORE_VERIFIED",
                "rows": len(keys), "payload_set_sha256": fingerprint(
                    [self.read_verified(k) for k in keys]),
                "owner_device_reboot_verified": False,
                "github_writer_verified_here": False,
                "production_custody_verified": False}


def persist_offline_chain(*, receipt_record, exchange_info, journal_path):
    result = chain_result(receipt_record=receipt_record, exchange_info=exchange_info)
    if result["status"] != "RESEARCH_ONLY_READY_FOR_LOCAL_APPLICATION_JOURNAL":
        return result
    journal = LocalChainJournal(journal_path)
    identity, outcome = journal.append_readback(result)
    return {**result, "stage04_store": outcome, "stage04_identity": identity,
            "stage04_readback_sha256": fingerprint(journal.read_verified(identity)),
            "stages_completed": [*result["stages_completed"], "04_LOCAL_SQLITE_APPLICATION_READBACK"]}
