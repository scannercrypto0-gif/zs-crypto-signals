"""Offline qualification integration: actual 01/03A/03B1 contracts, no network."""
from __future__ import annotations

import dataclasses
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from zs_smart_gate.core import Candle, MarketSnapshot
from zs_smart_gate.mtf_contracts import CandleWindow, ReconciliationTolerance
from zs_smart_gate.stage03a_contracts import Direction, Horizon, ResearchKeyRegistry
from zs_smart_gate.stage03_qualification_readiness import assess_readiness


UTC = timezone.utc
START = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)
EXACT = ReconciliationTolerance("0", "0", "0", "SAME_SOURCE_EXACT_FIXTURE_ONLY")


def setup(horizon, direction=Direction.UP):
    frame, childframe, count, mins = (
        ("30m", "5m", 6, 5) if horizon is Horizon.INTRADAY
        else ("4h", "1h", 4, 60))
    close = START + timedelta(minutes=count * mins)
    child = [
        CandleWindow(childframe, START+timedelta(minutes=i*mins),
                     START+timedelta(minutes=(i+1)*mins),
                     close+timedelta(seconds=1), close+timedelta(seconds=1),
                     "SYNTHETIC:SAME_SOURCE", "100", "102", "99", "101",
                     "10", "1000") for i in range(count)
    ]
    parent = CandleWindow(frame, START, close, close+timedelta(seconds=2),
                          close+timedelta(seconds=2), "SYNTHETIC:SAME_SOURCE",
                          "100", "102", "99", "101", str(count*10), str(count*1000))
    core_start = close - timedelta(minutes=105)
    core = [
        Candle(core_start+timedelta(minutes=i*5),
               core_start+timedelta(minutes=(i+1)*5),
               close+timedelta(seconds=1), close+timedelta(seconds=1),
               "100", "102", "99", "101", "10", "1000") for i in range(21)
    ]
    market = MarketSnapshot("BTCUSDT", "USDT", True, "TRADING",
                            "50000000", "100", "100.01",
                            close+timedelta(seconds=2))
    return dict(symbol="BTCUSDT", horizon=horizon, direction=direction, parent=parent,
                children=child, core_5m=core, market=market,
                decision_at=close+timedelta(seconds=5), tolerance=EXACT,
                event_discriminator="candidate-A")


