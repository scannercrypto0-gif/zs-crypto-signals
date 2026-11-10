"""Only new Stage05C round-2 session/permit and launcher safety checks.

No Bot API, Binance, user-session access, or old 16/16 and 12/12 reruns.
"""
import ast
from pathlib import Path
import tempfile
import unittest

from zs_smart_gate.stage05_contracts import canonical, digest
from zs_smart_gate.stage05_custody import LocalOutbox

REPO = Path(__file__).resolve().parents[1]
SOURCE = (REPO / "scripts" / "stage05c-once.py").read_text(encoding="utf-8")
LAUNCHER = (REPO / "scripts" / "launch-stage05c-once.ps1").read_text(encoding="utf-8")
OLD_SESSION = "ISSUE51-6762796319-05C-ONCE"
NEW_SESSION = "ISSUE56-6764588810-05C-ROUND2-ONCE"
PERMIT = "OWNER-APPROVED-ISSUE56-6764588810-05C-ROUND2-ONCE"


def assignments():
    tree = ast.parse(SOURCE)
    return {
        target.id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
        if isinstance(node.value, ast.Constant)
    }


class Round2SessionOnlyTests(unittest.TestCase):
    def test_unique_static_authorization_without_old_permit(self):
        constants = assignments()
        self.assertEqual(constants["SESSION"], NEW_SESSION)
        self.assertEqual(constants["PERMIT_DECISION"], PERMIT)
        self.assertNotIn('OwnerPermit("OWNER-APPROVED-ISSUE51', SOURCE)
        self.assertIn("OwnerPermit(PERMIT_DECISION, head,", SOURCE)
        self.assertNotIn("SESSION = " + repr(OLD_SESSION), SOURCE)

    def test_round2_directory_is_separate_without_old_root_mutations(self):
        self.assertIn('ROOT = Path("D:/ZS-SMART-GATE/stage51-05c-round2-6764588810")', SOURCE)
        self.assertNotIn('ROOT = Path("D:/ZS-SMART-GATE/stage51-05c-once")', SOURCE)
        self.assertIn("$root = 'D:\\ZS-SMART-GATE\\stage51-05c-round2-6764588810'", LAUNCHER)
        self.assertNotIn("$root = 'D:\\ZS-SMART-GATE\\stage51-05c-once'", LAUNCHER)

    def test_prior_consumed_session_remains_immutable_and_new_one_is_one_shot(self):
        with tempfile.TemporaryDirectory() as folder:
            previous = Path(folder) / "round1"
            current = Path(folder) / "round2"
            previous.mkdir()
            current.mkdir()
            old = LocalOutbox(previous / "out.sqlite")
            new = LocalOutbox(current / "out.sqlite")
            oldkey = "interactive-session/" + digest(canonical(OLD_SESSION))
            newkey = "interactive-session/" + digest(canonical(NEW_SESSION))
            self.assertNotEqual(oldkey, newkey)
            self.assertTrue(old.create_if_absent(oldkey, b"consumed round one"))
            self.assertTrue(new.create_if_absent(newkey, b"consumed round two"))
            self.assertFalse(new.create_if_absent(newkey, b"retry forbidden"))
            self.assertEqual(old.read(oldkey), b"consumed round one")
            self.assertEqual(new.read(newkey), b"consumed round two")

    def test_manual_gate_and_preflight_before_python_live(self):
        self.assertIn("if ($Live) {", LAUNCHER)
        self.assertIn("ROUND2_BOTH_HUMANS_AND_EXCLUSIVE_POLL_REQUIRED", LAUNCHER)
        self.assertIn("ROUND2_EXACT_SHA_OFFLINE_PREFLIGHT_REQUIRED", LAUNCHER)
        self.assertIn("AUTHORIZE ISSUE56 ROUND2 ", LAUNCHER)
        self.assertIn("ROUND2_OWNER_CONSOLE_ACK_MISSING", LAUNCHER)
        self.assertLess(LAUNCHER.index("ROUND2_OWNER_CONSOLE_ACK_MISSING"),
                        LAUNCHER.index("$loaded = @()"))
        self.assertIn("ROUND2_PREFLIGHT_PROVENANCE_MISMATCH", SOURCE)
        self.assertIn('if not args.live:', SOURCE)
        self.assertIn('if store.read(key) is not None:', SOURCE)

    def test_bounded_budget_and_safe_scope_remain_unchanged(self):
        self.assertIn("len(calls) >= 12", SOURCE)
        self.assertIn('calls.count(method) >= 2', SOURCE)
        self.assertIn('method not in ("getMe", "getWebhookInfo", "getUpdates", "sendMessage")', SOURCE)
        self.assertIn("ROOT / stamp", SOURCE)
        self.assertIn("shared.save(folder / \"report.json\", report)", SOURCE)
        self.assertNotIn("capture(", SOURCE)
        self.assertNotIn("public_get(", SOURCE)
        self.assertNotIn("--session", SOURCE)
        self.assertNotIn("--permit", SOURCE)


if __name__ == "__main__":
    unittest.main()
