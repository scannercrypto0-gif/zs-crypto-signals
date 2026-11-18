"""ORDER007 synthetic/offline tests; owner Windows is sole test authority."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from zs_smart_gate.marketwide_cursor import PauseScan
from zs_smart_gate.order007_original_source import (
    bounded_source, CompleteBoundedCapture, _adopt_runtime_budget,
)
from zs_smart_gate.order007_science import source_intake
from zs_smart_gate.stage05_contracts import canonical, digest

ROOT = Path(__file__).resolve().parents[1]


class NoNetwork:
    attempts = weight = used = bytes = 0
    receipts = []

    def get(self, path, params):
        raise PauseScan("SYNTHETIC_QUOTA_BLOCK")


class Order007ReleaseTests(unittest.TestCase):
    def test_explicit_d_only_powershell_paths(self):
        code = (ROOT/"scripts"/"order007-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("D:\\ZS-SMART-GATE", code)
        self.assertIn("Assert-Checkout", code)
        self.assertIn("DISABLED", code)
        self.assertNotIn("Register-ScheduledTask", code)
        self.assertNotIn("Enable-ScheduledTask", code)
        self.assertIn("--live-read-only", code)

    def test_acceptance_uses_local_python_and_raw_hashes(self):
        code = (ROOT/"scripts"/"order007-windows-acceptance.ps1").read_text(
            encoding="utf-8")
        self.assertIn("unittest", code)
        self.assertIn("SHA256", code)
        self.assertIn("tested_head", code)
        self.assertIn("restore_verified", code)
        self.assertIn("3.12", (ROOT/"scripts"/"order007-windows.ps1").read_text(
            encoding="utf-8"))

    def test_no_automatic_scheduled_or_external_execution(self):
        for name in ("order007-windows.ps1", "order007-windows-acceptance.ps1"):
            txt = (ROOT/"scripts"/name).read_text(encoding="utf-8")
            self.assertNotIn("Send-Telegram", txt)
            self.assertNotIn("Start-ScheduledTask", txt)
            self.assertNotIn("SQLINSERT", txt)
        txt = (ROOT/"scripts"/"order007-shadow.py").read_text(encoding="utf-8")
        self.assertIn("run_tree(argv,timeout=120)", txt)
        self.assertIn("STOP_REQUESTED", txt)

    def test_source_capture_rejects_non_usdt_and_duplicate(self):
        with TemporaryDirectory() as d:
            for values in (("BTCUSDT","BTCUSDT"), ("BTCBUSD",),
                           ("BTCUSDT","ETHUSDT","SOLUSDT"), tuple(),
                           ("BtcUSDT",)):
                with self.subTest(symbols=values):
                    with self.assertRaises(ValueError):
                        bounded_source(Path(d), values, transport=NoNetwork(),
                                       check_clock=False)

    def test_source_capture_quota_stop_is_honest_and_local(self):
        with TemporaryDirectory() as d:
            row = bounded_source(Path(d), ("BTCUSDT",),
                                 transport=NoNetwork(),check_clock=False)
            self.assertEqual(row["status"],"PARTIAL")
            self.assertEqual(row["stop"], "BOUNDED_SOURCE_STOP:SYNTHETIC_QUOTA_BLOCK")
            self.assertEqual(row["accepted_5m_event_windows"], 0)
            self.assertEqual(row["qualified_signal_ids"], [])
            path=Path(d)/"sanitized-source-manifest.json"
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text())["scientific_state"],
                             "SCIENCE_NOT_APPROVED")

    def test_source_intake_empty_is_not_scientific_validation(self):
        with TemporaryDirectory() as d:
            row = source_intake(Path(d))
            self.assertEqual(row["status"],"SCIENCE_NOT_APPROVED")
            self.assertEqual(row["event_count"],0)
            self.assertEqual(row["up_real_science_decision"],"NOT_QUALIFIED")
            self.assertEqual(row["down_real_science_decision"],"NOT_QUALIFIED")
            self.assertIsNone(row["n_required"])
            self.assertEqual(row["oos"],"NOT_OPENED_NO_PREREGISTRATION")

    def _fixture(self, root, *, corrupt=False, name="original-a"):
        folder=Path(root)/name
        folder.mkdir()
        packet={
            "symbol":"BTCUSDT", "boundary_ms":1770000000000,
            "source_scope":"PUBLIC_SPOT_CONDITIONAL_RESEARCH",
            "source_manifest_sha256":"a"*64, "decision_at":"2026-02-02T00:00:00Z",
            "frames":{}, "market":{}
        }
        files={}
        receipts=[]
        for i, frame in enumerate(("5m","30m","1h","4h"),1):
            name=f"response-{i}.private"
            rows=[]  # deliberately incomplete, valid JSON synthetic fixture
            data=canonical(rows)
            (folder/name).write_bytes(data)
            checksum=digest(data)
            files[frame]={"file":name,"sha256":checksum}
            receipts.append({"file":name,"sha256":checksum})
            packet["frames"][frame]={"rows":rows,
                "payload_sha256":digest(canonical(rows))}
        private=folder/"BTCUSDT-source.private.json"
        private.write_bytes(canonical(packet))
        sha=digest(private.read_bytes())
        manifest={
            "schema":"zs.order007.original-public-spot-source.v1",
            "raw_body_receipts":receipts,
            "coverage":[{
                "symbol":"BTCUSDT", "packet_sha256":("b"*64 if corrupt else sha),
                "private_packet_sha256":sha,
                "private_body_files":files,
                "input_payload_sha256":{k:v["sha256"] for k,v in files.items()},
            }],
        }
        (folder/"sanitized-source-manifest.json").write_bytes(canonical(manifest))
        return folder

    def test_science_intake_detects_invalid_input_hash(self):
        with TemporaryDirectory() as d:
            self._fixture(d,corrupt=True)
            report=source_intake(Path(d))
            self.assertEqual(report["event_count"],0)
            self.assertEqual(len(report["rejected_manifests"]),1)
            self.assertEqual(report["signals_created"],0)

    def test_science_intake_records_invalid_frames_without_promotion(self):
        with TemporaryDirectory() as d:
            self._fixture(d)
            report=source_intake(Path(d))
            self.assertEqual(report["event_count"],1)
            self.assertEqual(report["symbol_count"],1)
            self.assertEqual(report["candidate_counts_by_direction"]["UP"]["DATA_INVALID"],1)
            self.assertEqual(report["candidate_counts_by_direction"]["DOWN"]["DATA_INVALID"],1)
            self.assertEqual(report["signals_created"],0)
            self.assertEqual(report["precision"],None)

    def test_science_intake_deduplicates_same_original_packet(self):
        with TemporaryDirectory() as d:
            self._fixture(d,name="original-a")
            self._fixture(d,name="original-b")
            report=source_intake(Path(d))
            self.assertEqual(report["event_count"],1)
            self.assertFalse(report["rejected_manifests"])

    def test_science_output_does_not_expose_raw_packet(self):
        with TemporaryDirectory() as d:
            self._fixture(d)
            result=source_intake(Path(d))
            raw=json.dumps(result,sort_keys=True)
            self.assertNotIn('"frames": {}',raw)
            self.assertNotIn("API_KEY",raw)
            self.assertEqual(result["qualification_registry_modified"],False)

    def test_runtime_exchange_limit_controls_read_only_guard(self):
        with TemporaryDirectory() as d:
            cap=CompleteBoundedCapture(d)
            receipt={"payload":{"rateLimits":[
                {"rateLimitType":"REQUEST_WEIGHT","interval":"MINUTE",
                 "intervalNum":1,"limit":6000}]}}
            r=_adopt_runtime_budget(receipt,cap)
            self.assertEqual(r["internal_headroom_guard"],5500)
            self.assertEqual(cap.runtime_guard,5500)
            r2=_adopt_runtime_budget({"payload":{"rateLimits":[
                {"rateLimitType":"REQUEST_WEIGHT","interval":"MINUTE",
                 "intervalNum":1,"limit":1100}]}},cap)
            self.assertEqual(r2["internal_headroom_guard"],600)
            with self.assertRaises(PauseScan):
                _adopt_runtime_budget({"payload":{}},cap)

    def test_exact_11_requests_no_12th_read_only_get(self):
        with TemporaryDirectory() as d:
            cap=CompleteBoundedCapture(d)
            cap.attempts=11
            self.assertTrue(cap.healthy())
            with self.assertRaises(PauseScan):
                cap.get("klines",{"symbol":"BTCUSDT","interval":"5m",
                                   "endTime":"1","limit":"22"})

    def test_science_rejects_mutated_original_response_bytes(self):
        with TemporaryDirectory() as d:
            folder=self._fixture(d)
            (folder/"response-2.private").write_bytes(b"tampered")
            result=source_intake(Path(d))
            self.assertEqual(result["event_count"],0)
            self.assertEqual(len(result["rejected_manifests"]),1)
            self.assertEqual(result["status"],"SCIENCE_NOT_APPROVED")

    def test_source_intake_rejects_semantic_frame_mutation_even_if_rehashed(self):
        with TemporaryDirectory() as d:
            folder=self._fixture(d)
            packet_path=folder/"BTCUSDT-source.private.json"
            p=json.loads(packet_path.read_bytes())
            p["frames"]["1h"]["rows"]=[["forged-frame"]]
            p["frames"]["1h"]["payload_sha256"]=digest(canonical([["forged-frame"]]))
            packet_path.write_bytes(canonical(p))
            manifest_path=folder/"sanitized-source-manifest.json"
            m=json.loads(manifest_path.read_bytes())
            m["coverage"][0]["packet_sha256"]=digest(canonical(p))
            m["coverage"][0]["private_packet_sha256"]=digest(packet_path.read_bytes())
            manifest_path.write_bytes(canonical(m))
            report=source_intake(Path(d))
            self.assertEqual(report["event_count"],0)
            self.assertEqual(len(report["rejected_manifests"]),1)

    def test_disabled_upgrade_requires_ancestor_pinned_head_and_backups(self):
        script=(ROOT/"scripts"/"order007-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("if ($Action -eq 'Upgrade')",script)
        self.assertIn("merge-base --is-ancestor",script)
        self.assertIn("UPGRADE_REQUIRES_DISABLED_NO_WORKER",script)
        self.assertIn("UPGRADE_TARGET_HEAD_TREE_MISMATCH",script)
        self.assertIn("BACKUP_SHA256",script)
        self.assertIn("UPGRADE_DISABLED HEAD=",script)
        self.assertNotIn("Enable-ScheduledTask",script)

    def test_windows_restore_quiet_checkout_and_durable_failure_receipt(self):
        manager=(ROOT/"scripts"/"order007-windows.ps1").read_text(encoding="utf-8")
        acceptance=(ROOT/"scripts"/"order007-windows-acceptance.ps1").read_text(
            encoding="utf-8")
        self.assertIn("checkout --quiet --detach $pin.head",manager)
        self.assertIn("restore_error=$restoreError",acceptance)
        self.assertIn("fsck_error=$fsckError",acceptance)
        self.assertIn("$restored=$false",acceptance)
        self.assertIn("Get-FileHash -LiteralPath $stderr",acceptance)
