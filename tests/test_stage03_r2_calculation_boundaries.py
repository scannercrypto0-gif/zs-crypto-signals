"""One-pass synthetic source-unit and UTC-frame negative controls for R2."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from test_stage03_r2_offline import intraday, swing
from test_stage03_r2_source_contract import packet_pair, trace_bundle, mode_evidence
from zs_smart_gate.stage03_r2_offline import Unavailable, evaluate_r2, liquidity
from zs_smart_gate.stage03_r2_source_contract import (
    ticker24_from_public_fields, market_from_explicit_packets,
    inspect_full_impulse_trace, require_prior_mode,
)


def shift_bars(rows, delta):
    return tuple(replace(
        bar, open_at=bar.open_at + delta, close_at=bar.close_at + delta,
        received_at=bar.received_at + delta,
        available_at=bar.available_at + delta,
    ) for bar in rows)


class R2N06N10FocusedTests(TestCase):
    def test_n10_contiguous_weekly_sunday_origin_is_not_utc_monday(self):
        kw = swing()
        self.assertIsNotNone(evaluate_r2(**kw)["normalizers"]["DAILY_WEEKLY_CONTEXT"])
        ctx = dict(kw["context"])
        ctx["1w"] = shift_bars(ctx["1w"], -timedelta(days=1))
        kw["context"] = ctx
        result = evaluate_r2(**kw)
        self.assertIsNone(result["normalizers"]["DAILY_WEEKLY_CONTEXT"])
        self.assertEqual(result["missing_reasons"]["DAILY_WEEKLY_CONTEXT"],
                         "CONTEXT_UTC_BOUNDARY_MISMATCH:1w")
        self.assertFalse(result["publishable"])

    def test_n10_contiguous_daily_2300_utc_origin_is_not_midnight(self):
        kw = swing()
        ctx = dict(kw["context"])
        ctx["1d"] = shift_bars(ctx["1d"], -timedelta(hours=1))
        kw["context"] = ctx
        result = evaluate_r2(**kw)
        self.assertIsNone(result["normalizers"]["DAILY_WEEKLY_CONTEXT"])
        self.assertEqual(result["missing_reasons"]["DAILY_WEEKLY_CONTEXT"],
                         "CONTEXT_UTC_BOUNDARY_MISMATCH:1d")
        self.assertIsNotNone(result["normalizers"]["FOUR_H_STRONG_CLOSE"])

    def test_n06_n12_realistic_base_and_quote_fields_arithmetic_reference(self):
        for maker in (intraday, swing):
            kw = maker()
            book, ticker = packet_pair(kw)
            raw = {"symbol": "BTCUSDT", "volume": "250",
                   "quoteVolume": "20000000"}
            parsed = ticker24_from_public_fields(
                raw=raw, endpoint="/api/v3/ticker/24hr", symbol="BTCUSDT",
                quote_asset="USDT", receipt=ticker.receipt)
            self.assertEqual(parsed.base_volume, D("250"))
            self.assertEqual(parsed.quote_volume, D("20000000"))
            market = market_from_explicit_packets(
                book=book, ticker=parsed, decision_at=kw["decision_at"],
                witness=kw["witness"])
            self.assertEqual(market, kw["market"])
            # Independent hand-calculated: spread ~9.995002499 bps,
            # liquidity = (3*(1-spread/20) + 2*(1-10m/20m))/5.
            self.assertEqual(
                liquidity(market, kw["decision_at"], kw["witness"]),
                D("0.5001499250374812593703148426"))
            self.assertEqual(kw["market"].quote_24h, D("20000000"))

    def test_reject_base_volume_substitution_invalid_endpoint_or_missing_field(self):
        kw = intraday()
        book, ticker = packet_pair(kw)
        base = {"symbol": "BTCUSDT", "volume": "250",
                "quoteVolume": "20000000"}
        args = dict(endpoint="/api/v3/ticker/24hr", symbol="BTCUSDT",
                    quote_asset="USDT", receipt=ticker.receipt)
        with self.assertRaisesRegex(Unavailable, "BASE_AND_QUOTE_FIELDS_REQUIRED"):
            ticker24_from_public_fields(raw={"symbol":"BTCUSDT",
                                             "volume":"250"}, **args)
        with self.assertRaisesRegex(Unavailable, "ENDPOINT_REQUIRED"):
            ticker24_from_public_fields(raw=base, **dict(args, endpoint="/api/v3/klines"))
        with self.assertRaisesRegex(Unavailable, "PAYLOAD_SYMBOL_MISMATCH"):
            ticker24_from_public_fields(raw=dict(base,symbol="ETHUSDT"),**args)
        with self.assertRaisesRegex(Unavailable, "NEGATIVE_VOLUME"):
            ticker24_from_public_fields(raw=dict(base,volume="-1"), **args)
        wrong = ticker24_from_public_fields(
            raw=dict(base,quoteVolume="250"), **args)
        with self.assertRaisesRegex(Unavailable, "SPREAD_OR_24H_TURNOVER_INELIGIBLE"):
            market_from_explicit_packets(
                book=book,ticker=wrong,decision_at=kw["decision_at"],
                witness=kw["witness"])

    def test_n03_full_impulse_trace_rejects_crossfeed_and_non_5m_candle(self):
        kw = intraday()
        definition, trace, candles = trace_bundle(kw)
        wrong_source_bars = list(candles)
        wrong_source_trace = list(trace)
        wrong_source_bars[10] = replace(
            candles[10], source_id="SYNTHETIC:FOREIGN_PROVIDER")
        wrong_source_trace[10] = replace(
            trace[10], source_id="SYNTHETIC:FOREIGN_PROVIDER")
        args = dict(
            definition=definition, direction=kw["direction"],
            horizon=kw["horizon"], mode=kw["mode"],
            decision_at=kw["decision_at"], witness=kw["witness"])
        with self.assertRaisesRegex(Unavailable, "FULL_IMPULSE_CANDLE_SOURCE_CONFLICT"):
            inspect_full_impulse_trace(
                trace=wrong_source_trace, candles=wrong_source_bars, **args)
        wrong_frame_bars = list(candles)
        wrong_frame_trace = list(trace)
        wrong_frame_bars[0] = replace(
            candles[0], open_at=candles[0].open_at-timedelta(minutes=1))
        wrong_frame_trace[0] = replace(
            trace[0], open_at=wrong_frame_bars[0].open_at)
        with self.assertRaisesRegex(Unavailable, "FULL_IMPULSE_NOT_5M_FRAME"):
            inspect_full_impulse_trace(
                trace=wrong_frame_trace, candles=wrong_frame_bars, **args)

    def test_n07_prior_mode_rejects_stale_evidence_before_parent(self):
        kw = swing()
        mode = mode_evidence(kw)
        reference_close = kw["parent"].open_at - timedelta(hours=9)
        stale = replace(
            mode, context_close_at=reference_close,
            observed_at=reference_close+timedelta(seconds=1),
            received_at=reference_close+timedelta(seconds=2),
            available_at=reference_close+timedelta(seconds=3))
        with self.assertRaisesRegex(Unavailable, "MODE_CONTEXT_STALE_BEFORE_PARENT"):
            require_prior_mode(
                stale,mode=kw["mode"],direction=kw["direction"],
                horizon=kw["horizon"],parent=kw["parent"],
                decision_at=kw["decision_at"],witness=kw["witness"])
