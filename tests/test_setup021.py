"""ORDER-021 offline only: real accepted parser/scanner/core + frozen setup v1."""
import copy
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
import json
import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from zs_smart_gate.setup021 import CONFIG, CONFIG_SHA256, VERSION, digest, evaluate
from zs_smart_gate.setup021_fixtures import scenario
from zs_smart_gate.setup021_store import ResearchStoreError, SQLiteResearchJournal


DEV = "2026-09-01T00:00:00Z"
OOS = "2026-10-01T00:00:00Z"


def sample(when=DEV, *, symbol="BTCUSDT", breakout=True, partition="DEV", **changes):
    data = scenario(when, symbol=symbol, breakout=breakout, **changes)
    return evaluate(**data, partition=partition)


class Setup021ContractTests(unittest.TestCase):
    def test_frozen_predeclared_setup(self):
        self.assertEqual(CONFIG["lookback_closed_bars"], 20)
        self.assertEqual(CONFIG["quote_volume_factor"], "1.20")
        self.assertEqual(CONFIG["direction"], "UP")
        self.assertEqual(CONFIG["max_market_snapshot_age_seconds"], 90)
        self.assertEqual(VERSION, "ORDER021_SETUP_V1_1_FROZEN")
        self.assertEqual(CONFIG_SHA256, digest(CONFIG))

    def test_actual_parser_scanner_core_positive(self):
        a = sample()
        self.assertEqual(a["status"], "DETECTED_SIGNAL")
        self.assertEqual(a["core_status"], "PASS")
        self.assertFalse(a["previous_condition"])
        self.assertTrue(a["current_condition"])
        self.assertTrue(a["event_id"])
        self.assertFalse(a["qualified"])
        self.assertFalse(a["publishable"])
        self.assertIsNone(a["score"])
        self.assertEqual(a["score_status"], "SCORE_UNAVAILABLE")
        self.assertEqual(a["historical_pit"], "HISTORICAL_PIT_UNVERIFIED")

    def test_non_breakout_is_candidate_not_detection(self):
        self.assertEqual(sample(breakout=False)["status"], "RESEARCH_CANDIDATE")

    def test_event_identity_stable_under_replay(self):
        one, two = sample(), sample()
        self.assertEqual(one["event_id"], two["event_id"])
        self.assertEqual(one["row_key"], two["row_key"])

    def test_distinct_closed_event_has_distinct_identity(self):
        one, two = sample(), sample("2026-09-02T00:00:00Z")
        self.assertNotEqual(one["event_id"], two["event_id"])

    def test_open_candle_never_backfills_prior_as_current(self):
        a = sample(forming=True)
        self.assertEqual(a["status"], "RESEARCH_CANDIDATE")
        self.assertIn("FORMING_OR_FUTURE_OR_NOT_YET_RECEIVED", a["reason_codes"])

    def test_delayed_receipt_explicitly_stale(self):
        self.assertEqual(sample(delayed=True)["reason_codes"], ["STALE_OBSERVATION"])

    def test_missing_bar_refuses_to_infer(self):
        self.assertEqual(sample(missing=True)["status"], "RESEARCH_CANDIDATE")

    def test_gap_in_closed_5m_window_rejected(self):
        x = scenario(DEV)
        x["klines"][10][0] += 300000
        x["klines"][10][6] += 300000
        a = evaluate(**x, partition="DEV")
        self.assertEqual(a["status"], "RESEARCH_CANDIDATE")
        self.assertIn("INVALID_CANDLE_WINDOW", a["reason_codes"])

    def test_market_snapshot_future_rejected_by_existing_core(self):
        x = scenario(DEV)
        x["market"] = replace(x["market"], observed_at=x["decision_at"] + timedelta(seconds=1))
        a = evaluate(**x, partition="DEV")
        self.assertEqual(a["status"], "RESEARCH_CANDIDATE")
        self.assertIn("SCANNER_OR_CORE_REJECTED", a["reason_codes"])

    def test_old_true_to_new_true_is_not_new_detection(self):
        x = scenario(DEV)
        x["klines"][20][2], x["klines"][20][4], x["klines"][20][7] = "112", "111", "1300"
        x["klines"][21][2], x["klines"][21][4], x["klines"][21][7] = "115", "114", "1300"
        a = evaluate(**x, partition="DEV")
        self.assertTrue(a.get("previous_condition"))
        self.assertTrue(a.get("current_condition"))
        self.assertEqual(a["status"], "RESEARCH_CANDIDATE")
        self.assertEqual(a["reason_codes"], ["NO_FALSE_TO_TRUE_TRANSITION"])

    def test_low_volume_is_not_made_zero_or_detected(self):
        x = scenario(DEV)
        x["klines"][-1][7] = "1199"
        a = evaluate(**x, partition="DEV")
        self.assertEqual(a["status"], "RESEARCH_CANDIDATE")

    def test_quote_volume_zero_baseline_rejected(self):
        x = scenario(DEV)
        for row in x["klines"][:-1]:
            row[7] = "0"
        a = evaluate(**x, partition="DEV")
        self.assertEqual(a["status"], "RESEARCH_CANDIDATE")
        self.assertEqual(a["reason_codes"][:2], ["SCANNER_OR_CORE_REJECTED", "MISSING_RVOL_BASE_OR_QUOTE"])

    def test_independent_incomplete_source_rows_have_distinct_keys(self):
        # Missing last candle timestamps must never collapse all rejected rows
        # for a symbol into one row_key=sha256(version+symbol+null).
        x = scenario(DEV)
        first = copy.deepcopy(x)
        first["klines"].pop(12)
        second = copy.deepcopy(x)
        second["klines"].pop(13)
        a, b = (evaluate(**item, partition="DEV") for item in (first, second))
        self.assertEqual(a["status"], "RESEARCH_CANDIDATE")
        self.assertEqual(b["status"], "RESEARCH_CANDIDATE")
        self.assertNotEqual(a["input_sha256"], b["input_sha256"])
        self.assertNotEqual(a["row_key"], b["row_key"])
        with tempfile.TemporaryDirectory() as d:
            store = SQLiteResearchJournal(Path(d) / "db.sqlite")
            self.assertEqual(store.append_readback(a), "COMMITTED_AND_READBACK_VERIFIED")
            self.assertEqual(store.append_readback(b), "COMMITTED_AND_READBACK_VERIFIED")
            self.assertEqual(len(store.rows()), 2)

    def test_invalid_last_timestamp_rows_are_distinct_candidates(self):
        x, y = scenario(DEV), scenario(DEV)
        x["klines"][-1][0] = "bad-open"
        y["klines"][-1][0] = "different-bad-open"
        a, b = evaluate(**x, partition="DEV"), evaluate(**y, partition="DEV")
        self.assertEqual(a["reason_codes"], ["INVALID_LAST_KLINE_TIMESTAMP"])
        self.assertEqual(b["reason_codes"], ["INVALID_LAST_KLINE_TIMESTAMP"])
        self.assertNotEqual(a["row_key"], b["row_key"])
        self.assertIsNone(a["event_id"])

    def test_bad_22_row_schema_is_sanitized_candidate_not_exception(self):
        x = scenario(DEV)
        x["klines"][7] = ["truncated"]
        a = evaluate(**x, partition="DEV")
        self.assertEqual(a["status"], "RESEARCH_CANDIDATE")
        self.assertEqual(a["reason_codes"], ["PARSER_OR_PREDICATE_REJECTED", "KLINES_SCHEMA"])
        self.assertEqual(len(a["input_sha256"]), 64)
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(SQLiteResearchJournal(Path(d) / "db.sqlite").append_readback(a),
                             "COMMITTED_AND_READBACK_VERIFIED")

    def test_bad_numeric_kline_field_is_nonfatal_and_redacted(self):
        x = scenario(DEV)
        x["klines"][5][4] = "definitely-not-a-price"
        a = evaluate(**x, partition="DEV")
        self.assertEqual(a["status"], "RESEARCH_CANDIDATE")
        self.assertEqual(a["reason_codes"], ["PARSER_OR_PREDICATE_REJECTED", "INVALID_KLINE_FIELDS"])
        self.assertNotIn("definitely-not-a-price", str(a))

    def test_stale_market_snapshot_rejected_at_declared_90s_limit(self):
        x = scenario(DEV)
        x["market"] = replace(x["market"], observed_at=x["decision_at"] - timedelta(days=2))
        a = evaluate(**x, partition="DEV")
        self.assertEqual(a["status"], "RESEARCH_CANDIDATE")
        self.assertEqual(a["reason_codes"], ["MARKET_SNAPSHOT_STALE"])
        self.assertEqual(a["market_observed_at"], x["market"].observed_at.isoformat())
        # Exact boundary is allowed, and no price/volume thresholds changed.
        x["market"] = replace(x["market"], observed_at=x["decision_at"] - timedelta(seconds=90))
        self.assertEqual(evaluate(**x, partition="DEV")["status"], "DETECTED_SIGNAL")

    def test_input_and_decision_evidence_changes_for_same_event(self):
        x = scenario(DEV)
        one = evaluate(**x, partition="DEV")
        y = copy.deepcopy(x)
        y["klines"][3][5] = "11"  # volume input differs, trigger identity unchanged
        two = evaluate(**y, partition="DEV")
        self.assertEqual(one["status"], "DETECTED_SIGNAL")
        self.assertEqual(two["status"], "DETECTED_SIGNAL")
        self.assertEqual(one["row_key"], two["row_key"])
        self.assertEqual(one["event_id"], two["event_id"])
        self.assertNotEqual(one["input_sha256"], two["input_sha256"])
        self.assertEqual(one["received_at"], x["received_at"].isoformat())
        self.assertEqual(one["decision_at"], x["decision_at"].isoformat())
        self.assertEqual(one["market_observed_at"], x["market"].observed_at.isoformat())
        with tempfile.TemporaryDirectory() as d:
            store = SQLiteResearchJournal(Path(d) / "db.sqlite")
            store.append_readback(one)
            with self.assertRaisesRegex(ResearchStoreError, "DUPLICATE_CONFLICT"):
                store.append_readback(two)
        z = copy.deepcopy(x)
        z["decision_at"] += timedelta(seconds=1)
        self.assertNotEqual(one["input_sha256"], evaluate(**z, partition="DEV")["input_sha256"])

    def test_partition_oos_no_retuning_and_no_probability(self):
        a = sample(OOS, partition="OOS")
        self.assertEqual(a["contract_sha256"], CONFIG_SHA256)
        self.assertEqual(a["status"], "DETECTED_SIGNAL")
        self.assertEqual(a["partition"], "OOS")
        self.assertIsNone(a["probability"])

    def test_prospective_not_admitted_by_synthetic_replay(self):
        with self.assertRaisesRegex(ValueError, "PARTITION_UNAUTHORIZED"):
            evaluate(**scenario(DEV), partition="PROSPECTIVE")

    def test_symbol_outside_scope_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(**scenario(DEV, symbol="SOLUSDT"), partition="DEV")

    def test_no_network_used_by_offline_pipeline(self):
        with patch("socket.socket", side_effect=AssertionError("NO_SOCKETS_FOR_ORDER021")):
            with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP_FOR_ORDER021")):
                self.assertEqual(sample()["status"], "DETECTED_SIGNAL")

    def test_old_data_read_after_decision_is_not_admitted(self):
        x = scenario(DEV)
        x["decision_at"] = x["received_at"] - timedelta(microseconds=1)
        self.assertEqual(evaluate(**x, partition="DEV")["status"], "RESEARCH_CANDIDATE")


