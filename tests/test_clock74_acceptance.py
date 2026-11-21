"""CLOCK74 offline acceptance gaps: final-response guards and compact receipts."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from zs_smart_gate import marketwide_capture as capture
from zs_smart_gate.marketwide_cursor import PauseScan
from zs_smart_gate.ops_windows_watchdog import START
from zs_smart_gate.stage05_contracts import canonical, digest
from test_marketwide_capture import Opener, Response

ROOT = Path(__file__).resolve().parents[1]


class Clock74AcceptanceTests(unittest.TestCase):
    def test_eleventh_response_size_and_total_byte_guards_preserve_original(self):
        for bound, limit, reason in (
                ("MAX_BODY", 1, "UNVERIFIED_RESPONSE_OR_SIZE"),
                ("MAX_TOTAL_BODY", 2, "BODY_BUDGET_EXHAUSTED")):
            with self.subTest(bound=bound), tempfile.TemporaryDirectory() as folder:
                fake = Opener(Response(raw=b"{}"))
                transport = capture.PublicCapture(folder, opener=fake)
                transport.attempts = 10
                with patch.object(capture, bound, limit):
                    with self.assertRaisesRegex(PauseScan, reason):
                        transport.get("klines", {})
                raw = (Path(folder)/"response-11.private").read_bytes()
                self.assertEqual(raw, b"{}")
                rows = [json.loads(line) for line in (Path(folder)/"requests.jsonl").read_bytes().splitlines()]
                self.assertEqual(rows[-1]["body_sha256"], digest(raw))
                self.assertEqual(rows[-1]["attempt"], 11)
                with self.assertRaisesRegex(PauseScan, "REQUEST_BUDGET_EXHAUSTED"):
                    transport.get("klines", {})
                self.assertEqual(fake.calls, 1)

    def test_eleventh_response_deadline_and_observed_weight_still_stop(self):
        for reason in ("CAPTURE_DEADLINE_EXHAUSTED", "OBSERVED_WEIGHT_HEADROOM_EXHAUSTED"):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as folder:
                clock = [0]
                class Fake:
                    calls = 0
                    def open(self, request, timeout):
                        self.calls += 1
                        if reason == "CAPTURE_DEADLINE_EXHAUSTED":
                            clock[0] = capture.MAX_SECONDS
                        return Response(header=str(capture.MAX_USED_WEIGHT)
                                        if reason == "OBSERVED_WEIGHT_HEADROOM_EXHAUSTED" else "120")
                fake = Fake()
                transport = capture.PublicCapture(folder, opener=fake, monotonic=lambda: clock[0])
                transport.attempts = 10
                with self.assertRaisesRegex(PauseScan, reason):
                    transport.get("klines", {})
                self.assertEqual(fake.calls, 1)
                self.assertEqual(len(transport.receipts), 1)
                raw = (Path(folder)/"response-11.private").read_bytes()
                self.assertEqual(transport.receipts[0]["body_sha256"], digest(raw))

    def test_estimated_weight_exact_cap_accepts_response_then_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = Opener(Response())
            transport = capture.PublicCapture(folder, opener=fake)
            transport.weight = capture.MAX_WEIGHT - capture.WEIGHTS["klines"]
            self.assertEqual(transport.get("klines", {})["payload"], {})
            self.assertEqual(transport.weight, capture.MAX_WEIGHT)
            with self.assertRaisesRegex(PauseScan, "ESTIMATED_WEIGHT_BUDGET_EXHAUSTED"):
                transport.get("klines", {})
            self.assertEqual(fake.calls, 1)

    def test_python_compact_output_preserves_large_original_and_no_delivery(self):
        entry = runpy.run_path(str(ROOT/"scripts"/"order007-shadow.py"))["main"]
        with tempfile.TemporaryDirectory(dir="D:/ZS-SMART-GATE/temp") as folder:
            output = Path(folder)
            original = dict(
                status="MARKET_COVERAGE_PARTIAL", stop="REQUEST_BUDGET_EXHAUSTED",
                requests=11, receipt_manifest_sha256="a"*64,
                snapshot={"rows": ["SYNTHETIC_PRIVATE_INVENTORY_MARKER"]*10000},
                funnel=dict(eligible=45, source_validated=2, coverage="MARKET_COVERAGE_PARTIAL"))
            raw = canonical(original)
            (output/"result.json").write_bytes(raw)
            stream = io.StringIO()
            argv = ["order007-shadow.py", "--live-read-only", "--child",
                    "--root", "D:/ZS-SMART-GATE", "--output", str(output)]
            with patch.object(sys, "argv", argv), \
                 patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(START))), \
                 patch.object(capture, "run", return_value=original) as injected, \
                 redirect_stdout(stream):
                code = entry()
            self.assertEqual(code, 2)
            injected.assert_called_once()
            summary = json.loads(stream.getvalue())
            self.assertEqual(summary["requests"], 11)
            self.assertEqual(summary["stop"], "REQUEST_BUDGET_EXHAUSTED")
            self.assertNotIn("SYNTHETIC_PRIVATE_INVENTORY_MARKER", stream.getvalue())
            self.assertLess(len(stream.getvalue()), 2048)
            self.assertEqual((output/"result.json").read_bytes(), raw)

    def test_powershell51_actual_summary_block_and_hash_pointers(self):
        with tempfile.TemporaryDirectory(dir="D:/ZS-SMART-GATE/temp") as folder:
            output = Path(folder)
            result = dict(stop=None, boundary_preflight=None,
                          funnel=dict(stopped_reason="CANDLE_ENTRY_WINDOW_EXPIRED",
                                      eligible=45, attempted=2, coverage_pct=4.4444),
                          requests=11, estimated_weight=120, observed_used_weight=1500,
                          snapshot={"rows": ["SYNTHETIC_PRIVATE_INVENTORY_MARKER"]*10000})
            raw = canonical(result)
            journal = b'{"scope":"SYNTHETIC_TEST_ONLY","attempt":11}\n'
            (output/"result.json").write_bytes(raw)
            (output/"requests.jsonl").write_bytes(journal)
            script = output/"summary-test.ps1"
            script.write_text(r"""param([string]$Repository,[string]$Output)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1){throw 'POWERSHELL_51_REQUIRED'}
