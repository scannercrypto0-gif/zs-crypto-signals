"""ORDER025 GitHub-only private source custody: synthetic test bytes ONLY.

Never call GitHub CLI or a market endpoint. Real source upload remains an
explicit owner action after private-repo and source-SHA checks; no fake private PASS.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from zs_smart_gate.stage03_order022 import (
    MONTHS, SYMBOLS, ResearchBlocked, canonical, filename, freeze, run,
)
from test_stage03_order022 import all_fixture_archives

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "order025-github-custody.py"
spec = importlib.util.spec_from_file_location("order025_custody", SCRIPT)
custody = importlib.util.module_from_spec(spec)
spec.loader.exec_module(custody)


def setup_synthetic_copy(root):
    root = Path(root)
    original = root / "old-evidence"
    private = root / "original-replay"
    batch = original / "monthly"
    batch.mkdir(parents=True)
    private.mkdir()
    staged = private / "verified_5m_archives"
    cat = all_fixture_archives(staged)
    src_items = []
    for f in cat["files"]:
        copy = batch / f["name"]
        shutil.copyfile(staged / f["name"], copy)
        src_items.append({
            "name": f["name"], "symbol": f["symbol"], "interval": "5m",
            "sha256": f["sha256"],
        })
        f["source"] = "BINANCE_VISION_SPOT_PUBLIC_ARCHIVE"
    cat["source_kind"] = "REAL_ARCHIVE_PRIVATE"
    old_manifest = original / "manifest.json"
    old_index = original / "dataset-index.json"
    old_manifest.write_bytes(canonical({"files": src_items}))
    old_index.write_bytes(b'{"fixture":"SYNTHETIC_TEST_ONLY"}\n')
    catalog = private / "local-010b-catalog.json"
    catalog.write_bytes(canonical(cat))
    freeze(staged, catalog, private / "frozen-experiment.json")
    result = run(private / "frozen-experiment.json", staged,
                 private / "research-results.sqlite", private / "verified-restore.sqlite")
    report = private / "historical-price-only-report.json"
    report.write_bytes(canonical(result) + b"\n")
    frozen_sha = hashlib.sha256((private/"frozen-experiment.json").read_bytes()).hexdigest()
    report_sha = hashlib.sha256(report.read_bytes()).hexdigest()
    (private/"private-run-receipt.json").write_bytes(canonical({
        "frozen_manifest_sha256": frozen_sha,
        "result_report_sha256": report_sha,
        "status":"SYNTHETIC_TEST_NOT_A_REAL_MARKET_ATTESTATION",
    }) + b"\n")
    pins = {
        "ORIGINAL_MANIFEST_SHA": hashlib.sha256(old_manifest.read_bytes()).hexdigest(),
        "ORIGINAL_INDEX_SHA": hashlib.sha256(old_index.read_bytes()).hexdigest(),
        "REPORT_SHA": report_sha,
    }
    return original, private, pins


class PrivateGitHubCustodyTests(unittest.TestCase):
    def fake_pins(self,pins):
        st = ExitStack()
        for name,value in pins.items():
            st.enter_context(patch.object(custody,name,value))
        return st

    def test_twelve_original_bytes_and_report_were_pinned_before_upload(self):
        with tempfile.TemporaryDirectory() as d:
            original,private,pins=setup_synthetic_copy(d)
            with self.fake_pins(pins), patch("socket.socket",side_effect=AssertionError("NO_NETWORK")):
                assets,doc=custody.locally_pinned_inputs(original,private)
            self.assertEqual(sum(name.endswith(".zip") for name in assets),12)
            self.assertEqual(len(assets),20)  # 12 ZIPs, 2 old pins, 5 required + 1 optional catalog
            self.assertEqual(doc["asset_hashes"]["manifest.json"]["sha256"],
                             pins["ORIGINAL_MANIFEST_SHA"])
            self.assertEqual(doc["asset_hashes"]["dataset-index.json"]["sha256"],
                             pins["ORIGINAL_INDEX_SHA"])
            self.assertNotIn(str(original.resolve()),str(doc))
            self.assertNotIn(str(private.resolve()),str(doc))

    def test_remote_verification_matches_original_bytes_and_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            original,private,pins=setup_synthetic_copy(d)
            remote=Path(d)/"downloaded"
            remote.mkdir()
            with self.fake_pins(pins):
                assets,doc=custody.locally_pinned_inputs(original,private)
                for name,p in assets.items():
                    shutil.copyfile(p,remote/name)
                (remote/"asset-index.json").write_bytes(canonical(doc)+b"\n")
                receipt=custody.verify_download(remote)
                self.assertEqual(receipt["status"],"GITHUB_TRANSFER_HASHES_VERIFIED")
                self.assertEqual(receipt["zip_count"],12)
                with self.assertRaisesRegex(ResearchBlocked,"TRANSFER_RECEIPT_REQUIRED"):
                    custody.verify_download(remote,require_transfer_receipt=True)
                (remote/"transfer-verification.json").write_bytes(canonical(receipt)+b"\n")
                self.assertEqual(custody.verify_download(remote,require_transfer_receipt=True)["assets"],20)
                self.assertEqual(custody.verify_download(remote)["assets"],20)
                (remote/filename("BTCUSDT","2025-01")).write_bytes(b"TAMPER")
                with self.assertRaisesRegex(ResearchBlocked,"SIZE_MISMATCH"):
                    custody.verify_download(remote)

    def test_remote_asset_list_extra_file_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            original,private,pins=setup_synthetic_copy(d)
            remote=Path(d)/"downloaded"
            remote.mkdir()
            with self.fake_pins(pins):
                assets,doc=custody.locally_pinned_inputs(original,private)
                for name,p in assets.items():
                    shutil.copyfile(p,remote/name)
                (remote/"asset-index.json").write_bytes(canonical(doc)+b"\n")
                (remote/"unregistered.zip").write_bytes(b"malicious")
                with self.assertRaisesRegex(ResearchBlocked,"SET_UNEXPECTED"):
                    custody.verify_download(remote)

    def test_invalid_missing_index_refuses_preflight(self):
        with tempfile.TemporaryDirectory() as d:
            original,private,pins=setup_synthetic_copy(d)
            (original/"dataset-index.json").unlink()
            with self.fake_pins(pins):
                with self.assertRaisesRegex(ResearchBlocked,"PREVIOUS_PIN_NOT_FOUND"):
                    custody.locally_pinned_inputs(original,private)

    def test_modified_original_zip_refuses_source_attestation(self):
        with tempfile.TemporaryDirectory() as d:
            original,private,pins=setup_synthetic_copy(d)
            (original/"monthly"/filename("ETHUSDT","2025-02")).write_bytes(b"INVALID")
            with self.fake_pins(pins):
                with self.assertRaisesRegex(ResearchBlocked,"PREVIOUS_PIN_NOT_FOUND"):
                    custody.locally_pinned_inputs(original,private)

    def test_report_tamper_rejects_before_upload(self):
        with tempfile.TemporaryDirectory() as d:
            original,private,pins=setup_synthetic_copy(d)
            with (private/"historical-price-only-report.json").open("ab") as f:
                f.write(b"tampered")
            with self.fake_pins(pins):
                with self.assertRaisesRegex(ResearchBlocked,"REPORT_SHA_MISMATCH"):
                    custody.locally_pinned_inputs(original,private)

    def test_upload_rejects_bad_source_pins_before_github(self):
        with patch.object(custody,"locally_pinned_inputs",
                          side_effect=ResearchBlocked("SOURCE_PIN_INVALID")), \
             patch.object(custody,"gh",side_effect=AssertionError("NO_GITHUB_REQUEST")):
            with self.assertRaisesRegex(ResearchBlocked,"SOURCE_PIN_INVALID"):
                custody.upload("not-existing","not-existing")

    def test_upload_requires_private_repo_before_release(self):
        with patch.object(custody,"locally_pinned_inputs",return_value=({},{})), \
             patch.object(custody,"assert_remote_private",
                          side_effect=ResearchBlocked("REMOTE_REPOSITORY_NOT_PRIVATE")), \
             patch.object(custody,"gh",side_effect=AssertionError("NO_RELEASE_CREATION")):
            with self.assertRaisesRegex(ResearchBlocked,"NOT_PRIVATE"):
                custody.upload("fixture-original","fixture-run")

    def test_upload_cli_has_no_rights_ack(self):
        with patch.object(custody,"upload") as upload:
            self.assertEqual(custody.main(["upload","--original-root","a",
                                          "--private-run-dir","b"]),0)
            upload.assert_called_once_with("a","b")

    def test_public_or_unknown_git_visibility_fail_closed(self):
        class Resp:
            def __init__(self,val):self.stdout=val
        with patch.object(custody,"gh",return_value=Resp("PUBLIC\n")):
            with self.assertRaisesRegex(ResearchBlocked,"NOT_PRIVATE"):
                custody.assert_remote_private()
        with patch.object(custody,"gh",return_value=Resp("PRIVATE\n")):
            custody.assert_remote_private()


if __name__=="__main__":
    unittest.main()
