"""Offline unit/contract/end-to-end test of bounded Binance scanner with real core.

All HTTP replies are deterministic injected fixtures. No public network in this suite.
"""
import dataclasses
import io
import json
import time
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from zs_smart_gate.binance_live import LiveBlocked, LiveFailure
from zs_smart_gate.core import MarketSnapshot
from zs_smart_gate.scanner import (
    FIVE_MINUTE_MS, MAX_HTTP_REQUESTS, MAX_SYMBOLS_PER_CYCLE,
    build_universe, inspect_candles, main, scan_once, select_sample,
)
from zs_smart_gate.binance_live import timestamp


def sample_exchange():
    return {"symbols": [
        {"symbol": symbol, "quoteAsset": "USDT", "status": "TRADING",
         "isSpotTradingAllowed": True}
        for symbol in ("AAAUSDT", "BBBUSDT", "CCCUSDT", "DDDUSDT", "EEEUSDT")
    ] + [
        {"symbol": "LOWUSDT", "quoteAsset": "USDT", "status": "TRADING",
         "isSpotTradingAllowed": True},
        {"symbol": "HALTUSDT", "quoteAsset": "USDT", "status": "BREAK",
         "isSpotTradingAllowed": True},
        {"symbol": "NOTSPOTUSDT", "quoteAsset": "USDT", "status": "TRADING",
         "isSpotTradingAllowed": False},
        {"symbol": "ETHBTC", "quoteAsset": "BTC", "status": "TRADING",
         "isSpotTradingAllowed": True},
    ]}


def market_rows():
    names = [row["symbol"] for row in sample_exchange()["symbols"] if row["quoteAsset"] == "USDT"]
    tickers = [{"symbol": symbol, "quoteVolume": "50000000"} for symbol in names]
    for row in tickers:
        if row["symbol"] == "LOWUSDT":
            row["quoteVolume"] = "9999999"
    books = [{"symbol": symbol, "bidPrice": "99.99", "askPrice": "100.01"} for symbol in names]
    return tickers, books


def klines(now_ms):
    last_close = now_ms // FIVE_MINUTE_MS * FIVE_MINUTE_MS
    first = last_close - 21 * FIVE_MINUTE_MS
    output = []
    for i in range(22):
        open_ms = first + i * FIVE_MINUTE_MS
        output.append([
            open_ms, "100", "101", "99", "100.5", "100",
            open_ms + FIVE_MINUTE_MS - 1, "10050", 100,
            "50", "5000", "0",
        ])
    return output


class FakeGetter:
    def __init__(self, *, removed_ticker=None, mode=None, weight=None):
        self.calls = []
        self.mode = mode
        self.weight = weight
        self.now_ms = int(time.time() * 1000)
        self.removed_ticker = removed_ticker

    def __call__(self, path, params=None):
        self.calls.append((path, params))
        if self.mode == "blocked" and path == "/api/v3/klines":
            raise LiveBlocked("SIMULATED_429")
        if self.mode == "missing" and path == "/api/v3/klines":
            raise LiveFailure("SIMULATED_MISSING_KLINES")
        if self.mode == "stale" and path == "/api/v3/klines":
            data = klines(self.now_ms - FIVE_MINUTE_MS * 2)
        elif path == "/api/v3/time":
            data = {"serverTime": self.now_ms}
        elif path == "/api/v3/exchangeInfo":
            data = sample_exchange()
        elif path == "/api/v3/ticker/24hr":
            data, _ = market_rows()
            if self.removed_ticker:
                data = [r for r in data if r["symbol"] != self.removed_ticker]
        elif path == "/api/v3/ticker/bookTicker":
            _, data = market_rows()
        elif path == "/api/v3/klines":
            data = klines(self.now_ms)
        else:
            raise AssertionError("UNEXPECTED_ENDPOINT_" + path)
        meta = {"path": path, "http_status": 200, "latency_ms": 10.0,
                "t0_local_ms": self.now_ms, "received_local_ms": self.now_ms,
                "used_weight_1m": self.weight if self.weight is not None else "12"}
        return data, meta


