"""Focused Stage03→Stage04 compatibility seam tests; Windows local only."""
from copy import deepcopy
from dataclasses import replace
import unittest

from test_stage03_r1_closed_parent import CLOSE, DECISION, fixture
from zs_smart_gate.stage03_r2_raw_features import evaluate_raw_research_batch
from zs_smart_gate.stage03_research_handoff import make_handoff, verify_handoff
from zs_smart_gate.stage05_contracts import ContractError, ensure_event
from zs_smart_gate.stage05_delivery import plan


def synthetic_handoff():
    row = evaluate_raw_research_batch(
        (fixture(),), closed_at=CLOSE, decision_at=DECISION)[0]
    return make_handoff(row)


class TestStage03ResearchHandoff(unittest.TestCase):
    def test_r0_r2_to_stage04_research_only_with_stable_digest(self):
        a = synthetic_handoff()
        self.assertTrue(verify_handoff(a))
        self.assertEqual(a, synthetic_handoff())
        self.assertEqual(a["qualification_state"], "UNKNOWN")
        self.assertFalse(a["delivery_authorized"])
        self.assertIsNone(a["signal_id"])
        self.assertEqual(a["evaluation_status"], "POLICY_HOLD")

    def test_no_stage05_promotion_or_delivery_from_research(self):
        handoff = synthetic_handoff()
        with self.assertRaises(ContractError):
            ensure_event(handoff)
        with self.assertRaises(ContractError):
            plan(handoff)

    def test_any_mutation_fails_exact_sha_and_legacy_unchanged(self):
        packet = synthetic_handoff()
        changed = deepcopy(packet)
        changed["raw_features"]["body_to_range"]["raw_value"] = "1"
        with self.assertRaisesRegex(ContractError, "RECORD_HASH_MISMATCH"):
            verify_handoff(changed)
        self.assertTrue(verify_handoff(packet))

    def test_disallowed_policy_or_missing_feature_rejected(self):
        row = evaluate_raw_research_batch(
            (fixture(),), closed_at=CLOSE, decision_at=DECISION)[0]
        changed = deepcopy(row)
        changed["qualification_state"] = "QUALIFIED"
        with self.assertRaisesRegex(ContractError, "NOT_ADMITTED"):
            make_handoff(changed)
        changed = deepcopy(row)
        changed["raw_features"]["closing_location"]["gate_result"] = "PASS"
        with self.assertRaises(ContractError):
            make_handoff(changed)
        changed = deepcopy(row)
        changed["raw_features_status"] = "NOT_ADMISSIBLE"
        with self.assertRaises(ContractError):
            make_handoff(changed)

    def test_invalid_window_does_not_create_admitted_handoff(self):
        raw = fixture()
        broken = replace(raw, children=raw.children[:-1])
        row = evaluate_raw_research_batch(
            (broken,), closed_at=CLOSE, decision_at=DECISION)[0]
        with self.assertRaisesRegex(ContractError, "NOT_ADMITTED"):
            make_handoff(row)
