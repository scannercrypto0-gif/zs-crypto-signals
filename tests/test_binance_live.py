"""Offline tests of live adapter contracts; never make public HTTP requests."""
import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.error import HTTPError

from zs_smart_gate.binance_live import (
    LiveBlocked, LiveFailure, get_json, is_spot_enabled, main, to_candles,
)
UTC = timezone.utc
BASE = datetime(2026, 1, 1, tzinfo=UTC)


def rows(count=22):
    start = int(BASE.timestamp() * 1000)
    return [
        [start + i * 300000, "100", "101", "99", "100", "100",
         start + (i + 1) * 300000 - 1, "10000", 100, "50", "5000", "0"]
        for i in range(count)
    ]


class BinanceLiveAdapterOfflineTests(unittest.TestCase):
    def test_close_time_inclusive_conversion_and_partial_exclusion(self):
        received = BASE + timedelta(minutes=105, seconds=1)
        output = to_candles(rows(), received)
        self.assertEqual(len(output), 21)
        self.assertEqual(output[0].open_at, BASE)
        self.assertEqual(output[-1].close_at, BASE + timedelta(minutes=105))
        self.assertEqual(output[-1].received_at, received)
        self.assertEqual(output[-1].available_at, received)

    def test_insufficient_history_is_not_a_signal(self):
        with self.assertRaisesRegex(LiveFailure, "INSUFFICIENT"):
            to_candles(rows(15), BASE + timedelta(hours=2))

    def test_incorrect_exchange_close_semantics_rejected(self):
        items = rows()
        items[0][6] += 1
        with self.assertRaisesRegex(LiveFailure, "TIMESTAMP_SEMANTICS"):
            to_candles(items, BASE + timedelta(hours=2))

    def test_spot_permissions_fail_closed_when_unknown(self):
        self.assertTrue(is_spot_enabled({"isSpotTradingAllowed": True}))
        self.assertTrue(is_spot_enabled({"permissions": ["SPOT"]}))
        self.assertTrue(is_spot_enabled({"permissionSets": [["SPOT"]]}))
        self.assertFalse(is_spot_enabled({"permissions": ["MARGIN"]}))
        with self.assertRaises(LiveFailure):
            is_spot_enabled({"status": "TRADING"})

    def test_endpoint_whitelist_blocks_account_and_order(self):
        with self.assertRaisesRegex(ValueError, "UNAUTHORIZED_ENDPOINT"):
            get_json("/api/v3/order")

    def test_rate_limit_retry_after_respects_budget(self):
        error = HTTPError("https://data-api.binance.vision/api/v3/time", 429,
                          "rate limited", {"Retry-After": "600"}, io.BytesIO(b""))
        with patch("zs_smart_gate.binance_live.urlopen", side_effect=error) as mock:
            with self.assertRaisesRegex(LiveBlocked, "BINANCE_RATE_LIMIT_429"):
                get_json("/api/v3/time")
            self.assertEqual(mock.call_count, 1)

    def test_live_cli_requires_explicit_opt_in(self):
        with patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as exc:
                main([])
        self.assertEqual(exc.exception.code, 2)

    def test_malformed_kline_schema_rejected(self):
        with self.assertRaisesRegex(LiveFailure, "KLINES_SCHEMA"):
            to_candles([["bad"]], BASE)

    def test_private_or_unexpected_symbols_rejected_before_network(self):
        from zs_smart_gate.binance_live import run_live
        with self.assertRaises(ValueError):
            run_live("BTCUSDT/../../account")
