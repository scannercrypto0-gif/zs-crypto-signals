import io
from pathlib import Path
import tempfile
from unittest import TestCase

from zs_smart_gate.marketwide_capture import PublicCapture
from zs_smart_gate.marketwide_cursor import PauseScan


class Response(io.BytesIO):
    def __init__(self, raw=b'{}', header="21", status=200):
        super().__init__(raw)
        self.status = status
        self.headers = {"X-MBX-USED-WEIGHT-1M": header}


class Opener:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def open(self, request, timeout):
        self.calls += 1
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


class MarketCaptureTests(TestCase):
    def test_quota_stops_with_durable_actual_body_pin(self):
        with tempfile.TemporaryDirectory() as root:
            opener = Opener(Response(header="5500"))
            capture = PublicCapture(root, opener=opener)
            with self.assertRaises(PauseScan):
                capture.get("exchangeInfo", {})
            self.assertEqual(capture.attempts, 1)
            self.assertEqual(capture.used, 5500)
            self.assertTrue((Path(root)/"response-1.private").exists())
            with self.assertRaises(PauseScan):
                capture.get("ticker/24hr", {})
            self.assertEqual(opener.calls, 1)

    def test_540_header_is_below_new_guard(self):
        with tempfile.TemporaryDirectory() as root:
            capture = PublicCapture(root, opener=Opener(Response(header="540")))
            receipt = capture.get("exchangeInfo", {})
            self.assertEqual(receipt["path"], "exchangeInfo")
            self.assertEqual(capture.used, 540)

    def test_timeout_and_unknown_header_never_retry(self):
        for response in (TimeoutError(), Response(header=None), Response(raw=b'invalid')):
            with tempfile.TemporaryDirectory() as root:
                opener = Opener(response)
                capture = PublicCapture(root, opener=opener)
                with self.assertRaises(PauseScan):
                    capture.get("exchangeInfo", {})
                self.assertEqual(opener.calls, 1)
                self.assertIn('"state":"RESERVED"', (Path(root)/"requests.jsonl").read_text())

    def test_deadline_and_endpoint_guard_have_no_http(self):
        clock = [0]
        with tempfile.TemporaryDirectory() as root:
            opener = Opener(Response())
            capture = PublicCapture(root, opener=opener, monotonic=lambda: clock[0])
            clock[0] = 111
            with self.assertRaises(PauseScan):
                capture.get("exchangeInfo", {})
            with self.assertRaises(ValueError):
                capture.get("order", {})
            self.assertEqual(opener.calls, 0)

    def test_weights_and_symbol_filter_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            opener = Opener(Response())
            capture = PublicCapture(root, opener=opener)
            with self.assertRaises(ValueError):
                capture.get("exchangeInfo", {"symbol": "BTCUSDT"})
            capture.weight = 130
            with self.assertRaises(PauseScan):
                capture.get("exchangeInfo", {})
            self.assertEqual(opener.calls, 0)

    def test_quota_preserves_complete_listing_for_offline_discovery(self):
        import json
        from zs_smart_gate.marketwide_capture import discovery_only
        payload = dict(symbols=[dict(symbol="OTHERUSDT", baseAsset="OTHER", quoteAsset="USDT",
                                    status="TRADING", isSpotTradingAllowed=True)])
        with tempfile.TemporaryDirectory() as root:
            capture = PublicCapture(root, opener=Opener(Response(
                raw=json.dumps(payload).encode(), header="5500")))
            with self.assertRaises(PauseScan):
                capture.get("exchangeInfo", {"showPermissionSets": "false"})
            result = discovery_only(capture.receipts[0])
            self.assertEqual(result["spot_discovered"], 1)
            self.assertEqual(result["actually_evaluated"], 0)
            self.assertEqual(result["rows"][0]["eligibility"], "UNKNOWN")