class Setup021StorageTests(unittest.TestCase):
    def test_full_write_readback_independent_restore(self):
        with tempfile.TemporaryDirectory() as d:
            db = SQLiteResearchJournal(Path(d) / "original.sqlite")
            a = sample()
            self.assertEqual(db.append_readback(a), "COMMITTED_AND_READBACK_VERIFIED")
            self.assertEqual(db.read_verified(a["row_key"]), a)
            r = db.backup_and_restore_verify(Path(d) / "other.sqlite")
            self.assertEqual(r["rows"], 1)
            self.assertEqual(r["status"], "OFFLINE_BACKUP_RESTORED_VERIFIED")
            self.assertFalse(r["native_owner_windows_proven"])

    def test_duplicate_idempotence_and_distinct_event(self):
        with tempfile.TemporaryDirectory() as d:
            db = SQLiteResearchJournal(Path(d) / "db.sqlite")
            a = sample()
            self.assertEqual(db.append_readback(a), "COMMITTED_AND_READBACK_VERIFIED")
            self.assertEqual(db.append_readback(a), "DUPLICATE_READBACK_CONFIRMED")
            b = sample("2026-09-02T00:00:00Z")
            self.assertEqual(db.append_readback(b), "COMMITTED_AND_READBACK_VERIFIED")
            self.assertEqual(len(db.rows()), 2)

    def test_conflicting_duplicate_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            db = SQLiteResearchJournal(Path(d) / "db.sqlite")
            a = sample()
            db.append_readback(a)
            b = copy.deepcopy(a)
            b["row_key"] = "f" * 64
            with self.assertRaises(ResearchStoreError):
                db.append_readback(b)

    def test_tampered_payload_readback_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "db.sqlite"
            db = SQLiteResearchJournal(p)
            a = sample()
            db.append_readback(a)
            with closing(sqlite3.connect(str(p))) as con:
                con.execute("UPDATE research_rows SET payload=? WHERE row_key=?", (b'{"false":true}', a["row_key"]))
                con.commit()
            with self.assertRaisesRegex(ResearchStoreError, "READBACK_HASH"):
                db.read_verified(a["row_key"])

    def test_reopen_after_interruption_keeps_dedup(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "db.sqlite"
            a = sample()
            SQLiteResearchJournal(p).append_readback(a)
            again = SQLiteResearchJournal(p)
            self.assertEqual(again.append_readback(a), "DUPLICATE_READBACK_CONFIRMED")

    def test_missing_source_backup_prohibition(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "db.sqlite"
            db = SQLiteResearchJournal(p)
            with self.assertRaises(ResearchStoreError):
                db.backup_and_restore_verify(p)

    def test_one_dev_one_oos_not_accidentally_combined(self):
        with tempfile.TemporaryDirectory() as d:
            db = SQLiteResearchJournal(Path(d) / "db.sqlite")
            a, b = sample(), sample(OOS, partition="OOS")
            db.append_readback(a)
            db.append_readback(b)
            rows = db.rows()
            self.assertEqual({x["partition"] for x in rows}, {"DEV", "OOS"})
            self.assertEqual(len({x["event_id"] for x in rows}), 2)

    def test_injected_sqlite_write_failure_cannot_be_reported_success(self):
        with tempfile.TemporaryDirectory() as d:
            db = SQLiteResearchJournal(Path(d) / "db.sqlite")
            with patch.object(db, "_connect", side_effect=sqlite3.OperationalError("injected storage unavailable")):
                with self.assertRaises(sqlite3.OperationalError):
                    db.append_readback(sample())

    def test_storage_rejects_scientific_promotion_flag_spoofing(self):
        for status_case in ("DETECTED_SIGNAL", "RESEARCH_CANDIDATE"):
            base = sample() if status_case == "DETECTED_SIGNAL" else sample(breakout=False)
            changes = (
                ("publishable", True),
                ("qualified", True),
                ("score", 99),
                ("probability", 0.99),
                ("score_status", "SCORE_AVAILABLE"),
                ("historical_pit", "PIT_VERIFIED"),
                ("contract_version", "SPOOFED_CONTRACT"),
                ("source", "OTHER_SOURCE"),
            )
            with tempfile.TemporaryDirectory() as d:
                db = SQLiteResearchJournal(Path(d) / "db.sqlite")
                for key, val in changes:
                    with self.subTest(status=status_case, field=key):
                        tampered = copy.deepcopy(base)
                        tampered[key] = val
                        with self.assertRaisesRegex(ResearchStoreError, "RESEARCH_ONLY_INVARIANT"):
                            db.append_readback(tampered)
                self.assertEqual(db.rows(), [])

    def test_missing_input_or_receipt_evidence_refused(self):
        with tempfile.TemporaryDirectory() as d:
            db = SQLiteResearchJournal(Path(d) / "db.sqlite")
            for key, val, expected in (
                ("input_sha256", "0", "INPUT_FINGERPRINT_REQUIRED"),
                ("received_at", None, "DECISION_TIMING_EVIDENCE_REQUIRED"),
                ("decision_at", "not-a-date", "DECISION_TIMING_EVIDENCE_INVALID"),
                ("market_observed_at", "2026-11-05T12:00:00", "DECISION_TIMING_EVIDENCE_INVALID"),
            ):
                with self.subTest(field=key):
                    obj = sample()
                    obj[key] = val
                    with self.assertRaisesRegex(ResearchStoreError, expected):
                        db.append_readback(obj)

    def test_storage_rejects_spoofed_qualified_or_foreign_contract(self):
        with tempfile.TemporaryDirectory() as d:
            db = SQLiteResearchJournal(Path(d) / "db.sqlite")
            a = sample()
            a["status"] = "QUALIFIED_SIGNAL"
            with self.assertRaises(ResearchStoreError):
                db.append_readback(a)
            a = sample()
            a["contract_sha256"] = "a"*64
            with self.assertRaises(ResearchStoreError):
                db.append_readback(a)


if __name__ == "__main__":
    unittest.main()
