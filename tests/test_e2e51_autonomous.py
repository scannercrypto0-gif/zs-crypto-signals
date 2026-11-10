"""Offline-only checks of the autonomous owner-authorized route."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from test_e2e51 import config, fixture
from zs_smart_gate.e2e51 import Stop, analyze

spec = importlib.util.spec_from_file_location(
    "e2e51_autonomous", Path(__file__).resolve().parents[1] / "scripts/e2e51-autonomous.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class AutonomousTests(unittest.TestCase):
    def test_missing_config_cannot_claim_or_call_market(self):
        def missing():
            raise ValueError("PRIVATE_VALUE_MUST_NOT_BE_LOGGED")
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(Stop, "^BLOCKED_MISSING_LOCAL_CONFIGURATION$"):
                app.session(root, "head", "tree", check=missing,
                            market=lambda *_: self.fail("market called"))
            self.assertEqual(list(root.iterdir()), [])

    def test_prior_claim_blocks_before_credentials(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            root = Path(tmp)
            app.runner.save(root / "session.claim.json", {})
            with self.assertRaisesRegex(Stop, "FOLLOWUP_ALREADY_CLAIMED"):
                app.session(root, "head", "tree",
                            check=lambda: self.fail("credentials called"),
                            market=lambda *_: self.fail("market called"))

    def test_separable_outputs_do_not_poll_or_prompt(self):
        receipts, now = fixture()
        calls = []
        def api(role, method, fields, attachment):
            calls.append((role, method, fields))
            return {"message_id": len(calls), "date": 100,
                    "chat": {"type": "private", "id": int(fields["chat_id"])}}
        app.runner.deliver(analyze(receipts, now, synthetic=True), config(), api,
                           lambda *_: None, lambda *_: self.fail("prompted"), interactive=False)
        self.assertEqual([(r,m) for r,m,_ in calls], [
            ("05A","sendMessage"), ("05A","sendMessage"),
            ("05B","sendMessage"), ("05B","sendDocument")])
        self.assertIn("SYNTHETIC TEST ONLY / NOT A TRADING SIGNAL", calls[0][2]["text"])
