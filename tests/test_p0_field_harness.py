"""Negative-focused, entirely offline ZS03 field safeguards. No market connection."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/p0-field-harness.py"
TEMPLATE = ROOT / "research/order025/p0-readiness/field-manifest-template-006.json"
spec = importlib.util.spec_from_file_location("p0_field_harness", SCRIPT)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
RAW = h.synthetic_fixture()
DIGEST = hashlib.sha256(RAW).hexdigest()


class FieldHarnessOffline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "attempts.jsonl"
        self.ctx = h.synthetic_context()

    def start(self, context=None):
        j = h.SyntheticJournal(self.path, context if context is not None else self.ctx, RAW)
        self.addCleanup(j.close)
        return j

    def test_default_real_field_is_not_authorized_and_cli_cannot_arm(self):
        self.assertFalse(h.REAL_FIELD_AUTHORIZED)
        ok = subprocess.run([sys.executable, str(SCRIPT), "--describe"],
                            text=True, capture_output=True, timeout=10)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertFalse(json.loads(ok.stdout)["permission_to_dispatch"]
                         if "permission_to_dispatch" in json.loads(ok.stdout)
                         else json.loads(ok.stdout)["market_transport_present"])
        for flag in ("--live", "--arm", "--network", "--execute"):
            v = subprocess.run([sys.executable, str(SCRIPT), flag],
                               capture_output=True, timeout=10)
            self.assertNotEqual(v.returncode, 0)

    def test_base_11_rest_attempts_weight_42_and_one_reserve_cap_46(self):
        j = self.start()
        for endpoint in h.REST_BASE:
            j.reserve_rest(endpoint)
        self.assertEqual((j.rest_count, j.rest_weight), (11, 42))
        j.reserve_rest("ticker/bookTicker/BTCUSDT,ETHUSDT", reserve_approved=True)
        self.assertEqual((j.rest_count, j.rest_weight), (12, 46))
        with self.assertRaisesRegex(h.FieldBlocked, "CAP"):
            j.reserve_rest("klines/BTCUSDT/5m", reserve_approved=True)
        self.assertEqual(h.verify_journal(self.path)["rows"], 13)
        self.assertFalse(j.snapshot()["permission_to_dispatch"])

    def test_missing_license_blocked_before_journal_creation(self):
        self.ctx["licensed_for"] = None
        with self.assertRaisesRegex(h.FieldBlocked, "LICENSE"):
            self.start()
        self.assertFalse(self.path.exists())

    def test_missing_pm_or_owner_authorization_blocked(self):
        for key in ("pm_go", "owner_go"):
            c = h.synthetic_context()
            c[key] = None
            with self.subTest(key=key), self.assertRaisesRegex(h.FieldBlocked, "APPROVALS"):
                h.check_synthetic_context(c, RAW)

    def test_real_host_or_real_mode_cannot_be_armed(self):
        for k, value in (("host", "data-api.binance.vision"),
                         ("host", "https://data-api.binance.vision"),
                         ("mode", "REAL"), ("armed", True)):
            c = h.synthetic_context()
            c[k] = value
            with self.subTest(k=k), self.assertRaises(h.FieldBlocked):
                h.check_synthetic_context(c, RAW)

    def test_off_allowlist_endpoints_pairs_and_parameters(self):
        j = self.start()
        for endpoint in ("klines/BTCUSDT/30m",
                         "klines/DOGEUSDT/5m",
                         "https://data-api.binance.vision/api/v3/klines",
                         "exchangeInfo/ALL",
                         "ticker/24hr/ALL", "accounts/withdraw",
                         "klines/BTCUSDT/5m?limit=9999"):
            with self.subTest(endpoint=endpoint), self.assertRaisesRegex(
                    h.FieldBlocked, "NOT_ALLOWLISTED"):
                j.reserve_rest(endpoint)
        self.assertEqual(j.rest_count, 0)

    def test_exchangeinfo_repeat_forbidden_even_if_reserve_approved(self):
        j = self.start()
        for endpoint in h.REST_BASE:
            j.reserve_rest(endpoint)
        with self.assertRaisesRegex(h.FieldBlocked, "EXCHANGEINFO_REPEAT"):
            j.reserve_rest("exchangeInfo/BTCUSDT,ETHUSDT", reserve_approved=True)

    def test_retry_or_reserve_before_base_complete_blocked(self):
        j = self.start()
        j.reserve_rest("klines/BTCUSDT/5m")
        with self.assertRaisesRegex(h.FieldBlocked, "EXTRA_REST"):
            j.reserve_rest("klines/BTCUSDT/5m", reserve_approved=True)
        self.assertEqual(j.rest_count, 1)

    def test_reserve_without_explicit_consent_blocked(self):
        j = self.start()
        for endpoint in h.REST_BASE:
            j.reserve_rest(endpoint)
        with self.assertRaisesRegex(h.FieldBlocked, "EXTRA_REST"):
            j.reserve_rest("klines/BTCUSDT/5m")

    def test_ws_allowlist_six_initial_and_six_extra_cap(self):
        j = self.start()
        for stream in sorted(h.WS_BASE):
            j.reserve_ws(stream)
        for stream in sorted(h.WS_BASE):
            j.reserve_ws(stream, reserve_approved=True)
        self.assertEqual(j.ws_count, 12)
        with self.assertRaisesRegex(h.FieldBlocked, "WS_SUBSCRIPTION_CAP"):
            j.reserve_ws(sorted(h.WS_BASE)[0], reserve_approved=True)

    def test_ws_repeated_without_consent_or_base_completed_denied(self):
        j = self.start()
        stream = sorted(h.WS_BASE)[0]
        j.reserve_ws(stream)
        with self.assertRaisesRegex(h.FieldBlocked, "EXTRA_WS"):
            j.reserve_ws(stream, reserve_approved=True)

    def test_off_allowlist_ws_rejected(self):
        j = self.start()
        for stream in ("!userData", "btcusdt@trade", "dogeusdt@ticker",
                       "wss://data-stream.binance.vision"):
            with self.assertRaisesRegex(h.FieldBlocked, "WS_STREAM_NOT_ALLOWLISTED"):
                j.reserve_ws(stream)

    def test_status_429_418_503_and_invalid_fail_closed(self):
        for status in (429, 418, 503, -1, "200"):
            with self.subTest(status=status):
                with tempfile.TemporaryDirectory() as tmp:
                    j = h.SyntheticJournal(Path(tmp)/"events", h.synthetic_context(), RAW)
                    try:
                        with self.assertRaisesRegex(h.FieldBlocked, "TRANSPORT_FAILURE"):
                            j.observe_status(status)
                        with self.assertRaisesRegex(h.FieldBlocked, "EVENT_ALREADY_BLOCKED"):
                            j.reserve_rest("klines/BTCUSDT/5m")
                    finally:
                        j.close()

    def test_ws_disconnect_halts_no_automatic_reconnect(self):
        j = self.start()
        j.reserve_ws("btcusdt@bookTicker")
        with self.assertRaisesRegex(h.FieldBlocked, "NO_AUTOMATIC_RETRY"):
            j.observe_disconnect()
        with self.assertRaisesRegex(h.FieldBlocked, "EVENT_ALREADY_BLOCKED"):
            j.reserve_ws("ethusdt@bookTicker")

    def test_stale_unauthenticated_wrong_peer_and_leap_block(self):
        failures = [
            ("nts_authenticated", False),
            ("source_fresh", False),
            ("leap_normal", False),
            ("monotonic_ok", False),
            ("ntpdata_selected", "OTHER_PEER"),
            ("tracking_selected", None),
        ]
        for k, v in failures:
            c = h.synthetic_context()
            c["clock"][k] = v
            with self.subTest(k=k), self.assertRaisesRegex(h.FieldBlocked, "CLOCK"):
                h.check_synthetic_context(c, RAW)

    def test_utc_uncertainty_must_be_strictly_less_than_1p5s(self):
        for value in (1_500_000_000, 1_500_000_001, -1, None, True):
            c = h.synthetic_context()
            c["clock"]["utc_uncertainty_ns"] = value
            with self.subTest(value=value), self.assertRaisesRegex(h.FieldBlocked, "UNCERTAINTY"):
                h.check_synthetic_context(c, RAW)

    def test_missing_asof_or_future_input_blocks(self):
        for key, value in (("input_available_latest_ns", None),
                           ("decision_earliest_ns", None),
                           ("input_available_latest_ns", 3_000_000_000)):
            c = h.synthetic_context()
            c["clock"][key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(
                    h.FieldBlocked, "AS_OF"):
                h.check_synthetic_context(c, RAW)

    def test_receipt_missing_or_raw_hash_mutated_blocks(self):
        for key, value in (("file_sha256_verified", False),
                           ("raw_sha256", "f" * 64),
                           ("raw_size_bytes", 10),
                           ("owner_external_custody", "REAL_OWNER_PASS"),
                           ("restored_raw_verified", False),
                           ("manifest_identity_verified", False)):
            c = h.synthetic_context()
            c["receipt"][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(h.FieldBlocked, "RECEIPT"):
                h.check_synthetic_context(c, RAW)

    def test_raw_restore_mismatch_and_missing_raw_blocks(self):
        j = self.start()
        for raw, checksum in ((RAW, "0" * 64),
                              (RAW[:-3], DIGEST)):
            with self.assertRaisesRegex(h.FieldBlocked, "MISMATCH"):
                j.register_raw("synthetic_copy.txt", raw,
                               restored_sha256=checksum,
                               owner_receipt_sha256=checksum)
        with self.assertRaisesRegex(h.FieldBlocked, "NOT_SYNTHETIC"):
            j.register_raw("synthetic_copy.txt", b"real raw",
                           restored_sha256=DIGEST, owner_receipt_sha256=DIGEST)

    def test_raw_file_count_cap_32(self):
        j = self.start()
        for i in range(32):
            j.register_raw(f"synthetic_{i}.txt", RAW, restored_sha256=DIGEST,
                           owner_receipt_sha256=DIGEST)
        self.assertEqual(j.raw_files, 32)
        with self.assertRaisesRegex(h.FieldBlocked, "CAP"):
            j.register_raw("synthetic_over.txt", RAW,
                           restored_sha256=DIGEST, owner_receipt_sha256=DIGEST)

    def test_raw_byte_cap_4_mib(self):
        # One large synthetic file, then another byte-bearing file exceeds 4MiB.
        raw = (b"origin=SYNTHETIC_ONLY\nmarket_requests=0\npayload=" +
               b"a" * (h.RAW_MAX - len(b"origin=SYNTHETIC_ONLY\nmarket_requests=0\npayload=")))
        c = h.synthetic_context(raw)
        j = h.SyntheticJournal(self.path, c, raw)
        self.addCleanup(j.close)
        d = hashlib.sha256(raw).hexdigest()
        j.register_raw("synthetic_large.txt", raw, restored_sha256=d, owner_receipt_sha256=d)
        with self.assertRaisesRegex(h.FieldBlocked, "CAP"):
            j.register_raw("synthetic_extra.txt", RAW,
                           restored_sha256=DIGEST, owner_receipt_sha256=DIGEST)

    def test_duplicate_file_name_refused(self):
        j = self.start()
        j.register_raw("synthetic_1.txt", RAW,
                       restored_sha256=DIGEST, owner_receipt_sha256=DIGEST)
        with self.assertRaisesRegex(h.FieldBlocked, "DUPLICATE"):
            j.register_raw("synthetic_1.txt", RAW,
                           restored_sha256=DIGEST, owner_receipt_sha256=DIGEST)

    def test_durable_journal_is_created_before_reservation_and_not_resumable(self):
        j = self.start()
        self.assertEqual(h.verify_journal(self.path)["rows"], 1)
        j.reserve_rest("klines/BTCUSDT/5m")
        self.assertEqual(h.verify_journal(self.path)["rows"], 2)
        with self.assertRaisesRegex(h.FieldBlocked, "NO_RESUME"):
            h.SyntheticJournal(self.path, h.synthetic_context(), RAW)

    def test_truncated_or_tampered_journal_detected(self):
        j = self.start()
        j.reserve_rest("klines/BTCUSDT/5m")
        j.close()
        original = self.path.read_bytes()
        self.path.write_bytes(original[:-1])
        with self.assertRaisesRegex(h.FieldBlocked, "TRUNCATED"):
            h.verify_journal(self.path)
        self.path.write_bytes(original.replace(b"REST_RESERVED_NO_SEND", b"REST_CHANGED_NO_SEND"))
        with self.assertRaisesRegex(h.FieldBlocked, "DIGEST_MISMATCH"):
            h.verify_journal(self.path)

    def test_missing_write_directory_fails_closed(self):
        with self.assertRaisesRegex(h.FieldBlocked, "JOURNAL_PARENT_MISSING"):
            h.SyntheticJournal(Path(self.tmp.name)/"missing"/"journal",
                               h.synthetic_context(), RAW)

    def test_manifest_template_is_unarmed_and_requires_future_approvals(self):
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(data["activation_state"], "DRAFT_NOT_ARMED")
        self.assertFalse(data["actual_field_capture_go"])
        self.assertIsNone(data["legal_rights"]["source_permission_evidence_sha256"])
        self.assertIsNone(data["event"]["utc_window_start"])
        self.assertEqual(data["budget"]["rest_physical_attempts_max"], 12)
        self.assertEqual(data["budget"]["rest_weight_max"], 46)
        self.assertEqual(data["budget"]["ws_physical_subscriptions_max"], 12)
        self.assertEqual(data["budget"]["max_raw_bytes"], h.RAW_MAX)


if __name__ == "__main__":
    unittest.main()
