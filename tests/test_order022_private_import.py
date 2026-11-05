"""Private-import safety tests: synthetic bytes only, no real source or network."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zs_smart_gate.stage03_order022 import ResearchBlocked, canonical, filename, MONTHS, SYMBOLS

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "order022-private-import.py"
spec = importlib.util.spec_from_file_location("private_import_022", SCRIPT)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def fake_source(root):
    root = Path(root)
    data = root / "batch-B"
    data.mkdir(parents=True)
    entries = []
    for symbol in SYMBOLS:
        for month in MONTHS:
            name = filename(symbol, month)
            content = f"SYNTHETIC_TEST_ONLY:{symbol}:{month}".encode()
            (data / name).write_bytes(content)
            entries.append(dict(name=name, symbol=symbol, interval="5m",
                                sha256=hashlib.sha256(content).hexdigest()))
    parent = root / "reviewed-build"
    parent.mkdir()
    old = parent / "manifest.json"
    old.write_bytes(canonical({"files": entries}))
    return old, entries


class PrivateImporterTests(unittest.TestCase):
    def test_missing_owner_drive_is_explicit_blocker(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                helper.perform(Path(d) / "not-mounted", Path(d) / "out")

    def test_prior_manifest_sha_and_exact_12_pins_are_required(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "source"
            manifest, entries = fake_source(source)
            with self.assertRaisesRegex(ResearchBlocked, "MANIFEST_JSON_MISSING_OR_SHA_MISMATCH"):
                helper.perform(source, Path(d) / "output")
            actual_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
            with patch.object(helper, "LEGACY_MANIFEST_SHA256", actual_sha):
                self.assertEqual(len(helper.original_010b_files(manifest)), 12)
                self.assertEqual(len(helper.archive_paths(
                    source, helper.original_010b_files(manifest))), 12)
                manifest.write_bytes(canonical({"files": entries[:-1]}))
                with self.assertRaisesRegex(ResearchBlocked, "TWELVE"):
                    helper.original_010b_files(manifest)

    def test_mutated_original_zip_rejected_against_preexisting_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "source"
            manifest, _ = fake_source(source)
            pins = helper.original_010b_files(manifest)
            (source / "batch-B" / filename("BTCUSDT", "2025-01")).write_bytes(b"TAMPERED")
            with self.assertRaisesRegex(ResearchBlocked, "ARCHIVE_MISSING_OR_SHA_MISMATCH"):
                helper.archive_paths(source, pins)

    def test_output_must_be_fresh_and_outside_private_source(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "source"
            source.mkdir()
            with self.assertRaisesRegex(ResearchBlocked, "OUTSIDE_SOURCE_ROOT"):
                helper.perform(source, source / "output")
            self.assertFalse((source / "output").exists())

    def test_one_step_sequence_no_network_mocked_real_analysis(self):
        """Never label synthetic example bytes as genuine market evidence."""
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "source"
            manifest, _ = fake_source(source)
            dest = Path(d) / "private-output"
            pinned = hashlib.sha256(manifest.read_bytes()).hexdigest()
            actions = []

            def check_inventory(stage, catalog):
                actions.append("inventory")
                self.assertEqual(len(list(Path(stage).glob("*.zip"))), 12)
                self.assertEqual(json.loads(Path(catalog).read_bytes())["schema"],
                                 "ORDER022_SOURCE_CATALOG_V1")
                return {"status": "COMPLETE_PINNED", "market_requests": 0}

            def mock_freeze(stage, catalog, output):
                actions.append("freeze")
                self.assertTrue((dest / "inventory.json").exists())
                Path(output).write_bytes(b'{"synthetic_fixture":true}')
                return {"manifest_sha256": hashlib.sha256(Path(output).read_bytes()).hexdigest()}

            def mock_run(manifest, stage, db, backup):
                actions.append("run")
                self.assertTrue(Path(manifest).exists())
                self.assertTrue((dest / "freeze-receipt.json").exists())
                return {"source_kind": "REAL_ARCHIVE_PRIVATE",
                        "status": "MOCKED_UNIT_TEST_NOT_ACTUAL_MARKET_REPLAY",
                        "market_requests": 0, "publishable": False}

            with patch.object(helper, "LEGACY_MANIFEST_SHA256", pinned), \
                 patch.object(helper, "inventory", side_effect=check_inventory), \
                 patch.object(helper, "freeze", side_effect=mock_freeze), \
                 patch.object(helper, "run", side_effect=mock_run), \
                 patch("socket.socket", side_effect=AssertionError("NETWORK_FORBIDDEN")):
                receipt = helper.perform(source, dest)
            self.assertEqual(actions, ["inventory", "freeze", "run"])
            self.assertEqual(receipt["verified_private_archive_count"], 12)
            self.assertEqual(receipt["market_requests"], 0)
            self.assertFalse(receipt["source_index_present_and_pinned"])
            self.assertTrue((dest / "private-run-receipt.json").exists())
            with self.assertRaisesRegex(ResearchBlocked, "PRIVATE_OUTPUT_MUST_BE_FRESH"):
                helper.perform(source, dest)

    def test_freeze_failure_never_produces_result_report(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "source"
            manifest, _ = fake_source(source)
            dest = Path(d) / "private-output"
            pinned = hashlib.sha256(manifest.read_bytes()).hexdigest()
            with patch.object(helper, "LEGACY_MANIFEST_SHA256", pinned), \
                 patch.object(helper, "inventory", return_value={"status":"COMPLETE_PINNED"}), \
                 patch.object(helper, "freeze", side_effect=ResearchBlocked("INVALID_CANDLE_ARCHIVE")):
                with self.assertRaisesRegex(ResearchBlocked, "INVALID_CANDLE_ARCHIVE"):
                    helper.perform(source, dest)
            self.assertFalse((dest / "historical-price-only-report.json").exists())


if __name__ == "__main__":
    unittest.main()
