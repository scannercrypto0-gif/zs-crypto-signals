"""Deterministic offline fixtures for manual, bounded public G0 adapter.

No socket/API calls, credentials, clock attestations, or scored results.
"""
from __future__ import annotations

import io
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from zs_smart_gate.binance_live import LiveBlocked, LiveFailure
from zs_smart_gate.stage03a_contracts import Horizon
from zs_smart_gate.stage03_g0_online_smoke import (
    CONTEXT, DURATIONS, closed_boundary, probe_once, main,
)

UTC = timezone.utc
NOW = datetime(2026, 10, 28, 12, 15, tzinfo=UTC)
NOW_MS = int(NOW.timestamp() * 1000)


def kline(open_ms, size, base="10", quote="1000"):
    return [open_ms, "100", "102", "99", "101", base,
            open_ms + size - 1, quote, 42, "4", "400", "0"]


class Fixture:
    def __init__(self):
        self.calls = []
        self.invalid = None
        self.rate_weight = None

    def __call__(self, path, params=None, *, on_attempt=None):
        if on_attempt is None:
            raise AssertionError("NO_PRE_SEND_GUARD")
        on_attempt(path)
        self.calls.append((path, params))
        n = len(self.calls)
        if self.invalid == "network" and n == 1:
            raise LiveBlocked("MOCK_NETWORK_UNAVAILABLE")
        if self.invalid == "geo" and n == 1:
            raise LiveFailure("HTTP_451")
        if self.invalid == "retry" and n == 1:
            on_attempt(path)
            raise AssertionError("RETRY_WAS_NOT_BLOCKED")
        received = NOW_MS + 100 + 10 * n
        meta = {
            "path": path, "http_status": 200, "latency_ms": 100,
            "t0_local_ms": received - 100,
            "received_local_ms": received,
            "used_weight_1m": str(self.rate_weight if self.rate_weight is not None else n + 10),
        }
        if path == "/api/v3/time":
            return {"serverTime": NOW_MS}, meta
        if path == "/api/v3/exchangeInfo":
            return {"symbols": [{
                "symbol": "ETHUSDT" if self.invalid == "wrong_symbol" else "BTCUSDT",
                "quoteAsset": "USDT", "status": "TRADING",
                "isSpotTradingAllowed": True,
            }]}, meta
        if path == "/api/v3/ticker/24hr":
            return {
                "symbol": "BTCUSDT", "quoteVolume": "50000000",
                "bidPrice": "100", "askPrice": "100.01",
            }, meta
        if path != "/api/v3/klines":
            raise AssertionError("UNAPPROVED_ENDPOINT")
        assert params["symbol"] == "BTCUSDT"
        frame = params["interval"]
        first = int(params["startTime"])
        duration = DURATIONS[frame]
        count = int(params["limit"])
        rows = [kline(first + i * duration, duration) for i in range(count)]
        if self.invalid == "missing_child" and (
            (frame == "5m" and count == 21)
            or (frame == "1h" and count == 4)):
            rows.pop()
        if frame == "30m" and count == 1:
            rows[0][5], rows[0][7] = "60", "6000"
        if frame == "4h" and count == 1:
            rows[0][5], rows[0][7] = "40", "4000"
        if self.invalid == "unclosed_context" and frame in ("1d", "1w"):
            rows[0][6] += duration
        return rows, meta


def fixture_run(horizon, fake=None):
    f = fake or Fixture()
    with patch("urllib.request.urlopen", side_effect=AssertionError("NETWORK_FORBIDDEN")), \
         patch("socket.create_connection", side_effect=AssertionError("NETWORK_FORBIDDEN")):
        result = probe_once(horizon=horizon, getter=f,
                            local_ms=lambda: NOW_MS + 1000,
                            monotonic=lambda: 0.0)
    return result, f


