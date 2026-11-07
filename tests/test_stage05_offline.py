"""ZS05-001 only: isolated synthetic three-destination integration acceptance."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import socket
from unittest.mock import patch
import unittest

from zs_smart_gate.stage03a_contracts import EventIdentity, Direction, Horizon, ResearchEvent
from zs_smart_gate.stage05_offline import (
    DESTINATIONS, SyntheticDetectedSignal, DisabledMockTransport, MemoryReceiptStore,
    OfflineThreeDestinationRouter, OfflineInteractiveReader, Envelope, canonical, sha256,
)

T=datetime(2026,11,7,12,0,tzinfo=timezone.utc)


def example(direction=Direction.UP, horizon=Horizon.INTRADAY,
            score="1.00",symbol="BTCUSDT",rule="ZS05_SYNTHETIC_FIXTURE_V1"):
    identity=EventIdentity.research_key(
        symbol=symbol,horizon=horizon,direction=direction,
        setup_type="SYNTHETIC_CONTINUATION",decision_candle_close_at=T,
        rule_version=rule,event_discriminator="OFFLINE_CASE_A")
    return SyntheticDetectedSignal(
        identity=identity,decision_at=T,
        source_id="SYNTHETIC:ZS05_001",
        source_ref="SYNTHETIC:OFFLINE_FIXTURE_001",
        evidence_quality="SYNTHETIC_PIT_UNVERIFIED",
        reason_codes=("SIMULATED_DETECTED_FOR_ROUTER_ONLY",),
        score=score,score_version=(
            "SCORE_UNAVAILABLE" if score is None else
            "SYNTHETIC_SCORE_FOR_FORMATTER_ONLY"),
    )


class Stage05OfflineIntegrationTests(unittest.TestCase):
    def pipeline(self,failures=None):
        store=MemoryReceiptStore()
        tr=DisabledMockTransport(failures)
        return store,tr,OfflineThreeDestinationRouter(store,tr)

    def test_one_end_to_end_one_identity_three_independent_receipts_and_sha(self):
        store,transport,router=self.pipeline()
        sig=example()
        # Even if the process can normally reach network, this path cannot use it.
        with patch.object(socket,"socket",side_effect=AssertionError("NO_NETWORK")):
            result=router.route(sig)
        self.assertEqual(result["signal_id"],sig.signal_id)
        self.assertTrue(sig.signal_id.startswith("ZS05-SIM-"))
        self.assertEqual(result["mode"],"OFFLINE_DISABLED_SIMULATION")
        receipts=result["receipts"]
        self.assertEqual([r["destination"] for r in receipts],list(DESTINATIONS))
        self.assertEqual(len({r["idempotency_key"] for r in receipts}),3)
        self.assertEqual(len({r["snapshot_sha256"] for r in receipts}),1)
        self.assertTrue(all(r["status"]=="MOCK_DELIVERED" for r in receipts))
        self.assertTrue(all(r["signal_id"]==sig.signal_id for r in receipts))
        self.assertTrue(all(not r["external_sent"] and not r["durable_readback"]
                            for r in receipts))
        bodies=result["message_bodies"]
        self.assertEqual(bodies[0]["human"],bodies[1]["human"])
        self.assertNotEqual(bodies[0]["human"],bodies[2]["human"])
        self.assertIsNone(bodies[0]["analytics_json"])
        analytics=bodies[2]["analytics_json"]
        self.assertEqual(analytics["signal_id"],sig.signal_id)
        self.assertEqual(analytics["source_snapshot_sha256"],
                         sha256(store.snapshots[sig.signal_id]))
        self.assertEqual(bodies[2]["payload_sha256"],
                         Envelope.build(sig.snapshot(),DESTINATIONS[2]).payload_sha256)
        self.assertEqual(bodies[2]["analytics_json_sha256"],sha256(canonical(analytics)))
        self.assertIsNone(bodies[0]["analytics_json_sha256"])
        self.assertEqual(transport.mock_attempts,list(DESTINATIONS))
        self.assertEqual((result["external_sends"],result["market_calls"],result["real_secrets"]),(0,0,0))
        # Print only synthetic routing / hash / receipt aggregate; no market rows.
        print("ZS05_001_SYNTHETIC_DEMO="+json.dumps({
            "signal_id":result["signal_id"],
            "snapshot_sha256":result["snapshot_sha256"],
            "destinations":[{"name":r["destination"],"status":r["status"],
                             "attempts":r["attempts"]} for r in receipts],
            "external_sends":0,"market_calls":0,"real_secrets":0,
            "source":"SYNTHETIC_ONLY","qualified_live_signal":False,
        },sort_keys=True))

    def test_four_horizon_direction_combinations_and_no_short(self):
        for h in Horizon:
            for d in Direction:
                with self.subTest(h=h,d=d):
                    store,tr,router=self.pipeline()
                    sig=example(direction=d,horizon=h)
                    result=router.route(sig)
                    primary=result["message_bodies"][0]["human"]
                    self.assertIn("Direction: "+d.value,primary)
                    self.assertIn("Horizon: "+h.value,primary)
                    self.assertIn(sig.signal_id,primary)
                    self.assertIn("NO SHORT" if d==Direction.DOWN else "UP",primary)
                    self.assertEqual(len(result["receipts"]),3)

    def test_low_score_not_filtered_and_score_unavailable_explicit(self):
        for score in ("0.00","0.01",None,"99.99"):
            with self.subTest(score=score):
                store,tr,router=self.pipeline()
                s=example(score=score)
                r=router.route(s)
                self.assertEqual(len(tr.mock_attempts),3)
                primary=r["message_bodies"][0]["human"]
                if score is None:
                    self.assertIn("Score: SCORE_UNAVAILABLE",primary)
                    self.assertIsNone(r["message_bodies"][2]["analytics_json"]["decision"]["score"])
                else:
                    self.assertIn("Score: "+score,primary)

    def test_research_event_cannot_be_promoted_or_routed(self):
        store,tr,router=self.pipeline()
        # Constructor-independent type guard; real ResearchEvent always has candidate status.
        empty_research=object.__new__(ResearchEvent)
        with self.assertRaisesRegex(PermissionError,"RESEARCH_CANDIDATE_NOT_DETECTED_SIGNAL"):
            router.route(empty_research)
        with self.assertRaises(PermissionError):
            router.route({"status":"RESEARCH_CANDIDATE","signal_id":"FAKE"})
        self.assertEqual(tr.mock_attempts,[])

    def test_injected_failure_isolated_then_retry_only_failed_destination(self):
        store,tr,router=self.pipeline({"PRIMARY_CHAT_B":1})
        signal=example()
        first=router.route(signal)
        self.assertEqual([x["status"] for x in first["receipts"]],
                         ["MOCK_DELIVERED","MOCK_FAILED","MOCK_DELIVERED"])
        self.assertEqual(len(tr.mock_attempts),3)
        second=router.route(signal)
        self.assertEqual([x["status"] for x in second["receipts"]],
                         ["MOCK_DELIVERED"]*3)
        self.assertEqual([x["attempts"] for x in second["receipts"]],[1,2,1])
        self.assertEqual(tr.mock_attempts,["PRIMARY_CHAT_A","PRIMARY_CHAT_B",
                                           "ANALYTICS_CHAT_C","PRIMARY_CHAT_B"])
        self.assertEqual((tr.external_sends,tr.market_calls),(0,0))

    def test_bounded_mock_retries_stop_after_three_failures(self):
        store,tr,router=self.pipeline({"ANALYTICS_CHAT_C":999})
        s=example()
        for i in range(6):
            result=router.route(s)
        c=result["receipts"][2]
        self.assertEqual(c["status"],"MOCK_RETRY_EXHAUSTED")
        self.assertEqual(c["attempts"],3)
        self.assertEqual(tr.mock_attempts.count("ANALYTICS_CHAT_C"),3)
        self.assertEqual(tr.mock_attempts.count("PRIMARY_CHAT_A"),1)
        self.assertEqual(tr.mock_attempts.count("PRIMARY_CHAT_B"),1)
        self.assertEqual(tr.external_sends,0)

    def test_replay_restart_with_same_memory_receipt_store_is_deduped(self):
        store,tr,router=self.pipeline()
        signal=example()
        first=router.route(signal)
        new_transport=DisabledMockTransport()
        restarted=OfflineThreeDestinationRouter(store,new_transport)
        second=restarted.route(example())
        self.assertEqual(first["receipts"],second["receipts"])
        self.assertEqual(new_transport.mock_attempts,[])
        self.assertEqual(len(store.snapshots),1)
        self.assertEqual(len(store.receipts),3)

    def test_replay_without_retained_mock_store_does_not_claim_durable_dedup(self):
        s=example()
        first=OfflineThreeDestinationRouter(MemoryReceiptStore(),DisabledMockTransport())
        second=OfflineThreeDestinationRouter(MemoryReceiptStore(),DisabledMockTransport())
        self.assertEqual(first.route(s)["signal_id"],second.route(s)["signal_id"])
        self.assertFalse(first.route(s)["durable_readback"])
        self.assertEqual(len(second.transport.mock_attempts),3)

    def test_mutated_same_event_snapshot_fail_closed_before_dispatch(self):
        store,tr,router=self.pipeline()
        router.route(example(score="1"))
        before=list(tr.mock_attempts)
        with self.assertRaisesRegex(ValueError,"SAME_EVENT_MUTATED_SNAPSHOT_BLOCKED"):
            router.route(example(score="2"))
        self.assertEqual(before,tr.mock_attempts)

    def test_wrong_receipt_fingerprint_fail_closed_before_attempt(self):
        store,tr,router=self.pipeline()
        result=router.route(example())
        receipt=store.receipts[result["receipts"][1]["idempotency_key"]]
        store.receipts[receipt.idempotency_key]=replace(receipt,payload_sha256="0"*64)
        before=list(tr.mock_attempts)
        with self.assertRaisesRegex(ValueError,"RECEIPT_IDEMPOTENCY_CONFLICT_BLOCKED"):
            router.route(example())
        self.assertEqual(before,tr.mock_attempts)

    def test_no_real_transport_constructor_accepted(self):
        store=MemoryReceiptStore()
        with self.assertRaises(PermissionError):
            OfflineThreeDestinationRouter(store,object())
        with self.assertRaises(PermissionError):
            OfflineThreeDestinationRouter(object(),DisabledMockTransport())

    def test_incomplete_or_untrusted_source_and_trade_levels_rejected(self):
        sig=example()
        for changed in (
            {"source_id":"BINANCE:SPOT:BTCUSDT"},
            {"source_ref":"https://example.com/live"},
            {"evidence_quality":"PIT_VERIFIED"},
            {"reason_codes":()},
            {"plan_status":"TRADE_READY"},
            {"score":"101"},
            {"score_version":"PRODUCTION_SCORE"},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    replace(sig,**changed)
        self.assertIsNone(sig.identity.signal_id)

    def test_05c_authorization_and_readonly_query_are_separate(self):
        store,tr,router=self.pipeline()
        sig=example(horizon=Horizon.SWING)
        router.route(sig)
        reader=OfflineInteractiveReader(store,frozenset({"SYNTHETIC:OWNER"}))
        before=dict(store.snapshots),dict(store.receipts)
        for command in ("/status","/swing","/analyze BTCUSDT",
                        "/signal "+sig.signal_id):
            out=reader.query("SYNTHETIC:OWNER",command)
            self.assertEqual(out["count"],1)
            self.assertFalse(out["new_signal_generated"])
            self.assertEqual(out["snapshots"][0]["signal_id"],sig.signal_id)
        self.assertEqual((store.snapshots,store.receipts),before)
        self.assertEqual((tr.external_sends,tr.market_calls),(0,0))
        for who,cmd in (("UNKNOWN","/status"),("SYNTHETIC:ATTACKER","/status")):
            with self.assertRaises(PermissionError):
                reader.query(who,cmd)
        for cmd in ("/trade","/poll","/signal ZS05-SIM-"+"a"*32,
                    "/intraday","/analyze ETHUSDT","status","/status  "):
            with self.assertRaises(ValueError):
                reader.query("SYNTHETIC:OWNER",cmd)

    def test_identity_changed_direction_horizon_changes_sim_signal_id(self):
        ids=set()
        for h in Horizon:
            for d in Direction:
                ids.add(example(d,h).signal_id)
        self.assertEqual(len(ids),4)

    def test_injected_transport_exception_is_redacted_and_isolated(self):
        class ExplodingTransport(DisabledMockTransport):
            def attempt(self,envelope):
                if envelope.destination=="PRIMARY_CHAT_A":
                    self.mock_attempts.append(envelope.destination)
                    raise RuntimeError("SENSITIVE_FAKE_TOKEN_NEVER_LOG")
                return super().attempt(envelope)
        store=MemoryReceiptStore()
        tr=ExplodingTransport()
        result=OfflineThreeDestinationRouter(store,tr).route(example())
        self.assertEqual([r["status"] for r in result["receipts"]],
                         ["MOCK_FAILED","MOCK_DELIVERED","MOCK_DELIVERED"])
        self.assertNotIn("SENSITIVE_FAKE_TOKEN",json.dumps(result))
        self.assertEqual(tr.external_sends,0)


if __name__=="__main__":
    unittest.main()
