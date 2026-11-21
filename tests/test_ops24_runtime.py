"""OPS24 operational witness and normal-worker control failure tests."""
from contextlib import closing
import copy
import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from zs_smart_gate import ops_windows_time as clock
from zs_smart_gate.ops24_budget import Hold
from zs_smart_gate.ops24_runtime import RuntimeJournal, supervisor
from test_p0_clock_73 import valid_receipts

ROOT=Path(__file__).resolve().parents[1]


class Ops24SupervisorTests(unittest.TestCase):
    def test_disabled_or_missing_activation_never_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            journal=RuntimeJournal(root)
            window=journal.plan(1800,"head")
            def forbidden(*args):
                self.fail("network cycle was invoked")
            with patch("zs_smart_gate.marketwide_capture._is_admin",return_value=False):
                with self.assertRaises(Hold):
                    supervisor(root,window,activation=lambda:False,run_cycle=forbidden,clock=lambda:True)
                (root/"DISABLED").write_text("disabled")
                with self.assertRaises(Hold):
                    supervisor(root,window,activation=lambda:True,run_cycle=forbidden,clock=lambda:True)

    def test_elevated_worker_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder,patch("zs_smart_gate.marketwide_capture._is_admin",return_value=True):
            with self.assertRaisesRegex(Hold,"NORMAL_USER_TOKEN"):
                supervisor(folder,"unused",activation=lambda:True,run_cycle=lambda _:None,clock=lambda:True)

    def test_stop_and_singleton_hold_and_restart_slots(self):
        from zs_smart_gate.windows_runner import process_lock
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            journal=RuntimeJournal(root)
            window=journal.plan(1800,"head")
            with patch("zs_smart_gate.marketwide_capture._is_admin",return_value=False):
                with process_lock(root/"lock") as owned:
                    self.assertTrue(owned)
                    with self.assertRaisesRegex(Hold,"SINGLETON"):
                        supervisor(root,window,activation=lambda:True,run_cycle=lambda _:None,
                                   clock=lambda:True,wall=lambda:1800)
                (root/"STOP_REQUESTED").write_text("stop")
                result=supervisor(root,window,activation=lambda:True,run_cycle=lambda _:self.fail("cycle"),
                                  clock=lambda:True,wall=lambda:1800)
                self.assertEqual(result["stability"],"24H_STABILITY_NOT_PROVEN")
                self.assertTrue((root/"stopped.json").exists())

    def test_one_mock_cycle_has_health_and_boundary_without_24h_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            journal=RuntimeJournal(root)
            window=journal.plan(1800,"head")
            current=[1800]
            def sleep(_):
                (root/"STOP_REQUESTED").write_text("test stop")
                current[0]+=1
            with patch("zs_smart_gate.marketwide_capture._is_admin",return_value=False), \
                 patch("zs_smart_gate.ops24_runtime.resources",return_value=dict(cpu_seconds=1)):
                result=supervisor(root,window,activation=lambda:True,
                    run_cycle=lambda _:dict(coverage="MARKET_COVERAGE_VERIFIED",eligible=45,validated=45),
                    clock=lambda:True,wall=lambda:current[0],sleep=sleep)
            self.assertEqual(sum(row["state"]=="PASS" for row in result["slots"]),2)
            self.assertEqual(result["stability"],"24H_STABILITY_NOT_PROVEN")

    def test_unreviewed_activation_cannot_be_replaced_by_bare_flags(self):
        module=runpy.run_path(str(ROOT/"scripts"/"ops24-worker.py"))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"release.json").write_text(json.dumps(dict(head="a"*40,tree="b"*40)))
            (root/"activation.json").write_text(json.dumps(dict(enabled=True)))
            with self.assertRaisesRegex(Hold,"ACTIVATION_SCOPE_INVALID"):
                module["activation"](root,"a"*40,"b"*40)

    def test_elapsed_wall_time_does_not_replace_observed_process_uptime(self):
        with tempfile.TemporaryDirectory() as folder:
            journal=RuntimeJournal(folder)
            window=journal.plan(1800,"head")
            report=journal.report(window,1800)
            for row in report["slots"]:
                journal.reserve(window,row["kind"],row["at"])
                journal.finish(window,row["kind"],row["at"],"PASS",{})
            # No actual session ran for 24h; completed fixture slots alone fail.
            report=journal.report(window,1800+86400)
            self.assertEqual(report["observed_uptime_lower_bound_seconds"],0)
            self.assertEqual(report["stability"],"24H_STABILITY_NOT_PROVEN")
