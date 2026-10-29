"""Windows GUI→one-time Task Scheduler→accepted 03B1 offline integration.

All source GETs below are deterministic fake transports. Real sockets are
explicitly forbidden in the successful cross-stage test.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
import hashlib,json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import Mock,patch

from zs_smart_gate.stage03b1_live import probe_once
from zs_smart_gate.windows_diagnostic import (
    INTENT,CLAIM,EVIDENCE,STATUS,BUDGET,authorize,execute,status,pinned,
)
from test_stage03b1 import FixtureTransport,NOW_MS,Horizon

UTC=timezone.utc
NOW=datetime(2026,10,29,7,0,0,tzinfo=UTC)
TOKEN="a"*32
SHA="b"*64
REV="c"*40
CONF={"revision":REV}

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.repo=self.root/"repo"
        self.runtime=self.root/"runtime"
        self.logs=self.root/"logs"
        for path in (self.repo,self.runtime,self.logs):path.mkdir()
        self.config=self.runtime/"deployment.json"
        self.pythonw=self.root/"pythonw.exe"
        self.pythonw.touch()
        self.executor=Mock()
        self.guard=patch("zs_smart_gate.windows_diagnostic.pinned",return_value=CONF)
        self.guard.start()
        self.addCleanup(self.guard.stop)
        self.paths=patch("zs_smart_gate.windows_diagnostic.d_path",side_effect=lambda p:Path(p))
        self.paths.start()
        self.addCleanup(self.paths.stop)

    def args(self):
        return dict(config_path=self.config,config_sha=SHA,repo=self.repo,
                    state=self.runtime,logs=self.logs)
    def arm(self,**kwargs):
        return authorize(**self.args(),pythonw=self.pythonw,executor=self.executor,
                         clock=lambda:NOW,token_factory=lambda:TOKEN,**kwargs)
    def run(self,*,probe,clock=lambda:NOW,token=TOKEN):
        return execute(**self.args(),token=token,probe=probe,clock=clock)

    def test_arm_once_creates_distinct_no_console_scheduler_task_and_consumes(self):
        response=self.arm()
        self.assertEqual(response["status"],"ARMED")
        self.assertEqual(self.executor.call_count,1)
        code=self.executor.call_args.args[0]
        self.assertIn("Register-ScheduledTask",code)
        self.assertIn("New-ScheduledTaskTrigger -Once",code)
        self.assertIn("New-ScheduledTaskAction",code)
        self.assertIn("pythonw.exe",code)
        self.assertIn("windows-diagnostic.pyw",code)
        self.assertIn("MultipleInstances IgnoreNew",code)
        self.assertIn("RunLevel Limited",code)
        self.assertNotIn("Enable-ScheduledTask",code)
        self.assertNotIn("windows-tick.py",code)
        self.assertNotIn("Start-ScheduledTask",code)
        self.assertNotIn("Resume",code)
        self.assertNotIn("stage03b3",code.lower())
        self.assertEqual(self.arm()["status"],"ALREADY_AUTHORIZED_OR_CONSUMED")
        self.executor.assert_called_once()

    def test_unapproved_or_bad_token_never_invokes_probe(self):
        get=Mock(side_effect=AssertionError("UNAUTHORIZED_HTTP"))
        with self.assertRaisesRegex(ValueError,"EXPLICIT_GUI_INTENT"):
            self.run(probe=get)
        self.arm()
        with self.assertRaisesRegex(ValueError,"EXPIRED_OR_MISMATCHED_GUI_INTENT"):
            self.run(probe=get,token="f"*32)
        get.assert_not_called()
        self.assertFalse((self.runtime/CLAIM).exists())

    def test_expired_or_clock_early_intent_never_uses_network(self):
        self.arm()
        for moment in (NOW-timedelta(seconds=1),NOW+timedelta(minutes=5,seconds=1)):
            with self.assertRaisesRegex(ValueError,"EXPIRED_OR_MISMATCHED"):
                self.run(probe=lambda **kw:self.fail("NETWORK"),clock=lambda:moment)
        self.assertFalse((self.runtime/CLAIM).exists())

    def test_real_stage03b1_core_fixture_from_scheduled_bridge_zero_real_sockets(self):
        self.arm()
        fake=FixtureTransport()
        def approved(**kwargs):
            return probe_once(**kwargs,getter=fake,local_ms=lambda:NOW_MS+1000)
        with patch.object(socket,"socket",side_effect=AssertionError("REAL_NETWORK_FORBIDDEN")):
            output=self.run(probe=approved)
        self.assertEqual(output["status"],"PASS",output)
        self.assertEqual(output["reconciliation_status"],"PASS")
        self.assertEqual(output["http_attempts"],6)
        self.assertLessEqual(output["http_attempts"],BUDGET)
        self.assertEqual(output["parent_frame"],"30m")
        self.assertEqual(output["symbol"],"BTCUSDT")
        self.assertIsNone(output["true_clock_uncertainty_ms"])
        self.assertEqual(output["study"],"OFF")
        self.assertEqual(len(output["http"]),6)
        evidence=json.loads((self.logs/EVIDENCE).read_text())
        self.assertEqual(evidence["stage03b1"]["coverage"]["child_candles_fetched"],6)
        self.assertEqual(evidence["stage03b1"]["coverage"]["core_5m_candles"],21)
        self.assertIsNone(evidence["stage03b1"]["signal_id"])
        self.assertIsNone(evidence["stage03b1"]["score"])
        self.assertTrue(evidence["one_time_consumed"])
        self.assertEqual(status(self.logs,SHA)["status"],"PASS")
        self.assertTrue((self.runtime/CLAIM).exists())

    def test_duplicate_scheduler_trigger_cannot_reprobe_or_overwrite_success(self):
        self.arm()
        probe=Mock(return_value={"status":"BLOCKED","signal_id":None,"score":None,
                                 "measurements":{"physical_http_attempts":0}})
        first=self.run(probe=probe)
        self.assertEqual(first["status"],"BLOCKED")
        saved=(self.logs/STATUS).read_bytes()
        with self.assertRaises(FileExistsError):
            self.run(probe=probe)
        self.assertEqual((self.logs/STATUS).read_bytes(),saved)
        self.assertEqual(probe.call_count,1)
        self.assertEqual(self.arm()["status"],"ALREADY_AUTHORIZED_OR_CONSUMED")

    def test_eighth_attempt_stop_is_visible_without_ninth_network_send(self):
        self.arm()
        fake=FixtureTransport()
        class Retrying:
            def __call__(self,path,params=None,*,on_attempt=None):
                for _ in range(3):
                    on_attempt(path)
                    fake.physical+=1
                return fake(path,params,on_attempt=on_attempt)
        def approved(**kwargs):
            return probe_once(**kwargs,getter=Retrying(),
                              local_ms=lambda:NOW_MS+1000)
        output=self.run(probe=approved)
        self.assertEqual(output["status"],"BLOCKED")
        self.assertEqual(output["http_attempts"],8)
        self.assertEqual(fake.physical,8)
        self.assertEqual(output["source_status"],"BLOCKED")
        self.assertEqual(len(json.loads((self.logs/EVIDENCE).read_text())["stage03b1"]
                              ["measurements"]["attempted_paths"]),8)

    def test_provider_failure_preserves_failure_status_and_consumes_permission(self):
        self.arm()
        fake=FixtureTransport()
        fake.fail_path="/api/v3/klines"
        output=self.run(probe=lambda **kw:probe_once(**kw,getter=fake,
                                                     local_ms=lambda:NOW_MS+1000))
        self.assertEqual(output["status"],"BLOCKED")
        self.assertEqual(output["http_attempts"],6)
        self.assertEqual(output["study"],"OFF")
        with self.assertRaises(FileExistsError):
            self.run(probe=lambda **kw:self.fail("RETRY_FORBIDDEN"))

    def test_unexpected_failure_sanitized_and_once_only(self):
        self.arm()
        output=self.run(probe=lambda **kw:(_ for _ in ()).throw(
            RuntimeError("SECRET_DO_NOT_LOG")))
        self.assertEqual(output["status"],"FAIL")
        self.assertEqual(output["error_category"],"RuntimeError")
        self.assertNotIn("SECRET_DO_NOT_LOG",(self.logs/STATUS).read_text())
        self.assertTrue((self.runtime/CLAIM).exists())

    def test_failed_scheduler_registration_consumes_intent_no_autoretry(self):
        self.executor.side_effect=RuntimeError("NO_ADMIN_APPROVAL")
        self.assertEqual(self.arm()["status"],"REGISTRATION_FAILED")
        self.assertEqual(self.arm()["status"],"ALREADY_AUTHORIZED_OR_CONSUMED")
        self.assertEqual(self.executor.call_count,1)
        self.assertEqual(status(self.logs,SHA)["error_category"],
                         "WINDOWS_TASK_REGISTRATION_FAILED")

    def test_pin_mismatch_and_no_d_path_escape_are_gated(self):
        with patch("zs_smart_gate.windows_diagnostic.pinned",
                   side_effect=ValueError("DEPLOYMENT_CHECKSUM_MISMATCH")):
            with self.assertRaisesRegex(ValueError,"DEPLOYMENT_CHECKSUM_MISMATCH"):
                self.arm()
        self.executor.assert_not_called()
        self.assertFalse((self.runtime/INTENT).exists())
        self.arm()
        self.assertEqual(status(self.logs,"0"*64)["status"],"PIN_MISMATCH")

    def test_simulation_and_prospective_entrypoints_remain_closed(self):
        project=Path(__file__).resolve().parents[1]
        simulation=(project/"scripts/windows-tick.py").read_text()
        gui=(project/"scripts/runner-control.pyw").read_text()
        entry=(project/"scripts/windows-diagnostic.pyw").read_text()
        control=(project/"src/zs_smart_gate/windows_control.py").read_text()
        self.assertIn("SIMULATION_NETWORK_FORBIDDEN",simulation)
        self.assertIn("sys.addaudithook(deny_network)",simulation)
        self.assertIn("SIMULATION_ONLY",control)
        self.assertIn("--dry-run --once",control)
        self.assertIn("messagebox.askyesno",gui)
        self.assertIn("diagnostic_start",gui)
        self.assertNotIn("diagnostic_start",simulation)
        self.assertNotIn("stage03b3",entry.lower())
        self.assertNotIn("stage03b3",control.lower())


if __name__=="__main__":
    unittest.main()
