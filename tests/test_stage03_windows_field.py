"""Bounded field runner offline contract checks. NO HTTP requests."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from zs_smart_gate import stage03_windows_field_capture as cap
from zs_smart_gate.stage03_windows_field_review import check_file, verify


class TestFieldCaptureContract(unittest.TestCase):
    def test_fixed_budget_and_no_auth(self):
        self.assertEqual([len(cap.PHASES[x]) for x in ("pre", "post")], [4, 6])
        self.assertEqual({v.get("symbol") for x in cap.PHASES.values() for _, v in x}, {"BTCUSDT"})
        self.assertNotIn("api_key", cap.__dict__)
        self.assertEqual(cap.BASE, "https://data-api.binance.vision")

    def test_forming_kline_rejected(self):
        bar = [1000, "2", "3", "1", "2", "4", 1000+300000-1, "8", 1, "0", "0"]
        res = cap.sanitize_payload("/api/v3/klines",
              {"interval": "5m", "limit": "80", "symbol": "BTCUSDT"}, [bar], 2000)
        self.assertEqual(res["bars"], [])
        self.assertEqual(res["forming_excluded"], 1)

    def test_hashed_receipt_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "receipt.json"
            obj = {"version": cap.VERSION, "completed": True, "phase": "pre", "symbol": "BTCUSDT"}
            obj["record_sha256"] = cap.digest(obj)
            path.write_text(json.dumps(obj), encoding="utf-8")
            self.assertEqual(check_file(path)["record_sha256"], obj["record_sha256"])
            obj["symbol"] = "ETHUSDT"
            path.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA_MISMATCH"):
                check_file(path)

    def test_missing_real_receipt_fails_closed(self):
        with self.assertRaises(FileNotFoundError):
            verify("never-exists-pre.json", "never-exists-post.json")


if __name__ == "__main__":
    unittest.main()
