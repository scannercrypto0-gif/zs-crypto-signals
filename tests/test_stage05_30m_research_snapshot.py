"""Stage05C read-only closed-30m integration: no network/bots/production."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import unittest
from unittest.mock import patch

from test_stage03_r1_closed_parent import CLOSE, DECISION, fixture
from test_stage05_real_telegram import config
from zs_smart_gate.stage03_r2_raw_features import evaluate_raw_research_batch
from zs_smart_gate.stage05_30m_research_snapshot import snapshot_from_r2
from zs_smart_gate.stage05_interactive import InteractiveService
from zs_smart_gate.stage05_contracts import ContractError


def r2():
    return evaluate_raw_research_batch(
        (fixture(),), closed_at=CLOSE, decision_at=DECISION)[0]


class Stage05ThirtyMinuteResearchTests(unittest.TestCase):
    def test_30m_converter_never_creates_signal_or_numeric_gate(self):
        snap=snapshot_from_r2(r2())
        self.assertEqual(snap["source_frame"],"30m")
        self.assertEqual(snap["symbol"],"BTCUSDT")
        self.assertEqual(snap["decision"],"RESEARCH_30M_POLICY_HOLD")
        self.assertIsNone(snap["signal_id"])
        self.assertIsNone(snap["score"])
        present=[x for x in snap["indicators"] if x["availability"]=="PRESENT"]
        not_implemented=[x for x in snap["indicators"]
                         if x["availability"]=="NOT_IMPLEMENTED"]
        self.assertGreater(len(present),5)
        self.assertGreater(len(not_implemented),4)
        self.assertTrue(all(x["evaluation"]=="UNKNOWN" and x["threshold"] is None
                            for x in snap["indicators"]))
        self.assertTrue(all(x["as_of"] is None and x["raw_value"] is None
                            for x in not_implemented))

    def test_authorized_05c_reads_30m_and_accepts_null_as_of_when_unimplemented(self):
        snap=snapshot_from_r2(r2())
        service=InteractiveService(
            config=config(), supported_symbols={"BTCUSDT"},
            lookup=lambda _:snap,clock=lambda:DECISION+timedelta(seconds=2))
        with patch("socket.create_connection",
                   side_effect=AssertionError("NETWORK_FORBIDDEN")), \
             patch("urllib.request.urlopen",
                   side_effect=AssertionError("NETWORK_FORBIDDEN")):
            self.assertEqual(service.accept(
                text="btcusdt",user_id="1001",chat_id="1001",message_id=430)["status"],
                "QUEUED")
            result=service.process_one()
        self.assertEqual(result["status"],"READ_ONLY_ANALYSIS")
        self.assertEqual(result["source_frame"],"30m")
        self.assertEqual(result["decision"],"RESEARCH_30M_POLICY_HOLD")
        self.assertTrue(result["no_new_signal_generated"])
        self.assertIsNone(result["signal_id"])
        self.assertTrue(any(x["availability"]=="NOT_IMPLEMENTED"
                            for x in result["indicators"]))
        rendered=service.format_reply(result)
        self.assertLessEqual(len(rendered),3900)
        self.assertIn("RESEARCH_ONLY_POLICY_HOLD",rendered)
        self.assertIn("Displayed ",rendered)
        self.assertIn("omitted ",rendered)

    def test_wrong_user_and_future_data_rejected(self):
        snap=snapshot_from_r2(r2())
        service=InteractiveService(
            config=config(),supported_symbols={"BTCUSDT"},
            lookup=lambda _:snap,clock=lambda:DECISION-timedelta(minutes=1))
        self.assertEqual(service.accept(
            text="BTCUSDT",user_id="7777",chat_id="7777",message_id=1)["status"],
            "UNAUTHORIZED")
        self.assertEqual(service.accept(
            text="BTCUSDT",user_id="1002",chat_id="1002",message_id=2)["status"],
            "QUEUED")
        self.assertEqual(service.process_one()["status"],"INVALID_SNAPSHOT")

    def test_changed_feature_or_parent_identity_cannot_pass(self):
        row=r2()
        corrupted=deepcopy(row)
        corrupted["raw_features"]["body_to_range"]["raw_value"]="999"
        with self.assertRaisesRegex(ContractError,"FEATURE_SHA"):
            snapshot_from_r2(corrupted)
        corrupted=deepcopy(row)
        corrupted["qualification_state"]="QUALIFIED"
        with self.assertRaises(ContractError):
            snapshot_from_r2(corrupted)
        corrupted=deepcopy(row)
        corrupted["identity"]["parent_close_at"]="2026-11-11T12:35:00Z"
        with self.assertRaises(ContractError):
            snapshot_from_r2(corrupted)

    def test_legacy_5m_snapshot_is_still_readable(self):
        data={"symbol":"BTCUSDT","as_of":"2026-11-11T12:30:10Z",
              "source_frame":"5m","closed_at":"2026-11-11T12:30:00Z",
              "source_sha256":"a"*64,"decision_sha256":"b"*64,
              "indicators":[],"score":None,"decision":"LEGACY_READ_ONLY"}
        service=InteractiveService(
            config=config(),supported_symbols={"BTCUSDT"},lookup=lambda _:data,
            clock=lambda:DECISION+timedelta(seconds=2))
        service.accept(text="BTCUSDT",user_id="1001",chat_id="1001",message_id=3)
        self.assertEqual(service.process_one()["status"],"READ_ONLY_ANALYSIS")
