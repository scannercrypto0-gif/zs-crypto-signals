"""P0 PR72 bounded collector and unapproved clock gate regression tests.

Synthetic-only tests; no live network or privilege mutation. Windows acceptance
also requires a matching local report from the owner machine.
"""
import unittest
from pathlib import Path
from unittest.mock import patch

from zs_smart_gate.ops_windows_time import CANDIDATE, POLICY_ID, SOURCE, assess
from zs_smart_gate.stage05_contracts import canonical, digest

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "scripts" / "p0-windows-time-admin-evidence.ps1"


def receipts():
    names = ("service", "status", "source", "configuration", "stripchart")
    rows = {name: {"exit": 0, "stdout": "", "wall_step_disagreement_s": 0.0}
            for name in names}
    rows["service"]["stdout"] = "STATE : 4 RUNNING"
    rows["status"]["stdout"] = (
        "Leap Indicator: 0(no warning)\nStratum: 4\n"
        "Source: time.cloudflare.com,0x8\n"
        "Root Delay: 0.090s\nRoot Dispersion: 0.020s\n")
    rows["source"]["stdout"] = "time.cloudflare.com,0x8"
    rows["stripchart"]["stdout"] = "\n".join(
        f"12:00:0{i}, d:+00.020s o:+00.001s" for i in range(4))
    return rows


class P0ClockPR72Tests(unittest.TestCase):
    def test_elevated_collector_absolute_fixed_binary_allowlist(self):
        text = COLLECTOR.read_text(encoding="utf-8")
        for needle in ("Join-Path $system32 'sc.exe'",
                       "Join-Path $system32 'w32tm.exe'",
                       "ADMINISTRATOR_REQUIRED", "OWNED_ROOT_REQUIRED",
                       "DISABLED_MARKER_REQUIRED", "SHADOW_LOCK_PRESENT",
                       "UNTRUSTED_DIRECTORY_OR_REPARSE_POINT"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertNotIn("Invoke-Expression", text)
        self.assertNotIn("Register-ScheduledTask", text)
        self.assertNotIn("w32tm /resync", text)
        # Real Windows acceptance separately tests this exact process exit.
        self.assertIn("[Console]::Error.WriteLine('ADMINISTRATOR_REQUIRED')", text)
        self.assertIn("[Environment]::Exit(73)", text)
        acceptance = (ROOT / "scripts" / "p0-pr72-windows-acceptance.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("NONADMIN_COLLECTOR_DENIAL_EXIT_NOT_PROVEN", acceptance)
        self.assertIn("NONADMIN_COLLECTOR_DENIAL_MARKER_NOT_PROVEN", acceptance)

    def test_bounded_child_failure_and_preserved_raw_hashes(self):
        text = COLLECTOR.read_text(encoding="utf-8")
        for needle in ("WaitForExit($TimeoutSeconds * 1000)", ".Kill()",
                       "WaitForExit(2000)", "timed_out", "elapsed_ms",
                       "stdout_sha256", "stderr_sha256",
                       "DIAGNOSTIC_FAILED_CLOSED", "timeout_seconds",
                       "UTF8Encoding]::new($false)"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_diagnostics_never_self_approve_policy_or_runtime(self):
        text = COLLECTOR.read_text(encoding="utf-8")
        self.assertIn("operational_policy_approved = $false", text)
        self.assertIn("runtime_witness_authorized = $false", text)
        self.assertIn("shadow_rerun = $false", text)
        self.assertIsNone(__import__(
            "zs_smart_gate.ops_windows_time", fromlist=["REVIEWED_POLICY_SHA256"]
        ).REVIEWED_POLICY_SHA256)

    def test_pending_review_is_blocked_despite_clean_measurements(self):
        result = assess(receipts(), sync_age_s=10)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("OPERATIONAL_TOLERANCES_NOT_APPROVED", result["blockers"])

    def test_nonadmin_source_and_configuration_denials(self):
        # Real Windows proof showed w32tm access denial on stdout with EXIT=0.
        # Both EXIT=0 and EXIT=5 must fail closed when the body says denied.
        for code in (0, 5):
            with self.subTest(exit=code):
                rows = receipts()
                for name in ("source", "configuration"):
                    rows[name]["exit"] = code
                    rows[name]["stdout"] = (
                        "The following error occurred: Access is denied. (0x80070005)"
                    )
                result = assess(rows, sync_age_s=10)
                self.assertIn("SOURCE_COMMAND_FAILED", result["blockers"])
                self.assertIn("CONFIGURATION_COMMAND_FAILED", result["blockers"])

    def test_changed_source_denied(self):
        rows = receipts()
        rows["status"]["stdout"] = rows["status"]["stdout"].replace(
            SOURCE, "Local CMOS Clock")
        self.assertIn("SOURCE_NOT_ALLOWLISTED", assess(
            rows, sync_age_s=10)["blockers"])

    def test_stale_missing_and_future_sync_denied(self):
        for age in (None, -1, 601, float("nan")):
            with self.subTest(age=age):
                self.assertIn("SYNC_FRESHNESS_UNVERIFIED_OR_STALE", assess(
                    receipts(), sync_age_s=age)["blockers"])

    def test_clock_step_denied(self):
        rows = receipts()
        rows["source"]["wall_step_disagreement_s"] = .2
        self.assertIn("SOURCE_TIME_STEP", assess(rows, sync_age_s=10)["blockers"])

    def test_offset_limit_denied(self):
        rows = receipts()
        rows["stripchart"]["stdout"] = rows["stripchart"]["stdout"].replace(
            "o:+00.001s", "o:+00.600s")
        self.assertIn("OFFSET_LIMIT", assess(rows, sync_age_s=10)["blockers"])

    def test_dispersion_limit_denied(self):
        rows = receipts()
        rows["status"]["stdout"] = rows["status"]["stdout"].replace(
            "Root Dispersion: 0.020s", "Root Dispersion: 0.900s")
        self.assertIn("CONDITIONAL_UNCERTAINTY_UNVERIFIED_OR_HIGH", assess(
            rows, sync_age_s=10)["blockers"])

    def test_duplicate_and_insufficient_quorum_denied(self):
        for count in (1, 3):
            rows = receipts()
            rows["stripchart"]["stdout"] = "\n".join(
                ["12:00:00, d:+00.020s o:+00.001s"] * count)
            self.assertIn("OFFSET_QUORUM_OR_DUPLICATE", assess(
                rows, sync_age_s=10)["blockers"])

    def test_policy_hash_replay_or_change_does_not_authorize(self):
        expected = {"policy_id": POLICY_ID, "source": SOURCE, "limits": CANDIDATE}
        with patch("zs_smart_gate.ops_windows_time.REVIEWED_POLICY_SHA256",
                   digest(canonical(expected))):
            self.assertEqual(assess(receipts(), sync_age_s=10)["status"], "BLOCKED")
            mutated = {**expected, "source": "elsewhere.example"}
            self.assertEqual(assess(receipts(), sync_age_s=10,
                                    policy=mutated)["status"], "BLOCKED")
            self.assertEqual(assess(receipts(), sync_age_s=10,
                                    policy=expected)["status"],
                             "OPERATIONAL_TIME_ACCEPTED")  # Synthetic gated logic only


if __name__ == "__main__":
    unittest.main()
