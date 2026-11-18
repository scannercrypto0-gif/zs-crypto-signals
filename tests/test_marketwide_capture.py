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
            opener = Opener(Response(header="203"))
            capture = PublicCapture(root, opener=opener)
            with self.assertRaises(PauseScan):
                capture.get("exchangeInfo", {})
            self.assertEqual(capture.attempts, 1)
            self.assertEqual(capture.used, 203)
            self.assertTrue((Path(root)/"response-1.private").exists())
            with self.assertRaises(PauseScan):
                capture.get("ticker/24hr", {})
            self.assertEqual(opener.calls, 1)

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
