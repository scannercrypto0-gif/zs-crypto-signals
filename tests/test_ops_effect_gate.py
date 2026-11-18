from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from zs_smart_gate.ops_effect_gate import EffectGate, ROLES
from zs_smart_gate.stage05_contracts import digest
from zs_smart_gate.stage05_custody import LocalOutbox


class Endpoint:
    def __init__(self, role):
        self.role = role
        self.calls = 0
        self.last = None
        self.crash = False

    def execute(self, key, raw):
        self.calls += 1
        self.last = {"role":self.role, "signal_id":"sig-"+"a"*64, "sha256":digest(raw), "state":"VERIFIED"}
        if self.crash:
            raise OSError("simulated lost reply")
        return self.last

    def reconcile(self, key, pin):
        return self.last


class EffectGateTests(TestCase):
    def test_roles_are_default_off_and_reconcile_without_resending(self):
        signal = {"scope":"APPROVED_REAL_SOURCE","signal_id":"sig-"+"a"*64,"trading_authorized":False}
        with TemporaryDirectory() as folder:
            path = Path(folder)/"journal.db"
            routes = {role:Endpoint(role) for role in ROLES}

            def controller():
                # Authority callbacks and endpoints are fixtures, not admitted real proofs.
                return EffectGate(LocalOutbox(path),routes,lambda role, permit: permit == role,lambda _:True)

            self.assertEqual(EffectGate(LocalOutbox(path),routes).step("telegram-a",signal)["status"],
                             "BLOCKED_PERMISSION")
            for role in ROLES:
                with self.subTest(role=role):
                    self.assertEqual(controller().step(role,signal,"other")["status"],"BLOCKED_PERMISSION")
                    self.assertEqual(controller().step(role,dict(signal,scope="SYNTHETIC_TEST_ONLY"),role)["status"],
                                     "BLOCKED_QUALIFICATION")
                    routes[role].crash = True
                    self.assertEqual(controller().step(role,signal,role)["status"],
                                     "EFFECT_RECONCILIATION_REQUIRED")
                    self.assertEqual(controller().step(role,signal,role)["state"],"VERIFIED")
                    self.assertEqual(controller().step(role,signal,role)["state"],"VERIFIED")
                    self.assertEqual(routes[role].calls,1)
                    self.assertEqual(controller().step(role,dict(signal,changed=True),role)["status"],
                                     "EFFECT_CONTENT_CONFLICT")
