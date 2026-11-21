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
from zs_smart_gate.ops24_clock import sign, check_clock, collect
from zs_smart_gate.ops24_runtime import RuntimeJournal, supervisor
from test_p0_clock_73 import valid_receipts

ROOT=Path(__file__).resolve().parents[1]


class Ops24ClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from zs_smart_gate.stage05_contracts import digest
        cls.private=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        cls.public=cls.private.public_key().public_bytes(
            serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        cls.pin=digest(cls.public)

    def payload(self):
        observations=valid_receipts()
        policy=dict(policy_id=clock.POLICY_ID,source=clock.SOURCE,limits=clock.CANDIDATE)
        result=clock.assess(observations,sync_age_s=10,policy=policy)
        return dict(schema="zs.ops24.clock-witness.v1",head="a"*40,tree="b"*40,
                    purpose="OPERATIONAL_CLOCK_ONLY",policy_sha256=clock.REVIEWED_POLICY_SHA256,
                    mono=100,wall=1000,valid_seconds=30,uncertainty_s=.075,
                    observations=observations,assessment=result,sync_age_s=10)

    def verify(self,envelope,**values):
        return check_clock(envelope,self.public,self.pin,head="a"*40,tree="b"*40,
                           mono=lambda:values.get("mono",110),wall=lambda:values.get("wall",1010))

    def test_normal_worker_verifies_operational_only_signed_observations(self):
        result=self.verify(sign(self.payload(),self.private))
        self.assertEqual(result["status"],"OPERATIONAL_TIME_ACCEPTED")
        self.assertEqual(result["independent_cryptographic_utc"],"NOT_PROVEN")

    def test_stale_future_step_and_reboot_witness_are_held(self):
        witness=sign(self.payload(),self.private)
        for mono,wall in ((131,1031),(99,999),(110,1011),(1,1010)):
            with self.subTest(mono=mono,wall=wall),self.assertRaises(Hold):
                self.verify(witness,mono=mono,wall=wall)

    def test_modified_witness_wrong_key_and_scope_fail(self):
        envelope=sign(self.payload(),self.private)
        envelope["payload"]["mono"]=105
        with self.assertRaises(Hold):
            self.verify(envelope)
        for field,value in (("head","c"*40),("purpose","SCIENTIFIC_UTC"),("policy_sha256","d"*64)):
            payload=self.payload()
            payload[field]=value
            with self.assertRaises(Hold):
                self.verify(sign(payload,self.private))
        with self.assertRaises(Hold):
            check_clock(sign(self.payload(),self.private),self.public,"f"*64,
                        head="a"*40,tree="b"*40)

    def test_valid_signature_does_not_make_bad_clock_observations_valid(self):
        payload=self.payload()
        payload["observations"]["source"]["exit"]=5
        with self.assertRaises(Hold):
            self.verify(sign(payload,self.private))

    def test_unprivileged_publisher_refused_before_key_or_command_access(self):
        with patch("zs_smart_gate.ops24_clock.is_admin",return_value=False):
            with self.assertRaisesRegex(Hold,"EXPLICIT_ADMIN_CONTEXT"):
                collect(Path("D:/unused-private-key"),Path("D:/unused-clock"),head="a"*40,tree="b"*40)


class Ops24SupervisorTests(unittest.TestCase):
    def test_disabled_or_missing_activation_never_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            journal=RuntimeJournal(root)
            window=journal.plan(1800,"head")
            def forbidden(*args):
                self.fail("network cycle was invoked")
            with patch("zs_smart_gate.ops24_clock.is_admin",return_value=False):
                with self.assertRaises(Hold):
                    supervisor(root,window,activation=lambda:False,run_cycle=forbidden,clock=lambda:True)
                (root/"DISABLED").write_text("disabled")
                with self.assertRaises(Hold):
                    supervisor(root,window,activation=lambda:True,run_cycle=forbidden,clock=lambda:True)

    def test_elevated_worker_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder,patch("zs_smart_gate.ops24_clock.is_admin",return_value=True):
            with self.assertRaisesRegex(Hold,"NORMAL_USER_TOKEN"):
                supervisor(folder,"unused",activation=lambda:True,run_cycle=lambda _:None,clock=lambda:True)

    def test_stop_and_singleton_hold_and_restart_slots(self):
        from zs_smart_gate.windows_runner import process_lock
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            journal=RuntimeJournal(root)
            window=journal.plan(1800,"head")
            with patch("zs_smart_gate.ops24_clock.is_admin",return_value=False):
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
            with patch("zs_smart_gate.ops24_clock.is_admin",return_value=False), \
                 patch("zs_smart_gate.ops24_runtime.resources",return_value=dict(cpu_seconds=1)):
                result=supervisor(root,window,activation=lambda:True,
                    run_cycle=lambda _:dict(coverage="MARKET_COVERAGE_VERIFIED",eligible=45,validated=45),
                    clock=lambda:True,wall=lambda:current[0],sleep=sleep)
            self.assertEqual(sum(row["state"]=="PASS" for row in result["slots"]),2)
            self.assertEqual(result["stability"],"24H_STABILITY_NOT_PROVEN")

    def test_signed_activation_cannot_be_replaced_by_bare_flags(self):
        module=runpy.run_path(str(ROOT/"scripts"/"ops24-worker.py"))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"release.json").write_text(json.dumps(dict(authority_sha256=None)))
            (root/"authority.public.pem").write_text("untrusted")
            with self.assertRaisesRegex(Hold,"PROTECTED_CLOCK_DEPLOYMENT"):
                module["activation"](root,"a"*40,"b"*40)

    def test_worker_writable_authority_is_not_trusted(self):
        from zs_smart_gate.ops24_clock import protected_authority
        with tempfile.TemporaryDirectory(dir="D:/ZS-SMART-GATE/temp") as folder:
            root=Path(folder)
            (root/"release.json").write_text("{}")
            (root/"authority.public.pem").write_text("synthetic untrusted key")
            with self.assertRaisesRegex(Hold,"TRUST_ACL_NOT_PROVEN"):
                protected_authority(root)

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
