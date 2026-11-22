"""Windows boot observation bounded failures, no clock or network collection."""
import importlib.util,json,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
from zs_smart_gate.ops24_budget import Hold
spec=importlib.util.spec_from_file_location("ops24_boot_worker",Path(__file__).resolve().parents[1]/"scripts/ops24-worker.py")
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
class BootTests(unittest.TestCase):
    def test_slow_boot_observation_has_bounded_budget(self):
        with patch.object(worker.subprocess,"check_output",return_value=json.dumps({"boot_utc":"actual-test-boot","session":0})) as call,patch.object(worker,"is_admin",return_value=False):
            result=worker.windows_observation()
        self.assertEqual(call.call_args.kwargs["timeout"],60)
        self.assertTrue(result["normal_token"])
        self.assertEqual(result["session"],0)
    def test_timeout_is_explicit_hold(self):
        with patch.object(worker.subprocess,"check_output",side_effect=subprocess.TimeoutExpired("redacted",60)):
            with self.assertRaisesRegex(Hold,"WINDOWS_BOOT_OBSERVATION_TIMEOUT_60S"):
                worker.windows_observation()
    def test_command_failure_is_explicit_hold(self):
        with patch.object(worker.subprocess,"check_output",side_effect=subprocess.CalledProcessError(1,"redacted")):
            with self.assertRaisesRegex(Hold,"WINDOWS_BOOT_OBSERVATION_COMMAND_FAILED"):
                worker.windows_observation()
