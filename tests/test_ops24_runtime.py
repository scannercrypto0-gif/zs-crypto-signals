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
            (root/"standing-authority.json").write_text(json.dumps(dict(enabled=True)))
            with self.assertRaisesRegex(Hold,"STANDING_RELEASE_SCOPE_OR_PIN_INVALID"):
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

    def test_entrypoints_resolve_checkout_without_caller_pythonpath(self):
        import sys
        for name in ("ops24-worker.py","ops24-bounded.py","ops24-science-replay.py","ops24-standing-release.py","ops24-release-verify.py"):
            process=subprocess.run([sys.executable,"-E","-B",str(ROOT/"scripts"/name),"--help"],
                capture_output=True,text=True,timeout=15)
            with self.subTest(script=name):
                self.assertEqual(process.returncode,0,process.stderr)
                self.assertIn("usage:",process.stdout)

    def test_standing_release_from_another_head_is_refused_before_network(self):
        from zs_smart_gate.ops24_authority import verify_cached
        with self.assertRaisesRegex(Hold,'STANDING_RELEASE_SCOPE_OR_PIN_INVALID'):
            verify_cached(dict(schema='zs.ops24.standing-authority.v2',head='old',tree='old'),
                          head='new',tree='new')

    def test_timed_breaker_resumes_but_stop_and_unknown_ban_do_not(self):
        with tempfile.TemporaryDirectory() as root:
            journal=RuntimeJournal(root)
            for _ in range(3):last=journal.breaker(now=10,success=False)
            journal.resume_after_backoff(last['retry_at']-1)
            with closing(journal.open()) as db:self.assertEqual(db.execute('SELECT halt FROM control').fetchone()[0],'CIRCUIT_BREAKER')
            journal.resume_after_backoff(last['retry_at']+1)
            with closing(journal.open()) as db:self.assertIsNone(db.execute('SELECT halt FROM control').fetchone()[0])
            journal.breaker(now=1000,success=False,hard_reason='PROVIDER_418_UNKNOWN_EXPIRY')
            journal.resume_after_backoff(100000)
            with closing(journal.open()) as db:self.assertEqual(db.execute('SELECT halt FROM control').fetchone()[0],'PROVIDER_418_UNKNOWN_EXPIRY')

    def test_startup_network_or_missing_receipt_hold_stops_without_market(self):
        import sys,time
        with tempfile.TemporaryDirectory(dir='D:/ZS-SMART-GATE/temp') as folder:
            root=Path(folder)
            head=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
            tree=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD^{tree}'],text=True).strip()
            import shutil
            from zs_smart_gate.stage05_contracts import digest
            git=shutil.which('git')
            (root/'release.json').write_text(json.dumps(dict(head=head,tree=tree,
                git_executable=git,git_sha256=digest(Path(git).read_bytes()))))
            process=subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/ops24-worker.py'),'Serve','--root',str(root)],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                until=time.monotonic()+12
                while not (root/'status.json').exists() and time.monotonic()<until and process.poll() is None:
                    time.sleep(.1)
                self.assertTrue((root/'status.json').exists())
                report=json.loads((root/'status.json').read_bytes())
                self.assertEqual(report['status'],'STARTUP_HOLD')
                self.assertEqual(report['scope'],'READ_ONLY_NO_MARKET_ACTIVITY')
                (root/'STOP_REQUESTED').write_text('emergency stop')
                stdout,stderr=process.communicate(timeout=5)
                self.assertEqual(process.returncode,2,stderr.decode(errors='replace'))
                self.assertIn(b'OPERATOR_STOP_OR_DISABLED',stdout)
                self.assertFalse((root/'cycles').exists())
            finally:
                if process.poll() is None:process.kill();process.communicate()

    def test_probe_uses_pinned_git_in_minimal_service_environment(self):
        import sys,shutil,os
        from zs_smart_gate.stage05_contracts import digest
        with tempfile.TemporaryDirectory(dir='D:/ZS-SMART-GATE/temp') as folder:
            root=Path(folder)
            git=shutil.which('git')
            (root/'release.json').write_text(json.dumps(dict(git_executable=git,
                 git_sha256=digest(Path(git).read_bytes()))))
            # This is a service-environment simulation, NOT an actual logoff.
            env=dict(SystemRoot=os.environ['SystemRoot'],WINDIR=os.environ['SystemRoot'],
                 PATH=os.environ['SystemRoot']+'\\System32',TEMP='D:/ZS-SMART-GATE/temp',
                 TMP='D:/ZS-SMART-GATE/temp',USERPROFILE=os.environ['SystemRoot']+'\\System32\\config\\systemprofile')
            process=subprocess.run([sys.executable,'-I','-B',str(ROOT/'scripts/ops24-worker.py'),
                 'Probe','--root',str(root)],env=env,capture_output=True,timeout=25,
                 creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(process.returncode,0,process.stderr.decode(errors='replace'))
            report=json.loads((root/'probe.json').read_bytes())
            self.assertTrue(report['normal_token'])
            self.assertEqual(report['market_calls'],0)
            self.assertEqual(report['telegram_calls'],0)
            self.assertTrue(report['head'])