class BoundedScannerTests(unittest.TestCase):
    def test_full_universe_and_baseline_are_not_modified(self):
        tickers, books = market_rows()
        items = build_universe(sample_exchange(), tickers, books,
                               datetime.now(timezone.utc))
        row = {x.symbol: x for x in items}
        self.assertEqual(len(items), 8)  # USDT symbols, NOT ETHBTC
        self.assertEqual(sum(x.status == "ELIGIBLE" for x in items), 5)
        self.assertEqual(row["LOWUSDT"].status, "INELIGIBLE")
        self.assertEqual(row["LOWUSDT"].cohort, "LOW_LIQUIDITY_RESEARCH_ONLY")
        self.assertEqual(row["LOWUSDT"].reasons, ("LOW_24H_QUOTE_VOLUME",))
        self.assertIn("SPOT_NOT_TRADABLE", row["HALTUSDT"].reasons)
        self.assertIn("SPOT_NOT_TRADABLE", row["NOTSPOTUSDT"].reasons)
        self.assertEqual(row["AAAUSDT"].market.quote_volume_24h, Decimal("50000000"))

    def test_missing_ticker_book_and_invalid_market_are_explicit(self):
        tickers, books = market_rows()
        tickers = [t for t in tickers if t["symbol"] != "AAAUSDT"]
        books = [b for b in books if b["symbol"] != "BBBUSDT"]
        for t in tickers:
            if t["symbol"] == "CCCUSDT":
                t["quoteVolume"] = "-1"
        rows = {x.symbol: x for x in build_universe(
            sample_exchange(), tickers, books, datetime.now(timezone.utc))}
        self.assertEqual(rows["AAAUSDT"].reasons, ("MISSING_24H_TICKER",))
        self.assertEqual(rows["BBBUSDT"].reasons, ("MISSING_BOOK_TICKER",))
        self.assertEqual(rows["CCCUSDT"].status, "INVALID_DATA")
        self.assertIn("INVALID_MARKET_FIELDS", rows["CCCUSDT"].reasons)

    def test_duplicate_exchange_and_book_are_rejected(self):
        tickers, books = market_rows()
        ex = sample_exchange()
        ex["symbols"].append(dict(ex["symbols"][0]))
        with self.assertRaisesRegex(LiveFailure, "EXCHANGE_DUPLICATE"):
            build_universe(ex, tickers, books, datetime.now(timezone.utc))
        ex = sample_exchange()
        books.append(dict(books[0]))
        with self.assertRaisesRegex(LiveFailure, "BOOK_DUPLICATE"):
            build_universe(ex, tickers, books, datetime.now(timezone.utc))

    def test_rotating_selection_covers_every_eligible_without_duplicates(self):
        tickers, books = market_rows()
        items = build_universe(sample_exchange(), tickers, books, datetime.now(timezone.utc))
        eligible = {x.symbol for x in items if x.status == "ELIGIBLE"}
        observed = set()
        for offset in range(len(eligible)):
            part = select_sample(items, 2, offset)
            self.assertEqual(len(set(x.symbol for x in part)), 2)
            observed.update(x.symbol for x in part)
        self.assertEqual(observed, eligible)
        self.assertEqual([x.symbol for x in select_sample(items, 3, 0)],
                         ["AAAUSDT", "BBBUSDT", "CCCUSDT"])
        for invalid in (0, -1, 5):
            with self.assertRaises(ValueError):
                select_sample(items, invalid, 0)
        with self.assertRaises(ValueError):
            select_sample(items, 2, -1)

    def test_offline_e2e_two_symbols_real_core_and_serialization(self):
        fake = FakeGetter()
        report = scan_once(limit=2, getter=fake)
        output = json.loads(json.dumps(report.as_dict(), sort_keys=True))
        self.assertEqual(report.status, "PASS")
        self.assertEqual(output["selection"]["selected_symbols"], ["AAAUSDT", "BBBUSDT"])
        self.assertEqual(output["universe"]["eligible_count"], 5)
        self.assertEqual(output["universe"]["cohorts"]["LOW_LIQUIDITY_RESEARCH_ONLY"], 1)
        self.assertEqual(output["measurements"]["calls_made"], 6)
        self.assertLessEqual(output["measurements"]["calls_made"], MAX_HTTP_REQUESTS)
        self.assertEqual(len(set(x["symbol"] for x in output["results"])), 2)
        for record in output["results"]:
            self.assertEqual(record["status"], "PASS")
            c = record["candidate"]
            self.assertEqual(c["status"], "ELIGIBLE")
            self.assertEqual(c["c2c_pct"], "0")
            self.assertEqual(Decimal(c["rvol_base_20"]), Decimal("1"))
            self.assertEqual(Decimal(c["rvol_quote_20"]), Decimal("1"))
            self.assertIsNone(c["score"])
            self.assertEqual(c["score_status"], "SCORE_UNAVAILABLE")
            self.assertEqual(c["impulse_classification"], "UNRESOLVED_CONTRACT")
            self.assertNotIn("signal_id", c)
            self.assertNotIn("telegram", c)
        self.assertEqual(fake.calls[0][0], "/api/v3/time")
        self.assertEqual(fake.calls[1][0], "/api/v3/exchangeInfo")
        self.assertEqual(fake.calls[2][0], "/api/v3/ticker/24hr")
        self.assertEqual(fake.calls[3][0], "/api/v3/ticker/bookTicker")

    def test_expanded_sample_reuses_universe_and_stays_inside_budget(self):
        fake = FakeGetter()
        report = scan_once(limit=4, offset=1, getter=fake)
        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.selections, ("BBBUSDT", "CCCUSDT", "DDDUSDT", "EEEUSDT"))
        self.assertEqual(len(report.results), 4)
        self.assertEqual(len(report.calls), 8)
        self.assertEqual(len(set(report.selections)), 4)
        self.assertGreaterEqual(report.peak_allocated_kib, 0)

    def test_missing_inventory_row_does_not_become_eligible(self):
        fake = FakeGetter(removed_ticker="CCCUSDT")
        output = scan_once(limit=2, getter=fake).as_dict(include_inventory=True)
        self.assertEqual(output["universe"]["eligible_count"], 4)
        self.assertFalse(output["universe"]["inventory_complete"])
        match = [x for x in output["inventory"] if x["symbol"] == "CCCUSDT"][0]
        self.assertEqual(match["status"], "MISSING_DATA")
        self.assertEqual(match["reasons"], ["MISSING_24H_TICKER"])

    def test_429_blocks_next_symbol_and_cannot_be_passed(self):
        fake = FakeGetter(mode="blocked")
        report = scan_once(limit=3, getter=fake)
        self.assertEqual(report.status, "BLOCKED")
        self.assertEqual(len(report.results), 1)
        self.assertEqual(report.results[0].status, "BLOCKED")
        self.assertIn("SIMULATED_429", report.results[0].reasons)
        self.assertEqual(len(fake.calls), 5)

    def test_missing_klines_causes_fail_not_missing_as_zero(self):
        report = scan_once(limit=2, getter=FakeGetter(mode="missing"))
        self.assertEqual(report.status, "FAIL")
        for result in report.results:
            self.assertEqual(result.status, "FAIL")
            self.assertIsNone(result.candidate)

    def test_stale_klines_are_not_reported_as_success(self):
        report = scan_once(limit=2, getter=FakeGetter(mode="stale"))
        self.assertEqual(report.status, "FAIL")
        self.assertIn("STALE_CLOSED_5M_WINDOW", report.results[0].reasons)

    def test_observed_weight_safety_stop_before_next_request(self):
        fake = FakeGetter(weight="1000")
        with self.assertRaisesRegex(LiveBlocked, "WEIGHT_SAFETY_STOP"):
            scan_once(limit=1, getter=fake)
        self.assertEqual(len(fake.calls), 1)

    def test_future_market_observation_fails_closed(self):
        tickers, books = market_rows()
        item = build_universe(sample_exchange(), tickers, books,
                              datetime.now(timezone.utc) + timedelta(minutes=2))[0]
        now_ms = int(time.time() * 1000)
        receipt = timestamp(now_ms)
        row = inspect_candles(item, klines(now_ms), receipt, receipt, 0)
        self.assertEqual(row.status, "FAIL")
        self.assertEqual(row.candidate.status, "UNAVAILABLE_MARKET")
        self.assertIsNone(row.candidate.spread_bps)
        self.assertIsNone(row.candidate.rvol_base_20)

    def test_api_getter_receipt_metadata_mandatory(self):
        def corrupt(path, params=None):
            return {"serverTime": int(time.time() * 1000)}, {}
        with self.assertRaisesRegex(LiveFailure, "RECEIPT_METADATA"):
            scan_once(limit=1, getter=corrupt)

    def test_cli_rejects_nonlive_and_bad_sample_before_requests(self):
        with patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as error:
                main(["--limit", "8"])
        self.assertEqual(error.exception.code, 2)
        with patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as error:
                main(["--limit", "2"])
        self.assertEqual(error.exception.code, 2)

    def test_no_network_when_imported_or_scanning_just_fixtures(self):
        with patch("zs_smart_gate.scanner.get_json", side_effect=AssertionError("NETWORK")):
            tickers, books = market_rows()
            rows = build_universe(sample_exchange(), tickers, books,
                                  datetime.now(timezone.utc))
            self.assertEqual(len(rows), 8)

if __name__ == "__main__":
    unittest.main()
