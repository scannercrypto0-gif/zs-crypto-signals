"""ORDER-025 private verifier tests. ALL archives here are SYNTHETIC TEST BYTES.

A mocked temporary REAL_ARCHIVE_PRIVATE catalog is deliberately used solely
to exercise source-status guards. No published/private historical market
outcome is made or implied by these unit tests.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zs_smart_gate.stage03_order022 import ResearchBlocked, canonical, freeze, run
from test_stage03_order022 import all_fixture_archives

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "order025-private-verify.py"
spec = importlib.util.spec_from_file_location("order025_verification", SCRIPT)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def synthetic_private_run(folder):
    """Create synthetic ZIPs in a temporary location, never as real evidence."""
    root = Path(folder)
    archive_dir = root / "verified_5m_archives"
    cat = all_fixture_archives(archive_dir)
    cat["source_kind"] = "REAL_ARCHIVE_PRIVATE"
    for file in cat["files"]:
        file["source"] = "BINANCE_VISION_SPOT_PUBLIC_ARCHIVE"
    catalog = root / "synthetic-catalog.json"
    catalog.write_bytes(canonical(cat))
    freeze(archive_dir, catalog, root / "frozen-experiment.json")
    result = run(root / "frozen-experiment.json", archive_dir,
                 root / "research-results.sqlite", root / "verified-restore.sqlite")
    report = root / "historical-price-only-report.json"
    report.write_bytes(canonical(result)+b"\n")
    report_sha = hashlib.sha256(report.read_bytes()).hexdigest()
    manifest_sha = hashlib.sha256((root / "frozen-experiment.json").read_bytes()).hexdigest()
    (root / "private-run-receipt.json").write_bytes(canonical({
        "result_report_sha256":report_sha,
        "frozen_manifest_sha256":manifest_sha,
        "verified_private_archive_count":12,
        "source_index_present_and_pinned":False
    })+b"\n")
    return report_sha


class IndependentAuditTests(unittest.TestCase):
    def test_separate_counter_matches_frozen_engine_with_synthetic_22bar(self):
        from test_stage03_order025 import candles
        from zs_smart_gate.stage03_order022 import evaluate_rows, read_protocol
        protocol, _ = read_protocol()
        bars = candles("2025-02-01T00:00:00Z", triggers=(25, 30, 43))
        independent = verify.independent_count(bars, protocol)
        accepted, events = evaluate_rows(bars,"BTCUSDT",protocol,"SYNTHETIC_TEST")
        self.assertEqual(independent["DEV"]["raw"],3)
        self.assertEqual(independent["DEV"]["suppressed"],1)
        self.assertEqual(independent["DEV"]["admitted"],2)
        self.assertEqual(independent["DEV"]["not_up"],2)
        self.assertEqual(independent["DEV"]["raw"],
                         accepted["DEV"]["partial_price_volume_patterns"])
        self.assertEqual(independent["DEV"]["suppressed"],
                         accepted["DEV"]["outcome_overlap_suppressed"])
        self.assertEqual(len(events["DEV"]),independent["DEV"]["admitted"])

    def test_synthetic_full_private_audit_reconciles_without_market_request(self):
        with tempfile.TemporaryDirectory() as folder:
            sha = synthetic_private_run(folder)
            with patch("socket.socket",side_effect=AssertionError("NETWORK_FORBIDDEN")):
                evidence = verify.private_audit(folder,sha)
            self.assertEqual(evidence["status"],"PRIVATE_OFFLINE_ARITHMETIC_REPRODUCED")
            self.assertEqual(evidence["source_zip_sha256_verified"],12)
            self.assertEqual(evidence["market_requests"],0)
            self.assertEqual(evidence["statistical_qualification"],"BLOCKED")
            self.assertFalse(evidence["publishable"])
            self.assertEqual(evidence["sqlite_report_restore"],
                             "MATCHES_ORIGINAL_PRIVATE_JOURNAL")
            self.assertEqual(set(evidence["partition_counts"]),{
                "BTCUSDT:DEV","BTCUSDT:OOS","ETHUSDT:DEV","ETHUSDT:OOS"})
            self.assertNotIn(str(Path(folder).resolve()),str(evidence))

    def test_wrong_expected_hash_rejected_prior_to_any_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            synthetic_private_run(folder)
            with self.assertRaisesRegex(ResearchBlocked,"PRIVATE_REPORT_SHA_MISMATCH"):
                verify.private_audit(folder,"0"*64)

    def test_tampered_report_counts_cannot_pass_with_rehashed_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            synthetic_private_run(folder)
            report = Path(folder)/"historical-price-only-report.json"
            obj = json.loads(report.read_bytes())
            obj["partition_results"]["BTCUSDT:DEV"]["partial_event_count"] += 1
            report.write_bytes(canonical(obj)+b"\n")
            expected = hashlib.sha256(report.read_bytes()).hexdigest()
            receipt = Path(folder)/"private-run-receipt.json"
            old = json.loads(receipt.read_bytes())
            old["result_report_sha256"] = expected
            receipt.write_bytes(canonical(old)+b"\n")
            with self.assertRaisesRegex(ResearchBlocked,"INDEPENDENT_REPLAY_COUNT_MISMATCH"):
                verify.private_audit(folder,expected)

    def test_mutated_archive_cannot_pass_original_pin(self):
        with tempfile.TemporaryDirectory() as folder:
            sha = synthetic_private_run(folder)
            archive = Path(folder)/"verified_5m_archives"/"BTCUSDT-5m-2025-02.zip"
            archive.write_bytes(archive.read_bytes()+b"touched")
            with self.assertRaisesRegex(ResearchBlocked,"FROZEN_ZIP_NOT_REPRODUCIBLE"):
                verify.private_audit(folder,sha)

    def test_corrupted_original_backup_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            sha = synthetic_private_run(folder)
            backup = Path(folder)/"verified-restore.sqlite"
            backup.write_bytes(b"not-an-SQLite-backup")
            with self.assertRaises(Exception):
                verify.private_audit(folder,sha)

    def test_not_recreating_unavailable_private_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ResearchBlocked,"REQUIRED_PRIVATE_INPUT_MISSING"):
                verify.private_audit(folder)


if __name__ == "__main__":
    unittest.main()