class BoundaryPreflightRegressionTests(TestCase):
    """Deterministic 30m entry-window checks with zero live HTTP."""

    def test_inside_first_90_seconds_is_admitted(self):
        from zs_smart_gate.marketwide_capture import boundary_preflight
        boundary = 1795086000000
        for age in (0, 45, 90):
            receipt = boundary_preflight(boundary / 1000 + age, boundary_ms=boundary)
            self.assertTrue(receipt["admitted"])
            self.assertEqual(receipt["boundary_ms"], boundary)
            self.assertEqual(receipt["freshness_window_seconds"], 90)

    def test_expired_window_is_blocked_with_explicit_age(self):
        from zs_smart_gate.marketwide_capture import boundary_preflight
        boundary = 1795086000000
        expired = boundary_preflight(boundary / 1000 + 1020, boundary_ms=boundary)
        self.assertEqual(expired["status"], "CANDLE_ENTRY_WINDOW_EXPIRED")
        self.assertFalse(expired["admitted"])
        self.assertEqual(expired["age_seconds"], 1020.0)
        self.assertEqual(expired["remaining_seconds"], 0.0)

    def test_outside_window_prevents_every_http_even_with_admin_clock(self):
        from unittest.mock import patch
        from zs_smart_gate.marketwide_capture import run
        with tempfile.TemporaryDirectory() as root:
            # A real PublicCapture would attempt HTTP if the preflight regressed.
            opener = Opener(Response())
            transport = PublicCapture(root, opener=opener)
            with patch("zs_smart_gate.marketwide_capture.time.time",
                       return_value=1795086000 + 1020):
                with patch("zs_smart_gate.marketwide_capture._is_admin", return_value=True):
                    receipt = run(Path(root), Path(root)/"cursor.sqlite",
                                  transport=transport, admin_clock_pilot=False)
            self.assertEqual(receipt["stop"], "CANDLE_ENTRY_WINDOW_EXPIRED_BEFORE_DISCOVERY")
            self.assertEqual(receipt["requests"], 0)
            self.assertEqual(receipt["estimated_weight"], 0)
            self.assertEqual(opener.calls, 0)
            self.assertIsNone(receipt["funnel"])
            self.assertEqual(receipt["qualification"], "QV1_REAL_POLICY_BLOCKED")
            self.assertTrue((Path(root)/"result.json").is_file())

    def test_clock_acceptance_never_overrides_expired_window(self):
        from unittest.mock import patch
        from zs_smart_gate.marketwide_capture import run
        from zs_smart_gate import ops_windows_time as clock
        from zs_smart_gate.stage05_contracts import canonical, digest
        policy = {"policy_id": clock.POLICY_ID, "source": clock.SOURCE,
                  "limits": clock.CANDIDATE}
        self.assertEqual(digest(canonical(policy)), clock.REVIEWED_POLICY_SHA256)
        with tempfile.TemporaryDirectory() as root:
            opener = Opener(Response())
            transport = PublicCapture(root, opener=opener)
            with patch("zs_smart_gate.marketwide_capture.time.time",
                       return_value=1795086000 + 1020):
                with patch("zs_smart_gate.marketwide_capture._is_admin", return_value=True):
                    receipt = run(Path(root), Path(root)/"cursor.sqlite",
                                  transport=transport, admin_clock_pilot=True)
            self.assertEqual(receipt["requests"], 0)
            self.assertEqual(opener.calls, 0)
            self.assertIsNone(receipt["snapshot"])
            self.assertIsNone(receipt["funnel"])
            self.assertEqual(receipt["live_e2e"], "LIVE_E2E_NOT_PROVEN")


