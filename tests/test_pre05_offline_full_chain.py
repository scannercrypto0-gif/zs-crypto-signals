"""Targeted NEW cross-edge tests only; never rerun accepted 00/03/04 suites.

Fixture uses the very same 5m source rows for scanner, frozen Setup, 03A/R2.
GitHub transport is NOT used. SQLite is real local application storage.
"""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import sqlite3
import subprocess
import sys
import unittest

from test_stage03_r2_offline import intraday
from test_stage03_r2_functional import stage03_inputs
from test_stage03_r2_closed_bundle import sample
from test_stage03_r2_receipt_bundle import _record

from zs_smart_gate.pre05_offline_chain import (
    LocalChainJournal, ChainRejected, chain_result, persist_offline_chain,
)


def one_source(symbol="BTCUSDT", *, breakout=True):
    original = intraday()
    stage03 = _record(sample(original, stage03_inputs(original)))
    stage03["symbol"] = symbol
    stage03["book"]["symbol"] = symbol
    stage03["ticker24"]["symbol"] = symbol
    stage03["ticker24"]["payload"]["symbol"] = symbol

    # The final 5m bar is modified IN ALL three representations, and the
    # original 30m parent is reconciled from the same six source children.
    if breakout:
        final = stage03["children"][-1]
        final["high"] = "112"
        final["close"] = "111"
        final["quote_volume"] = "1300"
        stage03["core_5m"][-1] = deepcopy(final)
        parent = stage03["parent"]
        parent["high"] = "112"
        parent["close"] = "111"
        parent["quote_volume"] = str(sum(
            __import__("decimal").Decimal(x["quote_volume"])
            for x in stage03["children"]
        ))
    exchange = {"symbols": [{
        "symbol": symbol, "quoteAsset": "USDT", "status": "TRADING",
        "isSpotTradingAllowed": True,
    }]}
    return stage03, exchange


def change_child(record, index, field, value):
    record["children"][index][field] = value
    record["core_5m"][-6:][index][field] = value


def duplicate_context_bar(record):
    record["context"]["5m"][-1] = deepcopy(record["context"]["5m"][-2])
    record["core_5m"][14] = deepcopy(record["context"]["5m"][-1])