class QualificationReadinessTests(unittest.TestCase):
    def assert_blocked(self, row):
        self.assertEqual(row["qualification_status"], "NOT_EVALUATED")
        self.assertIsNone(row["provisional_qualified_signal"])
        self.assertEqual(row["score_status"], "SCORE_UNAVAILABLE")
        self.assertIsNone(row["score"])
        self.assertIsNone(row["signal_id"])
        self.assertFalse(row["publishable"])
        self.assertFalse(row["delivery_authorized"])
        self.assertFalse(row["durable_dedup_authority"])
        self.assertEqual(row["trade_plan_status"], "RESEARCH_ONLY")
        self.assertEqual(row["stage03c_dependency"], "UNMERGED_NO_SCORE_INPUT_INTEGRATION")

    def test_both_horizons_and_directions_valid_closed_synthetic(self):
        for horizon in Horizon:
            for direction in Direction:
                with self.subTest(horizon=horizon.value, direction=direction.value):
                    kw = setup(horizon, direction)
                    with patch("urllib.request.urlopen", side_effect=AssertionError("NETWORK_FORBIDDEN")), \
                         patch("socket.create_connection", side_effect=AssertionError("NETWORK_FORBIDDEN")), \
                         patch("zs_smart_gate.stage03b1_live.probe_once",
                               side_effect=AssertionError("BINANCE_FORBIDDEN")):
                        row = assess_readiness(**kw)
                    self.assertEqual(row["raw_state"], "RAW_OBSERVATION")
                    self.assertEqual(row["status"], "RESEARCH_CANDIDATE")
                    self.assertEqual(row["reconciliation"]["status"], "PASS")
                    self.assertEqual(row["candidate"]["status"], "ELIGIBLE")
                    self.assertEqual(row["research_event"]["status"], "RESEARCH_CANDIDATE")
                    self.assertEqual(row["identity"]["direction"], direction.value)
                    self.assertEqual(row["identity"]["horizon"], horizon.value)
                    self.assertEqual(len(row["research_metrics"][direction.value]), 8)
                    self.assertEqual(row["dedup_status"], "UNTRACKED_EPHEMERAL")
                    self.assertTrue(all(m["status"] == "RESEARCH_METRIC_UNAPPROVED"
                                        for m in row["research_metrics"][direction.value]))
                    self.assertIn("NORMALIZATION_FORMULAS_NOT_APPROVED", row["reason_codes"])
                    self.assert_blocked(row)

    def test_delayed_parent_and_unclosed_parent_fail_closed(self):
        for horizon in Horizon:
            kw = setup(horizon)
            for parent in (
                dataclasses.replace(kw["parent"], available_at=kw["decision_at"]+timedelta(seconds=1)),
                dataclasses.replace(kw["parent"], close_at=kw["decision_at"]+timedelta(minutes=1)),
            ):
                with self.subTest(horizon=horizon.value, issue=parent.close_at):
                    row = assess_readiness(**{**kw, "parent": parent})
                    self.assertEqual(row["status"], "INVALID")
                    self.assertTrue(any("MTF_PARENT_" in s for s in row["reason_codes"]))
                    self.assertIsNone(row["candidate"])
                    self.assertEqual(row["research_metrics"], {})
                    self.assert_blocked(row)

    def test_missing_and_late_child_or_changed_source(self):
        for horizon in Horizon:
            kw = setup(horizon)
            tests = (
                (kw["children"][:-1], "MTF_CHILD_COUNT_MISMATCH"),
                ([dataclasses.replace(kw["children"][0],
                   available_at=kw["decision_at"]+timedelta(seconds=1))] +
                 kw["children"][1:], "FUTURE_OR_UNAVAILABLE_AT_DECISION"),
                ([dataclasses.replace(kw["children"][0], source_id="OTHER")] +
                 kw["children"][1:], "MTF_MIXED_SOURCES_UNVERIFIED"),
            )
            for children, marker in tests:
                with self.subTest(horizon=horizon.value, marker=marker):
                    row = assess_readiness(**{**kw, "children": children})
                    self.assertEqual(row["status"], "INVALID")
                    self.assertTrue(any(marker in x for x in row["reason_codes"]))
                    self.assertIsNone(row["research_event"])
                    self.assertEqual(row["research_metrics"], {})
                    self.assert_blocked(row)

    def test_core_missing_future_misaligned_and_child_disagreement(self):
        for horizon in Horizon:
            kw = setup(horizon)
            core = kw["core_5m"]
            alterations = [
                (core[:-1], "CORE_EXPECTED_21_CANDLES"),
                (core[:-1] + [dataclasses.replace(
                    core[-1], available_at=kw["decision_at"]+timedelta(seconds=1))],
                 "CORE_CANDLE_20_FUTURE_OR_UNAVAILABLE"),
                ([dataclasses.replace(core[0], open_at=core[0].open_at+timedelta(minutes=5))] +
                 core[1:], "CORE_CANDLE_0_BAD_DURATION"),
            ]
            if horizon is Horizon.INTRADAY:
                alterations.append((
                    core[:-1]+[dataclasses.replace(core[-1], base_volume=Decimal("12"))],
                    "INTRADAY_CORE_CHILD_SOURCE_MISMATCH"))
            for invalid, marker in alterations:
                with self.subTest(horizon=horizon.value, marker=marker):
                    row = assess_readiness(**{**kw, "core_5m": invalid})
                    self.assertEqual(row["status"], "INVALID")
                    self.assertIn(marker, row["reason_codes"])
                    self.assertIsNone(row["candidate"])
                    self.assert_blocked(row)

    def test_market_future_preparent_and_ineligible(self):
        for horizon in Horizon:
            kw = setup(horizon)
            cases = (
                (dataclasses.replace(kw["market"],
                     observed_at=kw["decision_at"]+timedelta(seconds=1)),
                 "INVALID", "MARKET_SNAPSHOT_FROM_FUTURE"),
                (dataclasses.replace(kw["market"],
                     observed_at=kw["parent"].close_at-timedelta(seconds=1)),
                 "INVALID", "MARKET_SNAPSHOT_PRE_PARENT_CLOSE"),
                (dataclasses.replace(kw["market"], quote_volume_24h=Decimal("0")),
                 "REJECTED", "LOW_24H_QUOTE_VOLUME"),
            )
            for market, status, marker in cases:
                row = assess_readiness(**{**kw, "market": market})
                self.assertEqual(row["status"], status)
                self.assertIn(marker, row["reason_codes"])
                self.assertEqual(row["research_metrics"], {})
                self.assert_blocked(row)
                if status == "INVALID":
                    self.assertIsNone(row["candidate"])

    def test_normalized_input_unknown_and_declared_is_never_scored(self):
        kw = setup(Horizon.INTRADAY)
        for groups, reason in (({"invented": "0.5"}, "UNKNOWN_NORMALIZED_GROUP"),
                               ({"30M_STRONG_CLOSE": "0.5"},
                                "NORMALIZATION_INPUT_NOT_APPROVED")):
            row = assess_readiness(**{**kw, "normalized_groups": groups})
            self.assertEqual(row["status"], "INVALID")
            self.assertIn(reason, row["reason_codes"])
            self.assertEqual(row["research_metrics"], {})
            self.assert_blocked(row)

    def test_ephemeral_dedup_retry_distinct_close_direction_and_discriminator(self):
        registry = ResearchKeyRegistry()
        kw = setup(Horizon.INTRADAY)
        a = assess_readiness(**{**kw, "registry": registry})
        b = assess_readiness(**{**kw, "registry": registry})
        self.assertEqual(a["identity"]["detection_event_key"],
                         b["identity"]["detection_event_key"])
        self.assertEqual(a["dedup_status"], "NEW_RESEARCH_EVENT")
        self.assertEqual(b["dedup_status"], "DUPLICATE_RETRY")
        different = assess_readiness(**{**kw, "registry": registry,
                                        "event_discriminator": "candidate-B"})
        self.assertEqual(different["dedup_status"], "NEW_RESEARCH_EVENT")
        down = assess_readiness(**{**kw, "registry": registry, "direction": Direction.DOWN})
        self.assertEqual(down["dedup_status"], "NEW_RESEARCH_EVENT")
        later = setup(Horizon.INTRADAY)
        offset = timedelta(minutes=30)
        later["parent"] = dataclasses.replace(
            later["parent"], open_at=later["parent"].open_at+offset,
            close_at=later["parent"].close_at+offset,
            received_at=later["parent"].received_at+offset,
            available_at=later["parent"].available_at+offset)
        later["children"] = [dataclasses.replace(
            c, open_at=c.open_at+offset, close_at=c.close_at+offset,
            received_at=c.received_at+offset, available_at=c.available_at+offset)
            for c in later["children"]]
        later["core_5m"] = [dataclasses.replace(
            c, open_at=c.open_at+offset, close_at=c.close_at+offset,
            received_at=c.received_at+offset, available_at=c.available_at+offset)
            for c in later["core_5m"]]
        later["market"] = dataclasses.replace(
            later["market"], observed_at=later["market"].observed_at+offset)
        later["decision_at"] = later["decision_at"]+offset
        fresh = assess_readiness(**{**later, "registry": registry})
        self.assertEqual(fresh["dedup_status"], "NEW_RESEARCH_EVENT")
        self.assertNotEqual(fresh["identity"]["detection_event_key"],
                            a["identity"]["detection_event_key"])
        for row in (a,b,different,down,fresh):
            self.assert_blocked(row)

    def test_wrong_horizon_market_symbol_and_unavailable_source(self):
        kw = setup(Horizon.SWING)
        for changed, reason in (
            ({"parent": dataclasses.replace(kw["parent"], timeframe="30m")}, "PARENT_HORIZON_MISMATCH"),
            ({"market": dataclasses.replace(kw["market"], symbol="ETHUSDT")}, "MARKET_SYMBOL_MISMATCH"),
            ({"core_5m": [dataclasses.replace(c, close_at=c.close_at+timedelta(minutes=5))
                          for c in kw["core_5m"]]}, "CORE_CLOSE_NOT_PARENT_ALIGNED"),
        ):
            row = assess_readiness(**{**kw, **changed})
            self.assertEqual(row["status"], "INVALID")
            self.assertIn(reason, row["reason_codes"])
            self.assert_blocked(row)

    def test_no_non_utc_or_malformed_source_input(self):
        kw = setup(Horizon.INTRADAY)
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            assess_readiness(**{**kw, "decision_at": datetime(2026,10,28,9,0)})
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_EVENT_IDENTITY"):
            assess_readiness(**{**kw, "event_discriminator": ""})


if __name__ == "__main__":
    unittest.main()
