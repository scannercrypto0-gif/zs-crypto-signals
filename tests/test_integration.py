"""Deterministic offline end-to-end tests of the *implemented* research path.

These call the real typed contracts and build_candidate (not mocked modules).
No full Score V1, signal event, durable storage or Telegram pipeline exists.
"""
import dataclasses
import json
import unittest
from datetime import timedelta
from decimal import Decimal

from test_core import fixture
from zs_smart_gate.core import build_candidate, check_eligibility, score_v1_partial


class OfflineResearchPathTests(unittest.TestCase):
    def test_complete_eligible_path_with_independent_oracles(self):
        market, candles, decision_at = fixture()
        result = build_candidate(market, candles, decision_at)
        output = json.loads(json.dumps(result.as_dict(), sort_keys=True))
        self.assertEqual(output["status"], "ELIGIBLE")
        self.assertEqual(output["eligibility_reasons"], [])
        self.assertEqual(output["candle_errors"], [])
        self.assertEqual(Decimal(output["c2c_pct"]), (Decimal(101) / Decimal(100) - 1) * 100)
        self.assertEqual(Decimal(output["oc_pct"]), Decimal(1))
        self.assertEqual(Decimal(output["rvol_base_20"]), Decimal(300) / Decimal(100))
        self.assertEqual(Decimal(output["rvol_quote_20"]), Decimal(30300) / Decimal(10000))
        expected_spread = Decimal(10000) * Decimal("0.1") / Decimal("100.05")
        self.assertEqual(Decimal(output["spread_bps"]), expected_spread)
        self.assertEqual(output["score_status"], "SCORE_UNAVAILABLE")
        self.assertIsNone(output["score"])
        self.assertEqual(output["impulse_classification"], "UNRESOLVED_CONTRACT")
        partial = score_v1_partial(result.c2c_pct, result.rvol_base_20, result.spread_bps)
        self.assertIsNone(partial["total"])
        self.assertIsNone(partial["components"]["mtf_alignment_20"])

    def test_ineligible_market_retains_observable_research_and_reason(self):
        market, candles, decision_at = fixture()
        market = dataclasses.replace(market, quote_volume_24h=9999999)
        r = build_candidate(market, candles, decision_at)
        self.assertEqual(r.status, "INELIGIBLE")
        self.assertIn("LOW_24H_QUOTE_VOLUME", r.eligibility_reasons)
        self.assertEqual(r.rvol_base_20, 3)
        self.assertIsNone(r.score)

    def test_missing_candle_blocks_all_derived_features(self):
        market, candles, decision_at = fixture()
        r = build_candidate(market, candles[:-1], decision_at)
        self.assertEqual(r.status, "INVALID_CANDLES")
        self.assertIn("EXPECTED_21_CANDLES", r.candle_errors)
        self.assertIsNone(r.c2c_pct)
        self.assertIsNone(r.rvol_quote_20)
        self.assertIsNone(r.spread_bps)

    def test_late_candle_cannot_enter_research_features(self):
        market, candles, decision_at = fixture()
        candles[-1] = dataclasses.replace(candles[-1], available_at=decision_at + timedelta(seconds=1))
        r = build_candidate(market, candles, decision_at)
        self.assertEqual(r.status, "INVALID_CANDLES")
        self.assertIn("CANDLE_20_FUTURE_OR_UNAVAILABLE", r.candle_errors)
        self.assertIsNone(r.c2c_pct)

    def test_future_snapshot_isolation_under_mutated_market_values(self):
        market, candles, decision_at = fixture()
        future = dataclasses.replace(market, observed_at=decision_at + timedelta(seconds=5))
        mutated = dataclasses.replace(future, bid=1, ask=10000, quote_volume_24h=0,
                                      spot_enabled=False, quote_asset="BTC")
        first = build_candidate(future, candles, decision_at).as_dict()
        second = build_candidate(mutated, candles, decision_at).as_dict()
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "UNAVAILABLE_MARKET")
        self.assertIsNone(first["spread_bps"])
        self.assertIsNone(first["c2c_pct"])
        self.assertEqual(check_eligibility(mutated, decision_at), ("MARKET_SNAPSHOT_FROM_FUTURE",))

    def test_time_gap_blocks_path(self):
        market, candles, decision_at = fixture()
        candles[7] = dataclasses.replace(candles[7], open_at=candles[7].open_at + timedelta(minutes=5),
                                        close_at=candles[7].close_at + timedelta(minutes=5),
                                        received_at=candles[7].received_at + timedelta(minutes=5),
                                        available_at=candles[7].available_at + timedelta(minutes=5))
        result = build_candidate(market, candles, decision_at)
        self.assertEqual(result.status, "INVALID_CANDLES")
        self.assertTrue(any("GAP_OR_OVERLAP" in x for x in result.candle_errors))

    def test_zero_volume_does_not_fabricate_rvol(self):
        market, candles, decision_at = fixture()
        candles = [dataclasses.replace(c, base_volume=0) for c in candles[:-1]] + candles[-1:]
        result = build_candidate(market, candles, decision_at)
        self.assertIsNone(result.rvol_base_20)
        self.assertEqual(result.rvol_quote_20, Decimal("3.03"))
        self.assertIn("RVOL_BASE_DENOMINATOR_MISSING", result.reason_codes)

    def test_bad_spread_is_explicit_in_candidate(self):
        market, candles, decision_at = fixture()
        market = dataclasses.replace(market, bid=0)
        result = build_candidate(market, candles, decision_at)
        self.assertEqual(result.status, "INELIGIBLE")
        self.assertIn("INVALID_BID_ASK", result.eligibility_reasons)
        self.assertIsNone(result.spread_bps)

    def test_repeat_path_is_deterministic_and_has_no_execution(self):
        market, candles, decision_at = fixture()
        one = build_candidate(market, candles, decision_at).as_dict()
        two = build_candidate(market, candles, decision_at).as_dict()
        self.assertEqual(one, two)
        self.assertNotIn("telegram", one)
        self.assertNotIn("order", one)
        self.assertNotIn("signal_id", one)

