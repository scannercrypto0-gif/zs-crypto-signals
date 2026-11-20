"""P0 owner-approved bounded admin pilot; no live I/O or Windows changes."""
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from zs_smart_gate import ops_windows_time as clock
from zs_smart_gate.marketwide_capture import run
from zs_smart_gate.stage05_contracts import canonical, digest

ROOT = Path(__file__).resolve().parents[1]


def valid_receipts():
    data = {name: {"exit": 0, "stdout": "", "stderr": "",
                   "wall_step_disagreement_s": 0} for name in clock.COMMANDS}
    data["service"]["stdout"] = "STATE : 4 RUNNING"
    data["status"]["stdout"] = (
        "Leap Indicator: 0(no warning)\nStratum: 4\n"
        "Source: time.cloudflare.com,0x8\n"
        "Root Delay: 0.090s\nRoot Dispersion: 0.020s")
    data["source"]["stdout"] = "time.cloudflare.com,0x8"
    data["stripchart"]["stdout"] = "\n".join(
        f"12:00:0{i}, d:+00.020s o:+00.001s" for i in range(4))
    return data


class Clock73Tests(unittest.TestCase):
    def test_owner_policy_digest_exact_and_no_implicit_activation(self):
        policy = {"policy_id": clock.POLICY_ID, "source": clock.SOURCE,
                  "limits": clock.CANDIDATE}
        self.assertEqual(digest(canonical(policy)), clock.REVIEWED_POLICY_SHA256)
        self.assertEqual(clock.assess(valid_receipts(), sync_age_s=10)["status"], "BLOCKED")
        self.assertEqual(clock.assess(valid_receipts(), sync_age_s=10, policy=policy)["status"],
                         "OPERATIONAL_TIME_ACCEPTED")  # synthetic only

    def test_nonfinite_offset_must_fail_closed(self):
        policy = {"policy_id": clock.POLICY_ID, "source": clock.SOURCE,
                  "limits": clock.CANDIDATE}
        rows = valid_receipts()
        rows["stripchart"]["stdout"] = rows["stripchart"]["stdout"].replace(
            "o:+00.001s", "o:+nan")
        self.assertEqual(clock.assess(rows, sync_age_s=10, policy=policy)["status"],
                         "BLOCKED")

    def test_admin_pilot_denied_without_windows_elevation(self):
        with TemporaryDirectory() as tmp:
            with patch("zs_smart_gate.marketwide_capture._is_admin", return_value=False):
                with self.assertRaises(PermissionError):
                    run(Path(tmp), Path(tmp) / "cursor.sqlite", admin_clock_pilot=True)

    def test_no_unreviewed_service_or_effects_added(self):
        script = (ROOT / "scripts" / "order007-windows.ps1").read_text(encoding="utf-8")
        child = (ROOT / "scripts" / "order007-shadow.py").read_text(encoding="utf-8")
        self.assertIn("CLOCK_PILOT_ADMIN_CONTEXT_REQUIRED", script)
        self.assertIn("--admin-clock-pilot", script)
        self.assertIn("--admin-clock-pilot", child)
        self.assertIn("run_tree(argv,timeout=120)", child)
        self.assertNotIn("Register-ScheduledTask", script)
        self.assertNotIn("Send-MailMessage", script)

    def test_operator_preflight_and_summary_are_read_only(self):
        script = (ROOT / "scripts" / "order007-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("CANDLE_ENTRY_PREFLIGHT_BLOCKED_NO_PUBLIC_GETS", script)
        self.assertIn("CANDLE_ENTRY_WINDOW_EXPIRED_BEFORE_LAUNCH", script)
        self.assertIn("CANDLE_ENTRY_PREFLIGHT BOUNDARY_MS=", script)
        self.assertIn("SHADOW_STOP_REASON=", script)
        self.assertIn("MARKET_ELIGIBLE=", script)
        self.assertIn("PUBLIC_GETS=", script)
        self.assertNotIn("Register-ScheduledTask", script)

    def test_policy_change_fails_closed(self):
        policy = {"policy_id": clock.POLICY_ID, "source": clock.SOURCE,
                  "limits": {**clock.CANDIDATE, "max_offset_s": 1.5}}
        self.assertEqual(clock.assess(valid_receipts(), sync_age_s=10, policy=policy)["status"],
                         "BLOCKED")


if __name__ == "__main__":
    unittest.main()
