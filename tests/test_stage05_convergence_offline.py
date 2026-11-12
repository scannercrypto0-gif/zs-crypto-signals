"""Targeted offline Stage05 contract convergence; no Telegram, HTTP, or old suite."""
from dataclasses import replace
from datetime import timezone
from unittest.mock import patch
import unittest

from test_stage05_real_telegram import config, event, T0
from test_stage03_research_handoff import synthetic_handoff
from zs_smart_gate.stage05_contracts import (
    ContractError, canonical, digest, ensure_event, make_document,
)
from zs_smart_gate.stage05_delivery import plan
from zs_smart_gate.stage05_interactive import InteractiveService, analysis_request_id
from zs_smart_gate.stage05_telegram_http import RuntimeFlags


class Stage05ConvergenceOfflineTests(unittest.TestCase):
    def test_three_distinct_bot_tokens_owner_a_b_and_c_equals_a(self):
        c=config()
        c.validate()
        self.assertEqual(len({c.signals_token,c.analytics_token,c.interactive_token}),3)
        self.assertNotEqual(c.signals_chat_a,c.signals_chat_b)
        self.assertEqual(c.analytics_chat,c.signals_chat_a)
        self.assertEqual(c.interactive_chats,frozenset((c.signals_chat_a,c.signals_chat_b)))
        self.assertEqual(c.interactive_users,c.interactive_chats)
        with self.assertRaises(ContractError):
            replace(c,analytics_chat=c.signals_chat_b).validate()
        with self.assertRaises(ContractError):
            replace(c,interactive_users=frozenset((c.signals_chat_a,))).validate()

    def test_one_synthetic_qualified_signal_three_separate_deliveries(self):
        test_only=event()
        jobs=plan(test_only)
        self.assertEqual([(j.destination,j.bot_id) for j in jobs],
                         [("A","SIGNALS"),("B","SIGNALS"),("C","ANALYTICS")])
        self.assertEqual(len({j.delivery_id for j in jobs}),3)
        self.assertEqual({j.signal_id for j in jobs},{"SYNTHETIC.SIGNAL.001"})
        self.assertEqual({j.candidate_id for j in jobs},{"SYNTHETIC.CANDIDATE.001"})
        self.assertEqual(plan(test_only),jobs)
        self.assertEqual(test_only["source_scope"],"SYNTHETIC_TEST_ONLY")

    def test_synthetic_rejected_candidate_c_only_no_signal(self):
        candidate=event(rejected=True)
        jobs=plan(candidate)
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0].destination,"C")
        self.assertEqual(jobs[0].bot_id,"ANALYTICS")
        self.assertIsNone(jobs[0].signal_id)
        doc=make_document(candidate)
        self.assertEqual(digest(doc["document"]),doc["manifest"]["sha256"])
        self.assertEqual(doc["manifest"]["signal_id"],None)

    def test_no_qualification_from_unknown_or_new_r2_research(self):
        unknown=event(rejected=True)
        unknown["qualification_status"]="UNKNOWN"
        with self.assertRaises(ContractError):
            ensure_event(unknown)
        research=synthetic_handoff()
        with self.assertRaises(ContractError):
            plan(research)

    def test_05c_read_only_two_authorized_accounts_without_network(self):
        c=config()
        service=InteractiveService(
            config=c, supported_symbols={"BTCUSDT","ETHUSDT"},
            lookup=lambda symbol: {
                "symbol":symbol, "as_of":"2026-11-09T08:35:01Z",
                "source_scope":"SYNTHETIC_TEST_ONLY",
                "indicators":[], "score":None,
                "decision":"NO_APPROVED_REAL_QUALIFICATION",
                "reason_codes":["RESEARCH_SNAPSHOT_ONLY"],
            }, clock=lambda:T0,
        )
        self.assertEqual(service.accept(
            text="BTCusdt",user_id="9999",chat_id="9999",message_id=1)["status"],
            "UNAUTHORIZED")
        with patch("socket.create_connection",
                   side_effect=AssertionError("NO_NETWORK_ALLOWED")), \
             patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_NETWORK_ALLOWED")):
            first=service.accept(text="btcusdt",user_id="1001",chat_id="1001",message_id=11)
            self.assertEqual(first["status"],"QUEUED")
            self.assertEqual(first["analysis_request_id"],
                             analysis_request_id("1001","1001",11))
            first_result=service.process_one()
            self.assertEqual(first_result["status"],"READ_ONLY_ANALYSIS")
            self.assertTrue(first_result["no_new_signal_generated"])
            self.assertIsNone(first_result["signal_id"])
            second=service.accept(text="ethusdt",user_id="1002",chat_id="1002",message_id=12)
            self.assertEqual(second["status"],"QUEUED")
            second_result=service.process_one()
            self.assertEqual(second_result["status"],"READ_ONLY_ANALYSIS")
            self.assertIsNone(second_result["signal_id"])

    def test_05c_cannot_claim_future_snapshot_or_wrong_actor(self):
        c=config()
        s=InteractiveService(
            config=c,supported_symbols={"BTCUSDT"},
            lookup=lambda symbol: {
                "symbol":symbol,"as_of":"2099-01-01T00:00:00Z",
                "indicators":[],"score":None,
            },clock=lambda:T0)
        self.assertEqual(s.accept(
            text="btcusdt",user_id="1001",chat_id="1002",message_id=1)["status"],
            "UNAUTHORIZED")
        self.assertEqual(s.accept(
            text="btcusdt",user_id="1001",chat_id="1001",message_id=2)["status"],
            "QUEUED")
        self.assertEqual(s.process_one()["status"],"INVALID_SNAPSHOT")
        self.assertFalse(RuntimeFlags().signals)
        self.assertFalse(RuntimeFlags().analytics)
