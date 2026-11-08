"""Only the new offline receipt -> typed 03A/R2 research entrypoint.

Prior accepted 9/9 and 3/3 regressions are not executed by this module.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from unittest import TestCase
from unittest.mock import patch

from test_stage03_r2_offline import intraday, swing, falling_structure
from test_stage03_r2_functional import stage03_inputs
from test_stage03_r2_source_contract import swing_readiness
from test_stage03_r2_closed_bundle import sample
from zs_smart_gate.mtf_contracts import CandleWindow
from zs_smart_gate.stage03a_contracts import Direction
from zs_smart_gate.stage03_r2_offline import Unavailable
from zs_smart_gate.stage03_r2_closed_bundle import stage03_r2_from_closed_bundle
from zs_smart_gate.stage03_r2_receipt_bundle import (
    SCHEMA, stage03_r2_from_closed_receipts,
)


def _stamp(value):
    return value.isoformat()


def _window(value):
    return {
        "timeframe": value.timeframe, "source_id": value.source_id,
        "open_at": _stamp(value.open_at), "close_at": _stamp(value.close_at),
        "received_at": _stamp(value.received_at),
        "available_at": _stamp(value.available_at),
        "open": str(value.open), "high": str(value.high),
        "low": str(value.low), "close": str(value.close),
        "base_volume": str(value.base_volume),
        "quote_volume": str(value.quote_volume),
    }


def _receipt(value):
    return dict(source_id=value.source_id,
                observed_at=_stamp(value.observed_at),
                received_at=_stamp(value.received_at),
                available_at=_stamp(value.available_at))


def _record(sampled):
    book = sampled["book"]
    ticker = sampled["ticker24"]
    tolerance = sampled["tolerance"]
    witness = sampled["witness"]
    return {
        "schema": SCHEMA, "symbol": sampled["symbol"],
        "horizon": sampled["horizon"].value,
        "direction": sampled["direction"].value,
        "mode": sampled["mode"],
        "parent": _window(sampled["parent"]),
        "children": [_window(x) for x in sampled["children"]],
        "core_5m": [_window(x) for x in sampled["core_5m"]],
        "context": {key: [_window(x) for x in bars]
                    for key, bars in sampled["context"].items()},
        "book": {
            "symbol": book.symbol, "quote_asset": book.quote_asset,
            "trading_status": book.trading_status,
            "spot_enabled": book.spot_enabled,
            "bid": str(book.bid), "ask": str(book.ask),
            "receipt": _receipt(book.receipt),
        },
        "ticker24": {
            "symbol": ticker.symbol, "quote_asset": ticker.quote_asset,
            "endpoint": "/api/v3/ticker/24hr",
            "payload": {
                "symbol": ticker.symbol,
                "volume": str(ticker.base_volume),
                "quoteVolume": str(ticker.quote_volume),
            }, "receipt": _receipt(ticker.receipt),
        },
        "witness": {
            "independent_reference": witness.independent_reference,
            "uncertainty_seconds": str(witness.uncertainty_seconds),
            "synthetic": True,
        },
        "decision_at": _stamp(sampled["decision_at"]),
        "tolerance": {
            "price": str(tolerance.price),
            "base_volume": str(tolerance.base_volume),
            "quote_volume": str(tolerance.quote_volume),
            "policy_id": tolerance.policy_id,
        },
        "event_discriminator": sampled["event_discriminator"],
        **({"prior_mode_4h": [_window(x) for x in sampled["prior_mode_4h"]]}
           if "prior_mode_4h" in sampled else {}),
    }


class ReceiptEntrypointOnly(TestCase):
    def test_closed_intraday_records_equal_existing_typed_e2e_deterministically(self):
        source = intraday()
        bundle = sample(source, stage03_inputs(source))
        record = _record(bundle)
        with patch("socket.create_connection", side_effect=AssertionError("NO_NETWORK")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("NO_NETWORK")):
            baseline = stage03_r2_from_closed_bundle(**bundle)
            first = stage03_r2_from_closed_receipts(record)
            second = stage03_r2_from_closed_receipts(deepcopy(record))
        self.assertEqual(first, baseline)
        self.assertEqual(second, first)
        self.assertEqual(first["status"], "RESEARCH_CANDIDATE")
        self.assertEqual(first["market_source_review"]["real_pit_verified"], False)
        self.assertIsNone(first["score"])
        self.assertIsNone(first["signal_id"])
        self.assertFalse(first["publishable"])
        self.assertEqual(first["market_requests"], 0)

    def test_reject_missing_volume_non_utc_crossfeed_and_fabricated_clock(self):
        source = intraday()
        original = _record(sample(source, stage03_inputs(source)))
        cases = (
            (lambda r: r["parent"].pop("base_volume"), "RECEIPT_RECORD_FIELDS_INVALID"),
            (lambda r: r["children"][0].__setitem__("quote_volume", 5.0),
             "RECEIPT_DECIMAL_STRING_REQUIRED"),
            (lambda r: r["parent"].__setitem__("open_at", "2026-06-03T03:00:00+03:00"),
             "RECEIPT_EXPLICIT_UTC_REQUIRED"),
            (lambda r: r["context"]["1h"][0].__setitem__("source_id", "SYNTHETIC:OTHER"),
             "BUNDLE_CANDLE_SOURCE_MISMATCH"),
            (lambda r: r["ticker24"]["payload"].pop("quoteVolume"),
             "RECEIPT_TICKER24_EXPLICIT_VOLUME_STRINGS_REQUIRED"),
            (lambda r: r["ticker24"].__setitem__("endpoint", "/api/v3/ticker/price"),
             "TICKER_24H_ENDPOINT_REQUIRED"),
            (lambda r: r["witness"].__setitem__("synthetic", False),
             "RECEIPT_REAL_CLOCK_UNSUPPORTED"),
        )
        for break_record, expected in cases:
            row = deepcopy(original)
            break_record(row)
            with self.subTest(reason=expected), self.assertRaisesRegex(Unavailable, expected):
                stage03_r2_from_closed_receipts(row)

    def test_swing_prior_mode_and_direction_reach_research_only(self):
        source = swing()
        source["direction"] = Direction.UP
        data = sample(source, swing_readiness(source))
        prior = falling_structure(source["parent"].open_at - timedelta(hours=4))
        data["prior_mode_4h"] = tuple(CandleWindow(
            "4h", b.open_at, b.close_at, b.received_at, b.available_at,
            b.source_id, b.o, b.h, b.l, b.c, 10, b.q,
        ) for b in prior)
        result = stage03_r2_from_closed_receipts(_record(data))
        self.assertEqual(result["status"], "RESEARCH_CANDIDATE")
        self.assertEqual(result["mode_evidence_review"]["mode"], "REVERSAL")
        self.assertEqual(result["r2"]["direction"], "UP")
        self.assertIsNone(result["score"])
        self.assertFalse(result["delivery_authorized"])