class Clock73SyntheticFullChainTests(TestCase):
    """Actual four-frame packet/parser/ledger on fake public HTTP, never network."""

    def _run_fixture(self, *, symbols, expire_after=None):
        import json
        from urllib.parse import parse_qs, urlsplit
        from unittest.mock import patch
        from test_marketwide_research import packet
        from test_p0_clock_73 import valid_receipts
        from zs_smart_gate import ops_windows_time as clock
        from zs_smart_gate.marketwide_capture import run

        fixtures = {symbol: packet(symbol=symbol) for symbol in symbols}
        exemplar = next(iter(fixtures.values()))
        boundary_ms = exemplar["boundary_ms"]
        epoch = [boundary_ms / 1000 + 10]
        observed = exemplar["frames"]["5m"]["received_at"]

        class FakePublicHTTP:
            def __init__(self):
                self.calls = []
            def open(self, request, timeout):
                parsed = urlsplit(request.full_url)
                endpoint = parsed.path.rsplit("/", 1)[-1]
                params = parse_qs(parsed.query)
                self.calls.append((endpoint, params))
                if endpoint == "exchangeInfo":
                    payload = {"symbols": [
                        {"symbol": sym, "baseAsset": sym.removesuffix("USDT"),
                         "quoteAsset": "USDT", "status": "TRADING",
                         "isSpotTradingAllowed": True}
                        for sym in symbols]}
                elif endpoint == "ticker/24hr":
                    payload = [{"symbol": sym, "quoteVolume": "50000000",
                                "closeTime": boundary_ms} for sym in symbols]
                elif endpoint == "ticker/bookTicker":
                    payload = [{"symbol": sym, "bidPrice": "100",
                                "askPrice": "100.01"} for sym in symbols]
                elif endpoint == "klines":
                    symbol = params["symbol"][0]
                    frame = params["interval"][0]
                    payload = fixtures[symbol]["frames"][frame]["rows"]
                    self_test.assertEqual(params["endTime"][0],
                                          str(boundary_ms // {
                                              "5m": 300000, "30m": 1800000,
                                              "1h": 3600000, "4h": 14400000
                                          }[frame] * {
                                              "5m": 300000, "30m": 1800000,
                                              "1h": 3600000, "4h": 14400000
                                          }[frame] - 1))
                    if expire_after == "first_packet" and frame == "4h":
                        epoch[0] = boundary_ms / 1000 + 91
                    if expire_after == "first_frame" and frame == "5m":
                        epoch[0] = boundary_ms / 1000 + 91
                else:
                    raise AssertionError("UNEXPECTED_TEST_ENDPOINT")
                return Response(raw=json.dumps(payload).encode(), header="1544")

        self_test = self
        fake = FakePublicHTTP()
        w32 = valid_receipts()
        clock_commands = {tuple(argv): w32[name]
                          for name, argv in clock.COMMANDS.items()}
        with tempfile.TemporaryDirectory() as root:
            capture = PublicCapture(root, opener=fake)
            with patch("zs_smart_gate.marketwide_capture.time.time",
                       side_effect=lambda: epoch[0]), \
                 patch("zs_smart_gate.marketwide_capture.now", return_value=observed), \
                 patch("zs_smart_gate.marketwide_capture._is_admin", return_value=True), \
                 patch("zs_smart_gate.marketwide_capture.command",
                       side_effect=lambda argv: clock_commands[tuple(argv)]), \
                 patch("zs_smart_gate.marketwide_capture.sync_age", return_value=10):
                result = run(Path(root), Path(root) / "cursor.sqlite",
                             transport=capture, admin_clock_pilot=True)
            persisted = json.loads((Path(root) / "result.json").read_text())
            self.assertEqual(persisted, result)
            self.assertEqual(result["clock"]["status"], "OPERATIONAL_TIME_ACCEPTED")
            self.assertEqual(result["clock"]["policy_sha256"], clock.REVIEWED_POLICY_SHA256)
            self.assertEqual(result["qualification"], "QV1_REAL_POLICY_BLOCKED")
            self.assertEqual(result["live_e2e"], "LIVE_E2E_NOT_PROVEN")
            self.assertEqual(result["estimated_weight"], capture.weight)
            self.assertEqual(result["requests"], len(fake.calls))
            self.assertTrue((Path(root) / "requests.jsonl").is_file())
            return result, fake.calls

    def test_positive_end_to_end_four_closed_timeframes_one_pair(self):
        result, calls = self._run_fixture(symbols=["OTHERUSDT"])
        self.assertEqual([endpoint for endpoint, _ in calls],
                         ["exchangeInfo", "ticker/24hr", "ticker/bookTicker",
                          "klines", "klines", "klines", "klines"])
        self.assertEqual([params["interval"][0] for endpoint, params in calls
                          if endpoint == "klines"], ["5m", "30m", "1h", "4h"])
        funnel = result["funnel"]
        self.assertEqual(funnel["attempted"], 1)
        self.assertEqual(funnel["source_validated"], 1)
        self.assertEqual(funnel["directionally_evaluated"], 2)
        self.assertEqual(funnel["coverage"], "MARKET_COVERAGE_VERIFIED")
        self.assertIsNone(funnel["stopped_reason"])
        directions = funnel["actual_evaluations"][0]["results"]
        self.assertEqual({row["direction"] for row in directions}, {"UP", "DOWN"})
        self.assertTrue(all(row["source_validated"] for row in directions))
        self.assertEqual({row["signal_id"] for row in directions}, {None})
        self.assertEqual(funnel["production_signals"], 0)

    def test_expiry_after_first_packet_before_second_pair_is_precise(self):
        result, calls = self._run_fixture(
            symbols=["OTHERUSDT", "SECONDUSDT"], expire_after="first_packet")
        self.assertEqual(len(calls), 7)
        self.assertEqual(sum(endpoint == "klines" for endpoint, _ in calls), 4)
        self.assertEqual(result["funnel"]["attempted"], 1)
        self.assertEqual(result["funnel"]["source_validated"], 1)
        self.assertEqual(result["funnel"]["eligible"], 2)
        self.assertEqual(result["funnel"]["stopped_reason"], "CANDLE_ENTRY_WINDOW_EXPIRED")
        self.assertEqual(result["stop"], "CANDLE_ENTRY_WINDOW_EXPIRED")
        self.assertFalse(result["funnel"]["stopped_due_to_quota"])

    def test_mid_packet_expiry_stops_next_candle_http_fail_closed(self):
        result, calls = self._run_fixture(
            symbols=["OTHERUSDT"], expire_after="first_frame")
        self.assertEqual(len(calls), 4)
        self.assertEqual(sum(endpoint == "klines" for endpoint, _ in calls), 1)
        self.assertEqual(result["funnel"]["attempted"], 1)
        self.assertEqual(result["funnel"]["source_validated"], 0)
        self.assertEqual(result["funnel"]["stopped_reason"], "CANDLE_ENTRY_WINDOW_EXPIRED")
        self.assertEqual(result["stop"], "CANDLE_ENTRY_WINDOW_EXPIRED")
        self.assertEqual(result["funnel"]["coverage"], "MARKET_COVERAGE_PARTIAL")
        self.assertFalse(result["funnel"]["stopped_due_to_quota"])
