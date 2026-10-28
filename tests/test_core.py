import dataclasses
import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from zs_smart_gate.core import (
    Candle, MarketSnapshot, build_candidate, check_eligibility, decimal,
    impulse_probe, price_changes, rvol, score_v1_partial, spread_bps,
    utc, validate_candles,
)

UTC = timezone.utc
START = datetime(2026, 1, 1, tzinfo=UTC)


def fixture():
    candles = []
    for i in range(21):
        t = START + timedelta(minutes=5 * i)
        last = i == 20
        candles.append(Candle(
            open_at=t, close_at=t + timedelta(minutes=5),
            received_at=t + timedelta(minutes=5, seconds=1),
            available_at=t + timedelta(minutes=5, seconds=1),
            open=100, high=102 if last else 100,
            low=100, close=101 if last else 100,
            base_volume=300 if last else 100,
            quote_volume=30300 if last else 10000,
        ))
    decision = candles[-1].available_at + timedelta(seconds=1)
    market = MarketSnapshot(
        symbol="BTCUSDT", quote_asset="USDT", spot_enabled=True,
        trading_status="TRADING", quote_volume_24h=10000000,
        bid="100", ask="100.1", observed_at=decision - timedelta(seconds=1))
    return market, candles, decision


class FoundationTests(unittest.TestCase):
    def test_valid_closed_21(self):
        _, cs, now = fixture()
        self.assertEqual(validate_candles(cs, now), ())

    def test_incomplete_last_candle(self):
        _, cs, now = fixture()
        self.assertIn("CANDLE_20_FUTURE_OR_UNAVAILABLE",
                      validate_candles(cs, cs[-1].close_at - timedelta(seconds=1)))

    def test_missing_candle(self):
        _, cs, now = fixture()
        self.assertIn("EXPECTED_21_CANDLES", validate_candles(cs[:-1], now))

    def test_time_gap(self):
        _, cs, now = fixture()
        shifted = dataclasses.replace(cs[4], open_at=cs[4].open_at + timedelta(minutes=5),
                                      close_at=cs[4].close_at + timedelta(minutes=5),
                                      received_at=cs[4].received_at + timedelta(minutes=5),
                                      available_at=cs[4].available_at + timedelta(minutes=5))
        cs[4] = shifted
        self.assertTrue(any("GAP_OR_OVERLAP" in x for x in validate_candles(cs, now)))

    def test_bad_alignment(self):
        _, cs, now = fixture()
        cs[4] = dataclasses.replace(cs[4], open_at=cs[4].open_at + timedelta(minutes=1))
        self.assertTrue(any("BAD_ALIGNMENT" in x for x in validate_candles(cs, now)))

    def test_bad_duration(self):
        _, cs, now = fixture()
        cs[0] = dataclasses.replace(cs[0], close_at=cs[0].close_at + timedelta(seconds=1))
        self.assertIn("CANDLE_0_BAD_DURATION", validate_candles(cs, now))

    def test_future_received_data_leakage(self):
        _, cs, now = fixture()
        cs[1] = dataclasses.replace(cs[1], received_at=now + timedelta(seconds=1),
                                    available_at=now + timedelta(seconds=1))
        self.assertIn("CANDLE_1_FUTURE_OR_UNAVAILABLE", validate_candles(cs, now))

    def test_time_order(self):
        _, cs, now = fixture()
        cs[0] = dataclasses.replace(cs[0], available_at=cs[0].close_at)
        self.assertIn("CANDLE_0_TIME_ORDER", validate_candles(cs, now))

    def test_naive_timestamp_rejected(self):
        _, cs, _ = fixture()
        with self.assertRaises(ValueError):
            dataclasses.replace(cs[0], open_at=datetime(2026, 1, 1))
        with self.assertRaises(ValueError):
            utc(datetime(2026, 1, 1))

    def test_utc_normalization(self):
        tz = timezone(timedelta(hours=3))
        self.assertEqual(utc(datetime(2026, 1, 1, 3, tzinfo=tz)), START)

    def test_invalid_ohlc(self):
        _, cs, now = fixture()
        cs[0] = dataclasses.replace(cs[0], high=90)
        self.assertIn("CANDLE_0_INVALID_OHLC", validate_candles(cs, now))

    def test_invalid_volume(self):
        _, cs, now = fixture()
        cs[0] = dataclasses.replace(cs[0], base_volume=-1)
        self.assertIn("CANDLE_0_INVALID_VOLUME", validate_candles(cs, now))

    def test_spread_zero_and_20_boundary(self):
        self.assertEqual(spread_bps(100, 100), 0)
        bid = Decimal("99.9")
        ask = Decimal("100.1")
        self.assertEqual(spread_bps(bid, ask), Decimal("20"))

    def test_spread_above_and_invalid(self):
        self.assertGreater(spread_bps(99, 101), 20)
        for bid, ask in ((0, 1), (2, 1), (-1, 1)):
            with self.assertRaises(ValueError):
                spread_bps(bid, ask)

    def test_market_eligibility_boundary(self):
        market, _, now = fixture()
        self.assertEqual(check_eligibility(market, now), ())
        self.assertIn("LOW_24H_QUOTE_VOLUME",
                      check_eligibility(dataclasses.replace(market, quote_volume_24h=9999999), now))
        self.assertIn("SPREAD_ABOVE_LIMIT",
                      check_eligibility(dataclasses.replace(market, bid=99, ask=101), now))

    def test_ineligible_spot_quote_status_and_future(self):
        market, _, now = fixture()
        m = dataclasses.replace(market, quote_asset="BTC", spot_enabled=False,
                                trading_status="HALT", observed_at=now + timedelta(seconds=1))
        reasons = check_eligibility(m, now)
        self.assertEqual(reasons, ("MARKET_SNAPSHOT_FROM_FUTURE",))

    def test_invalid_snapshot_spread(self):
        m, _, now = fixture()
        self.assertIn("INVALID_BID_ASK",
                      check_eligibility(dataclasses.replace(m, bid=0), now))

    def test_rvol_base_quote_distinct(self):
        _, cs, _ = fixture()
        self.assertEqual(rvol(cs, "base"), Decimal("3"))
        self.assertEqual(rvol(cs, "quote"), Decimal("3.03"))

    def test_zero_volume_denominator_not_zero(self):
        _, cs, _ = fixture()
        cs = [dataclasses.replace(c, base_volume=0) for c in cs[:-1]] + cs[-1:]
        self.assertIsNone(rvol(cs, "base"))

    def test_rvol_invalid_or_missing(self):
        _, cs, _ = fixture()
        self.assertIsNone(rvol(cs[:-1], "base"))
        with self.assertRaises(ValueError):
            rvol(cs, "wrong")

    def test_price_basis_independent(self):
        _, cs, _ = fixture()
        self.assertEqual(price_changes(cs), (Decimal("1"), Decimal("1")))
        cs[-1] = dataclasses.replace(cs[-1], open="100.5")
        c2c, oc = price_changes(cs)
        self.assertEqual(c2c, 1)
        self.assertNotEqual(c2c, oc)

    def test_experimental_impulse_probe_boundaries(self):
        k = {"basis": "CLOSE_TO_PREVIOUS_CLOSE_5M", "volume_kind": "BASE"}
        self.assertEqual(impulse_probe("0.7", "2", **k), "UPWARD_IMPULSE")
        self.assertEqual(impulse_probe("-0.7", "2", **k), "DOWNWARD_IMPULSE")
        self.assertEqual(impulse_probe("8", "1", **k), "NO_IMPULSE")
        self.assertEqual(impulse_probe("0.6", "2", **k), "NO_IMPULSE")
        with self.assertRaises(ValueError):
            impulse_probe("1", "3", basis="UNAPPROVED", volume_kind="BASE")

    def test_score_partial_never_probability(self):
        d = score_v1_partial(Decimal("1"), Decimal("3"), Decimal("10"))
        self.assertIsNone(d["total"])
        self.assertIsNone(d["components"]["mtf_alignment_20"])
        self.assertIsNone(d["components"]["momentum_consistency_10"])
        self.assertEqual(d["status"], "SCORE_UNAVAILABLE")

    def test_missing_score_inputs_not_filled_with_zero(self):
        d = score_v1_partial(None, None, None)
        self.assertTrue(all(v is None for v in d["components"].values()))

    def test_non_finite_and_bool_numbers_rejected(self):
        for x in ("NaN", "Infinity", True, "oops"):
            with self.assertRaises(ValueError):
                decimal(x)

    def test_candidate_deterministic_and_json_safe(self):
        m, cs, now = fixture()
        a = build_candidate(m, cs, now)
        b = build_candidate(m, cs, now)
        self.assertEqual(a.as_dict(), b.as_dict())
        self.assertEqual(a.status, "ELIGIBLE")
        self.assertEqual(a.impulse_classification, "UNRESOLVED_CONTRACT")
        self.assertIsNone(a.score)
        json.dumps(a.as_dict(), sort_keys=True)

    def test_candidate_rejects_unavailable_future(self):
        m, cs, now = fixture()
        cs[-1] = dataclasses.replace(cs[-1], available_at=now + timedelta(seconds=2))
        candidate = build_candidate(m, cs, now)
        self.assertEqual(candidate.status, "INVALID_CANDLES")
        self.assertIsNone(candidate.c2c_pct)
        self.assertIsNone(candidate.rvol_base_20)

    def test_candidate_ineligible_still_auditable(self):
        m, cs, now = fixture()
        m = dataclasses.replace(m, quote_volume_24h=0)
        a = build_candidate(m, cs, now)
        self.assertEqual(a.status, "INELIGIBLE")
        self.assertIn("UNIVERSE_NOT_ELIGIBLE", a.reason_codes)

    def test_no_automatic_durable_or_delivery_side_effects(self):
        m, cs, now = fixture()
        c = build_candidate(m, cs, now)
        self.assertNotIn("telegram", c.as_dict())
        self.assertNotIn("order", c.as_dict())


    def test_future_market_snapshot_is_completely_suppressed(self):
        market, candles, now = fixture()
        future = now + timedelta(seconds=30)
        a = dataclasses.replace(market, observed_at=future)
        b = dataclasses.replace(a, bid=1, ask=300, quote_volume_24h=0,
                                trading_status="HALT", spot_enabled=False, quote_asset="BTC")
        first, second = build_candidate(a, candles, now), build_candidate(b, candles, now)
        self.assertEqual(first.as_dict(), second.as_dict())
        self.assertEqual(first.status, "UNAVAILABLE_MARKET")
        self.assertEqual(first.eligibility_reasons, ("MARKET_SNAPSHOT_FROM_FUTURE",))
        for key in ("spread_bps", "c2c_pct", "oc_pct", "rvol_base_20",
                    "rvol_quote_20", "score"):
            self.assertIsNone(first.as_dict()[key])
        self.assertNotIn("LOW_24H_QUOTE_VOLUME", first.reason_codes)

    def test_partial_score_rejects_negative_and_nonfinite_rvol(self):
        for value in (-1, "-0.01", "NaN", "Infinity"):
            with self.subTest(rvol=value), self.assertRaises(ValueError):
                score_v1_partial(1, value, 1)

    def test_partial_score_rejects_invalid_spread(self):
        for value in (-1, "-0.01", "NaN", "Infinity"):
            with self.subTest(spread=value), self.assertRaises(ValueError):
                score_v1_partial(1, 3, value)

    def test_partial_score_accepts_zero_rvol_and_spread(self):
        result = score_v1_partial(1, 0, 0)
        self.assertEqual(result["components"]["volume_expansion_25"], "0")
        self.assertEqual(result["components"]["liquidity_quality_10"], "10")
        self.assertIsNone(result["total"])



if __name__ == "__main__":
    unittest.main()