class BoundedOnlineG0FixtureTests(unittest.TestCase):
    def test_both_horizons_actual_adapter_provenance_but_no_pit(self):
        for horizon, expected in ((Horizon.INTRADAY, 7), (Horizon.SWING, 8)):
            with self.subTest(horizon=horizon.value):
                row, fake = fixture_run(horizon)
                self.assertEqual(row["status"], "ONLINE_INTEGRATION_OBSERVED", row)
                self.assertEqual(row["attempt_count"], expected)
                self.assertEqual(len(fake.calls), expected)
                self.assertTrue(all(x["status"] == 200 for x in row["responses"]))
                self.assertEqual(row["child_count"], 6 if horizon is Horizon.INTRADAY else 4)
                self.assertEqual(row["core_5m_count"], 21)
                self.assertEqual(set(row["contexts"]), set(CONTEXT[horizon]))
                self.assertEqual(row["market_symbol"], "BTCUSDT")
                self.assertEqual(set(row["directions"]), {"UP", "DOWN"})
                self.assertEqual(row["parent"]["source_id"], "BINANCE:SPOT:PUBLIC_KLINES")
                for direction in ("UP", "DOWN"):
                    self.assertEqual(row["directions"][direction]["status"],
                                     "SOFTWARE_CONTRACTS_VALID_ON_SYNTHETIC_INPUT")
                    self.assertEqual(row["directions"][direction]["scientific_g0"],
                                     "NO_GO_PIT_UNVERIFIED")
                    self.assertEqual(row["directions"][direction]["score_status"],
                                     "SCORE_UNAVAILABLE")
                    self.assertEqual(set(row["directions"][direction]["context"]),
                                     set(CONTEXT[horizon]))
                self.assert_no_scientific_pit(row)

    def assert_no_scientific_pit(self, row):
        self.assertEqual(row["scientific_g0"], "NO_GO_PIT_UNVERIFIED")
        self.assertFalse(row["independent_pit_verified"] if "independent_pit_verified" in row else False)
        self.assertIsNone(row["source_publication_time"])
        self.assertIsNone(row["independent_utc_uncertainty_ms"])
        self.assertEqual(row["qualification_status"], "NOT_EVALUATED")
        self.assertEqual(row["score_status"], "SCORE_UNAVAILABLE")
        self.assertIsNone(row["score"])
        self.assertIsNone(row["signal_id"])
        self.assertFalse(row["publishable"])
        self.assertFalse(row["delivery_authorized"])

    def test_missing_child_is_data_unavailable_not_fake_pass(self):
        for horizon in Horizon:
            fake = Fixture()
            fake.invalid = "missing_child"
            row, _ = fixture_run(horizon, fake)
            self.assertEqual(row["status"], "ONLINE_INPUT_UNAVAILABLE")
            self.assertIn("CHILD_OR_BASE_HISTORY_UNAVAILABLE", row["reason"])
            self.assertLessEqual(row["attempt_count"], 8)
            self.assert_no_scientific_pit(row)

    def test_wrong_symbol_at_http_fetch_is_rejected_early(self):
        fake = Fixture()
        fake.invalid = "wrong_symbol"
        row, _ = fixture_run(Horizon.INTRADAY, fake)
        self.assertEqual(row["status"], "ONLINE_INPUT_UNAVAILABLE")
        self.assertEqual(row["reason"], "PUBLIC_API_SYMBOL_MISMATCH")
        self.assertEqual(row["attempt_count"], 3)
        self.assert_no_scientific_pit(row)

    def test_incomplete_daily_weekly_context_fail_without_substitution(self):
        for frame in ("1d", "1w"):
            fake = Fixture()
            fake.invalid = "unclosed_context"
            row, _ = fixture_run(Horizon.SWING, fake)
            self.assertEqual(row["status"], "ONLINE_INPUT_UNAVAILABLE")
            self.assertIn("CONTEXT_CLOSE_OR_UTC_ALIGNMENT_INVALID", row["reason"])
            self.assertLessEqual(row["attempt_count"], 8)
            self.assert_no_scientific_pit(row)

    def test_network_block_and_weight_guard_without_retries(self):
        fake = Fixture()
        fake.invalid = "network"
        row, _ = fixture_run(Horizon.INTRADAY, fake)
        self.assertEqual(row["status"], "ONLINE_BLOCKED")
        self.assertEqual(row["attempt_count"], 1)
        self.assert_no_scientific_pit(row)

        fake = Fixture()
        fake.rate_weight = 1000
        row, _ = fixture_run(Horizon.INTRADAY, fake)
        self.assertEqual(row["status"], "ONLINE_BLOCKED")
        self.assertEqual(row["reason"], "RATE_WEIGHT_STOP")
        self.assertEqual(row["attempt_count"], 1)
        self.assert_no_scientific_pit(row)

    def test_geographical_or_waf_http_denial_is_online_blocked_not_code_failure(self):
        fake = Fixture()
        fake.invalid = "geo"
        row, _ = fixture_run(Horizon.INTRADAY, fake)
        self.assertEqual(row["status"], "ONLINE_BLOCKED")
        self.assertEqual(row["reason"], "HTTP_451")
        self.assertEqual(row["attempt_count"], 1)
        self.assert_no_scientific_pit(row)

    def test_second_physical_attempt_is_blocked(self):
        fake = Fixture()
        fake.invalid = "retry"
        row, _ = fixture_run(Horizon.INTRADAY, fake)
        self.assertEqual(row["status"], "ONLINE_BLOCKED")
        self.assertEqual(row["reason"], "HTTP_RETRY_DISABLED")
        self.assertEqual(row["attempt_count"], 1)
        self.assert_no_scientific_pit(row)

    def test_closed_weekly_monday_boundary_and_cli_opt_in(self):
        self.assertEqual(closed_boundary(NOW_MS, "1w"),
                         int(datetime(2026, 10, 26, tzinfo=UTC).timestamp() * 1000))
        with patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as exc:
                main(["--horizon", "INTRADAY"])
        self.assertEqual(exc.exception.code, 2)
        with self.assertRaisesRegex(ValueError, "ONLY_BTCUSDT_TYPED_HORIZON_ALLOWED"):
            probe_once(horizon=Horizon.SWING, symbol="ETHUSDT", getter=Fixture())


if __name__ == "__main__":
    unittest.main()
