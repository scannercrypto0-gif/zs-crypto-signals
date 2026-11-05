"""ORDER-025 deterministic, offline-only historical replay audit regressions.

This does not modify Setup v1.1, scientific thresholds, or any real archives.
All inputs are synthetic; tests establish algorithmic invariants, not edge.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import tempfile
from pathlib import Path
import unittest

from zs_smart_gate.setup021 import CONFIG_SHA256, VERSION
from zs_smart_gate.stage03_order022 import (
    Bar, INTERVAL_MS, ONE_HOUR_BARS, SQLiteHistoricalEvidence,
    evaluate_rows, phase_for, read_protocol,
)


def millisecond(iso):
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def candles(start_iso, length=72, triggers=()):
    """Base bars are flat; explicit 3 spikes are valid independent breakouts."""
    base = millisecond(start_iso)
    spikes = {25: (Decimal(112), Decimal(111)),
              30: (Decimal(122), Decimal(121)),
              43: (Decimal(132), Decimal(131))}
    result = []
    for i in range(length):
        start = base + INTERVAL_MS * i
        high, close = spikes.get(i, (Decimal(101), Decimal(100)))
        quote = Decimal(1300) if i in triggers else Decimal(1000)
        result.append(Bar(
            start, start + INTERVAL_MS, Decimal(100),
            high if i in triggers else Decimal(101),
            Decimal(99), close if i in triggers else Decimal(100),
            Decimal(10), quote,
        ))
    return result


class FrozenProtocolRegression(unittest.TestCase):
    def setUp(self):
        self.protocol, self.protocol_sha = read_protocol()

    def test_exact_setup_v1_1_sha_and_partition_utc_boundaries(self):
        self.assertEqual(VERSION, "ORDER021_SETUP_V1_1_FROZEN")
        self.assertEqual(self.protocol["setup_contract_sha256"], CONFIG_SHA256)
        self.assertEqual(CONFIG_SHA256,
                         "0cb5f5aed50ac219d00188cca9827b26ab75dd15a9786773e683b40d10d818ce")
        p = self.protocol["partitions"]
        self.assertEqual(p["DEV"]["start_ms"], millisecond("2025-02-01T00:00:00Z"))
        self.assertEqual(p["DEV"]["end_exclusive_ms"], millisecond("2025-03-31T00:00:00Z"))
        self.assertEqual(p["OOS"]["start_ms"], millisecond("2025-04-02T00:00:00Z"))
        self.assertEqual(p["OOS"]["end_exclusive_ms"], millisecond("2025-07-01T00:00:00Z"))
        for t, partition in [
            ("2025-01-31T23:55:00Z", None),
            ("2025-02-01T00:00:00Z", "DEV"),
            ("2025-03-30T23:55:00Z", "DEV"),
            ("2025-03-31T00:00:00Z", None),
            ("2025-04-01T23:55:00Z", None),
            ("2025-04-02T00:00:00Z", "OOS"),
            ("2025-06-30T23:55:00Z", "OOS"),
            ("2025-07-01T00:00:00Z", None),
        ]:
            with self.subTest(t=t):
                self.assertEqual(phase_for(millisecond(t), self.protocol), partition)

    def test_three_triggers_inside_and_outside_12_bar_overlap(self):
        """25 and 30 trigger; 30 is suppressed; 43 admitted after embargo."""
        bars = candles("2025-02-01T00:00:00Z", triggers=(25, 30, 43))
        s, events = evaluate_rows(bars, "BTCUSDT", self.protocol, "SYNTHETIC_TEST")
        dev = s["DEV"]
        self.assertEqual(dev["partial_price_volume_patterns"], 3)
        self.assertEqual(dev["outcome_overlap_suppressed"], 1)
        self.assertEqual(len(events["DEV"]), 2)
        self.assertEqual(dev["observed_price_only_horizon_12"], 2)
        self.assertEqual([e["closed_candle_ms"] for e in events["DEV"]],
                         [bars[25].end, bars[43].end])
        self.assertEqual([e["future_price_label"] for e in events["DEV"]],
                         ["CLOSE_NOT_UP_12_BARS", "CLOSE_NOT_UP_12_BARS"])
        self.assertEqual(
            dev["partial_price_volume_patterns"] -
            dev["outcome_overlap_suppressed"], len(events["DEV"]))
        self.assertEqual(len(events["OOS"]), 0)
        self.assertTrue(all(e["label"] ==
                            "PARTIAL_PRICE_VOLUME_PATTERN_NOT_DETECTED_SIGNAL"
                            for e in events["DEV"]))
        self.assertTrue(all(e["core_spread_liquidity"] ==
                            "MISSING_HISTORICAL_BOOK_24H" for e in events["DEV"]))

    def test_identical_fixture_in_oos_has_independent_counter_and_event_keys(self):
        dev_bars = candles("2025-02-01T00:00:00Z", triggers=(25, 30, 43))
        oos_bars = candles("2025-04-02T00:00:00Z", triggers=(25, 30, 43))
        counts, events = evaluate_rows(dev_bars + oos_bars, "ETHUSDT",
                                       self.protocol, "SYNTHETIC_TEST")
        for phase in ("DEV", "OOS"):
            with self.subTest(phase=phase):
                self.assertEqual(counts[phase]["partial_price_volume_patterns"], 3)
                self.assertEqual(counts[phase]["outcome_overlap_suppressed"], 1)
                self.assertEqual(len(events[phase]), 2)
                self.assertEqual(counts[phase]["observed_price_only_horizon_12"], 2)
        self.assertTrue(set(e["event_key"] for e in events["DEV"]).isdisjoint(
            e["event_key"] for e in events["OOS"]))

    def test_12_bar_boundary_censors_future_without_looking_into_oos(self):
        # 51 5-minute bars up to the partition boundary: event at index 43
        # has 7 available bars, not 12; the forward label must be unavailable.
        start = "2025-03-30T19:45:00Z"
        bars = candles(start, length=51, triggers=(25, 43))
        s, events = evaluate_rows(bars, "BTCUSDT", self.protocol, "SYNTHETIC_TEST")
        self.assertEqual(s["DEV"]["partial_price_volume_patterns"], 2)
        self.assertEqual(len(events["DEV"]), 2)
        self.assertEqual(events["DEV"][1]["future_price_label"], "UNAVAILABLE")
        self.assertIsNone(events["DEV"][1]["future_close_delta_positive"])
        self.assertEqual(s["DEV"]["observed_price_only_horizon_12"], 1)
        self.assertEqual(s["DEV"]["future_bars_unavailable"], 1)

    def test_gap_rejects_cross_gap_windows_and_missing_future_label(self):
        bars = candles("2025-02-01T00:00:00Z", triggers=(25, 43))
        # Keep ordered complete records, but remove the twelfth forward bar
        # after event #25; the outcome must be UNKNOWN, never filled.
        broken = bars[:37] + bars[38:]
        s, events = evaluate_rows(broken, "BTCUSDT", self.protocol, "SYNTHETIC_TEST")
        self.assertGreater(s["DEV"]["gap_crossing_rejected"], 0)
        self.assertGreaterEqual(s["DEV"]["outcome_crosses_gap_or_partition"], 1)
        self.assertEqual(events["DEV"][0]["future_price_label"], "UNAVAILABLE")

    def test_replay_determinism_and_independent_sqlite_restore(self):
        bars = candles("2025-02-01T00:00:00Z", triggers=(25, 30, 43))
        a, ea = evaluate_rows(bars, "BTCUSDT", self.protocol, "SYNTHETIC_TEST")
        b, eb = evaluate_rows(list(bars), "BTCUSDT", self.protocol, "SYNTHETIC_TEST")
        self.assertEqual(a, b)
        self.assertEqual(ea, eb)
        with tempfile.TemporaryDirectory() as folder:
            source = SQLiteHistoricalEvidence(Path(folder) / "journal.sqlite")
            source.put("BTCUSDT:DEV", dict(a["DEV"]))
            source.put("BTCUSDT:DEV", dict(a["DEV"]))
            with self.assertRaisesRegex(Exception, "IMMUTABLE_REPORT_CONFLICT"):
                source.put("BTCUSDT:DEV", {"tamper": True})
            restored = source.backup_check(Path(folder) / "independent.sqlite")
            self.assertEqual(restored["status"], "READBACK_RESTORED_OFFLINE")
            self.assertEqual(restored["restored_rows"], 1)
            self.assertEqual(
                source.get("BTCUSDT:DEV"),
                SQLiteHistoricalEvidence(Path(folder) / "independent.sqlite")
                .get("BTCUSDT:DEV"))


if __name__ == "__main__":
    unittest.main()