class Pre05SingleSourceTargeted(unittest.TestCase):

    def test_same_22_bar_source_btc_eth_through_00_04_local_readback(self):
        with TemporaryDirectory(prefix="pre05-local-") as root:
            path = Path(root) / "evidence.sqlite"
            journal = LocalChainJournal(path)
            seen = []
            for symbol in ("BTCUSDT", "ETHUSDT"):
                with self.subTest(symbol=symbol):
                    record, exchange = one_source(symbol)
                    row = persist_offline_chain(
                        receipt_record=record, exchange_info=exchange,
                        journal_path=path,
                    )
                    self.assertEqual(
                        row["status"],
                        "RESEARCH_ONLY_READY_FOR_LOCAL_APPLICATION_JOURNAL",
                        row["rejection_reasons"],
                    )
                    self.assertEqual(row["stage01_status"], "PASS")
                    self.assertEqual(row["stage02_status"], "DETECTED_SIGNAL")
                    self.assertIsNotNone(row["stage02_internal_event_id"])
                    self.assertEqual(row["stage03_status"], "RESEARCH_CANDIDATE")
                    self.assertEqual(row["stage03_n03_status"], "UNAVAILABLE")
                    self.assertEqual(row["stage03_semantic_mapping"],
                                     "FOUR_UNMAPPED_SCOPED_NON_EQUIVALENCE")
                    self.assertEqual(len(row["stages_completed"]), 6)
                    self.assertEqual(row["stage04_store"],
                                     "LOCAL_SQLITE_COMMITTED_READBACK")
                    self.assertIsNone(row["signal_id"])
                    self.assertIsNone(row["score"])
                    self.assertFalse(row["publishable"])
                    self.assertFalse(row["delivery_authorized"])
                    self.assertEqual(row["market_requests"], 0)
                    self.assertEqual(row["external_sends"], 0)
                    saved = journal.read_verified(row["stage04_identity"])
                    self.assertEqual(saved["source_sha256"], row["source_sha256"])
                    self.assertEqual(saved["stage03_packet_sha256"],
                                     row["stage03_packet_sha256"])
                    self.assertEqual(saved["stage02_row_key"], row["stage02_row_key"])
                    seen.append(row["stage04_identity"])

            report = journal.backup_restore_verify(Path(root) / "restore.sqlite")
            self.assertEqual(report["status"],
                             "LOCAL_SQLITE_APPLICATION_RESTORE_VERIFIED")
            self.assertEqual(report["rows"], 2)
            self.assertEqual(len(set(seen)), 2)
            self.assertFalse(report["owner_device_reboot_verified"])
            self.assertFalse(report["github_writer_verified_here"])

    def test_missing_future_stale_mixed_duplicate_and_exchange_reject(self):
        base, exchange = one_source()
        from copy import deepcopy
        from datetime import datetime
        with TemporaryDirectory(prefix="pre05-negative-") as root:
            db = Path(root) / "rejected.sqlite"
            cases = (
                ("missing_base",
                 lambda d, e: (d["children"][-1].pop("base_volume"),
                               d["core_5m"][-1].pop("base_volume")),
                 "ORIGINAL_DECIMAL_STRING_REQUIRED:base_volume"),
                ("future_available",
                 lambda d, e: change_child(
                     d, -1, "available_at", "2099-01-01T00:00:00+00:00"),
                 "SOURCE_5M_GAP_FUTURE_OR_UNCLOSED"),
                ("source_mismatch",
                 lambda d, e: change_child(
                     d, 1, "source_id", "SYNTHETIC:FOREIGN"),
                 "SOURCE_ID_OR_FRAME_CONFLICT"),
                ("duplicate_bar",
                 lambda d, e: duplicate_context_bar(d),
                 "SOURCE_5M_GAP_FUTURE_OR_UNCLOSED"),
                ("non_utc",
                 lambda d, e: d["parent"].__setitem__(
                     "close_at", "2026-06-03T03:00:00+03:00"),
                 "EXPLICIT_UTC_REQUIRED:PARENT_CLOSE"),
                ("stale_receipt",
                 lambda d, e: d.__setitem__(
                     "decision_at",
                     (datetime.fromisoformat(d["decision_at"]) +
                      timedelta(minutes=3)).isoformat()),
                 "STAGE02_FAIL_CLOSED:STALE_OBSERVATION"),
                ("missing_exchange",
                 lambda d, e: e["symbols"].clear(),
                 "STAGE00_EXCHANGE_IDENTITY_MISSING"),
                ("foreign_book_symbol",
                 lambda d, e: d["book"].__setitem__(
                     "symbol", "FOREIGNUSDT"),
                 "MARKET_SYMBOL_OR_ENDPOINT_CONFLICT"),
                ("incomplete_child",
                 lambda d, e: change_child(
                     d, -1, "close_at", d["children"][-1]["open_at"]),
                 "SOURCE_5M_GAP_FUTURE_OR_UNCLOSED"),
            )
            for label, mutate, expected in cases:
                with self.subTest(case=label):
                    rec, ex = deepcopy(base), deepcopy(exchange)
                    mutate(rec, ex)
                    out = persist_offline_chain(
                        receipt_record=rec, exchange_info=ex,
                        journal_path=db)
                    self.assertEqual(out["status"], "REJECTED",
                                     (label, out["rejection_reasons"]))
                    self.assertTrue(out["rejection_reasons"])
                    self.assertIn(expected, out["rejection_reasons"][0])
                    self.assertNotIn("stage04_identity", out)
                    self.assertEqual(out["stage04_store"], "NOT_ATTEMPTED")
                    self.assertIsNone(out["score"])
                    self.assertIsNone(out["signal_id"])
            self.assertFalse(db.exists(), "Rejects must not create a durable claim")

    def test_duplicate_conflict_tamper_and_independent_process_reopen(self):
        with TemporaryDirectory(prefix="pre05-recovery-") as root:
            path = Path(root) / "evidence.sqlite"
            record, exchange = one_source()
            first = persist_offline_chain(
                receipt_record=record, exchange_info=exchange,
                journal_path=path)
            second = persist_offline_chain(
                receipt_record=deepcopy(record), exchange_info=deepcopy(exchange),
                journal_path=path)
            self.assertEqual(second["stage04_store"],
                             "LOCAL_SQLITE_DUPLICATE_IDENTICAL")
            identity = first["stage04_identity"]
            # Separate Windows Python process, not merely the same object.
            child = (
                "import json,sys;"
                "from zs_smart_gate.pre05_offline_chain import LocalChainJournal;"
                "x=LocalChainJournal(sys.argv[1]).read_verified(sys.argv[2]);"
                "print(json.dumps({'status':x['status'],"
                "'source_sha256':x['source_sha256']}))"
            )
            done = subprocess.run(
                [sys.executable, "-c", child, str(path), identity],
                capture_output=True, text=True, timeout=20, check=True,
                env=os.environ.copy(),
            )
            restored = json.loads(done.stdout)
            self.assertEqual(restored["source_sha256"], first["source_sha256"])
            self.assertEqual(
                restored["status"],
                "RESEARCH_ONLY_READY_FOR_LOCAL_APPLICATION_JOURNAL",
            )
            # Same identity but altered input MUST be rejected, not overwritten.
            altered = deepcopy(record)
            altered["ticker24"]["payload"]["quoteVolume"] = "21000000"
            with self.assertRaisesRegex(ChainRejected,
                                        "LOCAL_DUPLICATE_CONFLICT_OR_READBACK_FAILURE"):
                persist_offline_chain(receipt_record=altered,
                                      exchange_info=exchange, journal_path=path)
            with sqlite3.connect(path) as db:
                db.execute("UPDATE chain_receipts SET payload=? WHERE identity=?",
                           (b'{"tampered":true}', identity))
            with self.assertRaisesRegex(ChainRejected,
                                        "LOCAL_PAYLOAD_DIGEST_MISMATCH"):
                LocalChainJournal(path).read_verified(identity)