$path=Join-Path $Repository 'scripts\order007-windows.ps1'
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'PRODUCTION_SCRIPT_PARSE_ERROR'}
$hashFunction=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Hash-File'},$true)
. ([scriptblock]::Create($hashFunction.Extent.Text))
$source=[IO.File]::ReadAllText($path)
$begin=$source.IndexOf('    # Compact integrity pointer only;')
$end=$source.IndexOf('    if ($code -ne 0) { throw "SHADOW_PARTIAL_OR_STOP_EXIT=$code" }',$begin)
if($begin -lt 0 -or $end -le $begin){throw 'SUMMARY_BLOCK_NOT_FOUND'}
$dest=$Output
. ([scriptblock]::Create($source.Substring($begin,$end-$begin)))
""", encoding="utf-8")
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-File", str(script), "-Repository", str(ROOT), "-Output", str(output)],
                capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode(errors="replace"))
            text = proc.stdout.decode(errors="replace")
            self.assertIn("RESULT_SHA256="+digest(raw), text)
            self.assertIn("JOURNAL_SHA256="+digest(journal), text)
            self.assertIn("SHADOW_STOP_REASON=CANDLE_ENTRY_WINDOW_EXPIRED", text)
            self.assertNotIn("SYNTHETIC_PRIVATE_INVENTORY_MARKER", text)
            self.assertLess(len(proc.stdout), 2048)
            self.assertEqual((output/"result.json").read_bytes(), raw)
            self.assertEqual((output/"requests.jsonl").read_bytes(), journal)
