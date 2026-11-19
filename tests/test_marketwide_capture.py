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
