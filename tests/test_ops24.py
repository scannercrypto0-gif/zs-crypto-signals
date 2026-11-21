"""OPS24 B1 and supervisor offline failure-injection acceptance."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
import json
from pathlib import Path
import runpy
import sqlite3
import tempfile
import threading
import time
import unittest

from zs_smart_gate.ops24_budget import Budget, Hold, Policy
from zs_smart_gate.ops24_source import Client, scan
from zs_smart_gate.ops24_runtime import RuntimeJournal
from zs_smart_gate.stage05_contracts import canonical, digest

ROOT=Path(__file__).resolve().parents[1]
fixtures=runpy.run_path(str(ROOT/"tests"/"test_marketwide_research.py"))


class FakeMarket:
    def __init__(self,count=7):
        self.names=[f"ASSET{i:03d}USDT" for i in range(count)]
        self.packets={s:fixtures["packet"](s,"UP" if i%2 else "DOWN") for i,s in enumerate(self.names)}
        sample=next(iter(self.packets.values()))
        self.boundary=sample["boundary_ms"]
        self.epoch=self.boundary/1000+10
        self.calls=[]
        self.active=self.peak=0
        self.lock=threading.Lock()
        self.fail_status=None
        self.invalid=None

    def get(self,path,params,timeout,limit):
        with self.lock:
            self.calls.append((path,params))
            self.active+=1
            self.peak=max(self.peak,self.active)
        try:
            time.sleep(.001)
            if path=="exchangeInfo":
                body=dict(symbols=[dict(symbol=s,baseAsset=s[:-4],quoteAsset="USDT",isSpotTradingAllowed=True,
                                       status="TRADING") for s in self.names],
                          rateLimits=[dict(rateLimitType="REQUEST_WEIGHT",interval="MINUTE",intervalNum=1,limit=6000)])
            elif path=="ticker/24hr":
                body=[dict(symbol=s,quoteVolume="50000000",closeTime=int(self.epoch*1000)) for s in self.names]
            elif path=="ticker/bookTicker":
                body=[dict(symbol=s,bidPrice="100",askPrice="100.01") for s in self.names]
            else:
                if self.fail_status:
                    return self.fail_status,{"Retry-After":"120"},b""
                body=copy.deepcopy(self.packets[params["symbol"]]["frames"][params["interval"]]["rows"])
                if self.invalid==params["symbol"] and params["interval"]=="30m":
                    body[0][4]="999"
            return 200,{"X-MBX-USED-WEIGHT-1M":"1400"},canonical(body)
        finally:
            with self.lock:
                self.active-=1

    def stamp(self):
        from datetime import datetime,timezone
        return datetime.fromtimestamp(self.epoch,timezone.utc).isoformat().replace("+00:00","Z")


class Ops24BudgetTests(unittest.TestCase):
    def test_dynamic_budget_all_pairs_and_shared_final_decision(self):
        for count in (1,7,45):
            with self.subTest(count=count),tempfile.TemporaryDirectory() as folder:
                market=FakeMarket(count)
                budget=Budget(folder,"one-boundary")
                client=Client(budget,get=market.get,guard=lambda:True,stamp=market.stamp)
                result=scan(client,boundary_ms=market.boundary,wall=lambda:market.epoch,stamp=market.stamp)
                self.assertEqual(result["coverage"],"MARKET_COVERAGE_VERIFIED",result.get("stop"))
                self.assertEqual(result["eligible"],count)
                self.assertEqual(result["validated"],count)
                self.assertEqual(result["budget"]["requests"],3+4*count)
                self.assertEqual(result["budget"]["weight"],104+8*count)
                self.assertEqual(result["decision_at"],market.stamp())
                self.assertLessEqual(market.peak,2)
                self.assertTrue(all(row["directions"][0]["signal_id"] is None for row in result["rows"]))

    def test_atomic_inflight_reservations_do_not_oversubscribe(self):
        with tempfile.TemporaryDirectory() as folder:
            budget=Budget(folder,"cycle")
            def reserve(i):
                try:
                    budget.reserve("klines",dict(symbol=str(i)))
                    return True
                except Hold:
                    return False
            with ThreadPoolExecutor(max_workers=10) as pool:
                accepted=list(pool.map(reserve,range(10)))
            self.assertEqual(sum(accepted),2)
            self.assertEqual(budget.state()["active"],2)
            self.assertEqual(budget.state()["requests"],2)

    def test_unknown_request_never_reissued_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            budget=Budget(folder,"cycle")
            budget.reserve("klines",dict(symbol="LOST"))
            restored=Budget(folder,"cycle")
            with self.assertRaisesRegex(Hold,"UNCERTAIN_REQUEST_NO_REISSUE"):
                restored.reserve("klines",dict(symbol="LOST"))
            self.assertEqual(restored.state()["requests"],1)

    def test_committed_body_reconciles_without_http_and_detects_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            market=FakeMarket()
            budget=Budget(folder,"cycle")
            client=Client(budget,get=market.get,guard=lambda:True,stamp=market.stamp)
            first=client.get("ticker/bookTicker",{})
            client.get("ticker/bookTicker",{})
            self.assertEqual(len(market.calls),1)
            key=digest(canonical(["ticker/bookTicker",{}]))
            (Path(folder)/(key+".private")).write_bytes(b"tampered")
            with self.assertRaisesRegex(Hold,"RECEIPT_BODY_CORRUPTION"):
                client.get("ticker/bookTicker",{})
            self.assertEqual(first["payload"][0]["symbol"],market.names[0])

    def test_ban_and_rate_limit_stop_without_retry(self):
        for status in (429,418):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as folder:
                market=FakeMarket()
                market.fail_status=status
                budget=Budget(folder,"cycle")
                result=scan(Client(budget,get=market.get,guard=lambda:True,stamp=market.stamp),
                    boundary_ms=market.boundary,wall=lambda:market.epoch,stamp=market.stamp)
                self.assertIn("HTTP_"+str(status),result["stop"])
                self.assertNotEqual(result["coverage"],"MARKET_COVERAGE_VERIFIED")
                self.assertLessEqual(len(market.calls),5)

    def test_all_inputs_rechecked_at_final_decision_and_invalid_pair_partial(self):
        with tempfile.TemporaryDirectory() as folder:
            market=FakeMarket(5)
            market.invalid=market.names[0]
            result=scan(Client(Budget(folder,"cycle"),get=market.get,guard=lambda:True,stamp=market.stamp),
                boundary_ms=market.boundary,wall=lambda:market.epoch,stamp=market.stamp)
            self.assertEqual(result["validated"],4)
            self.assertEqual(result["coverage"],"MARKET_COVERAGE_PARTIAL")

    def test_untrusted_clock_makes_no_http(self):
        with tempfile.TemporaryDirectory() as folder:
            market=FakeMarket()
            result=scan(Client(Budget(folder,"cycle"),get=market.get,guard=lambda:False),
                        boundary_ms=market.boundary,wall=lambda:market.epoch)
            self.assertEqual(len(market.calls),0)
            self.assertEqual(result["coverage"],"BLOCKED")

    def test_step_deadline_and_byte_reservations_fail_closed(self):
        for mode in ("STEP","DEADLINE","BYTES"):
            clock=[100.,1000.]
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
                budget=Budget(folder,"cycle",mono=lambda:clock[0],wall=lambda:clock[1])
                if mode=="STEP":
                    clock[1]+=1
                elif mode=="DEADLINE":
                    clock[0]+=110
                    clock[1]+=110
                else:
                    with closing(budget.open()) as db:
                        db.execute("UPDATE control SET bytes=?",(budget.policy.max_bytes,))
                with self.assertRaises(Hold):
                    budget.reserve("klines",{})

    def test_partial_response_body_retained_and_no_fake_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            def oversized(path,params,timeout,limit):
                return 200,{"X-MBX-USED-WEIGHT-1M":"20"},b"x"*(limit+1)
            budget=Budget(folder,"cycle")
            with self.assertRaisesRegex(Hold,"BODY_CAP"):
                Client(budget,get=oversized,guard=lambda:True).get("klines",{})
            self.assertEqual(len(list(Path(folder).glob("*.private"))),1)
            self.assertEqual(budget.state()["active"],0)
            self.assertEqual(budget.state()["halt"],"BODY_CAP")

    def test_server_quota_is_adopted_conservatively(self):
        with tempfile.TemporaryDirectory() as folder:
            budget=Budget(folder,"cycle")
            budget.adopt_server_limit(2000)
            self.assertEqual(budget.state()["effective_weight_limit"],1500)
            with self.assertRaises(Hold):
                budget.adopt_server_limit(500)

    def test_result_replay_is_idempotent_and_hash_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            market=FakeMarket(2)
            budget=Budget(folder,"cycle")
            client=Client(budget,get=market.get,guard=lambda:True,stamp=market.stamp)
            first=scan(client,boundary_ms=market.boundary,wall=lambda:market.epoch,stamp=market.stamp)
            total=len(market.calls)
            self.assertEqual(scan(client,boundary_ms=market.boundary),first)
            self.assertEqual(len(market.calls),total)
            (Path(folder)/"result.json").write_bytes(b"{}")
            with self.assertRaisesRegex(Hold,"RESULT_READBACK_CORRUPTION"):
                scan(client,boundary_ms=market.boundary)


class Ops24RuntimeTests(unittest.TestCase):
    def test_planned_24h_is_not_elapsed_proof_and_enumerates_all_slots(self):
        with tempfile.TemporaryDirectory() as folder:
            journal=RuntimeJournal(folder)
            window=journal.plan(1800,"head")
            report=journal.report(window,1800)
            self.assertEqual(len(report["slots"]),336)
            self.assertEqual(report["planned_health"],288)
            self.assertEqual(report["planned_boundaries"],48)
            self.assertEqual(report["stability"],"24H_STABILITY_NOT_PROVEN")
            journal.missed(window,1800+86400)
            report=RuntimeJournal(folder).report(window,1800+86400)
            self.assertTrue(report["complete_elapsed"])
            self.assertNotEqual(report["stability"],"24H_COMPLETE")
            self.assertTrue(all(row["state"]=="MISSED" for row in report["slots"]))

    def test_restart_never_reclaims_unknown_slot_and_detects_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            journal=RuntimeJournal(folder)
            window=journal.plan(1800,"head")
            self.assertTrue(journal.reserve(window,"boundary",1800))
            self.assertFalse(RuntimeJournal(folder).reserve(window,"boundary",1800))
            journal.finish(window,"boundary",1800,"PARTIAL",dict(eligible=5,validated=4))
            with closing(journal.open()) as db:
                db.execute("UPDATE slots SET payload=? WHERE kind='boundary' AND at=1800",(b"{}",))
            with self.assertRaisesRegex(Hold,"RUNTIME_JOURNAL_CORRUPTION"):
                journal.report(window,1900)

    def test_circuit_breaker_and_ban_require_explicit_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            journal=RuntimeJournal(folder)
            for now in (100,110,130):
                result=journal.breaker(now=now,success=False)
            self.assertEqual(result["halt"],"CIRCUIT_BREAKER")
            self.assertGreater(result["retry_at"],130)
            self.assertEqual(journal.breaker(now=200,success=True)["halt"],"CIRCUIT_BREAKER")

    def test_legacy_budget_contract_is_preserved(self):
        from zs_smart_gate.marketwide_capture import MAX_REQUESTS,MAX_WEIGHT
        self.assertEqual((MAX_REQUESTS,MAX_WEIGHT),(11,140))


    def test_timeout_never_reissues_and_records_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            def timeout(*args):
                calls.append(1)
                raise TimeoutError()
            budget=Budget(folder,"cycle")
            client=Client(budget,get=timeout,guard=lambda:True)
            with self.assertRaises(Hold):
                client.get("klines",{})
            with self.assertRaises(Hold):
                client.get("klines",{})
            self.assertEqual(len(calls),1)
            self.assertEqual(budget.state()["halt"],"TRANSPORT_UNKNOWN_NO_REISSUE")

    def test_complete_receive_before_crash_can_reconcile_without_second_http(self):
        with tempfile.TemporaryDirectory() as folder:
            market=FakeMarket()
            budget=Budget(folder,"cycle")
            client=Client(budget,get=market.get,guard=lambda:True,stamp=market.stamp)
            from unittest.mock import patch
            with patch.object(budget,"finish",side_effect=OSError("synthetic crash before commit")):
                with self.assertRaises(OSError):
                    client.get("ticker/bookTicker",{})
            restored=Budget(folder,"cycle")
            key=digest(canonical(["ticker/bookTicker",{}]))
            restored.reconcile(key)
            recovered=Client(restored,get=market.get,guard=lambda:True).get("ticker/bookTicker",{})
            self.assertEqual(len(market.calls),1)
            self.assertTrue(recovered["payload"])

    def test_final_decision_rechecks_oldest_market_and_candle_input(self):
        with tempfile.TemporaryDirectory() as folder:
            market=FakeMarket(3)
            def final_stamp():
                # Discovery's current timestamp stays frozen; the final D changes
                # only after every expected HTTP response has arrived.
                if len(market.calls)>=15:
                    return "2026-09-01T02:02:00Z"
                return market.stamp()
            client=Client(Budget(folder,"cycle"),get=market.get,guard=lambda:True,stamp=market.stamp)
            result=scan(client,boundary_ms=market.boundary,wall=lambda:market.epoch,stamp=final_stamp)
            self.assertEqual(result["validated"],0)
            self.assertEqual(result["coverage"],"MARKET_COVERAGE_PARTIAL")
            self.assertTrue(all(row["state"]=="DATA_INVALID" for row in result["rows"]))

    def test_science_intake_replays_original_bytes_without_qualification(self):
        from zs_smart_gate.ops24_science import intake
        with tempfile.TemporaryDirectory() as folder:
            market=FakeMarket(3)
            client=Client(Budget(folder,"cycle"),get=market.get,guard=lambda:True,stamp=market.stamp)
            result=scan(client,boundary_ms=market.boundary,wall=lambda:market.epoch,stamp=market.stamp)
            report=intake(folder)
            self.assertEqual(report["events"],3)
            self.assertEqual(report["signals_created"],0)
            self.assertFalse(report["up_qualified"])
            self.assertFalse(report["down_qualified"])
            self.assertIsNone(report["precision"])
            self.assertIsNone(report["return_after_costs"])
            first=next(Path(folder).glob("*.private"))
            first.write_bytes(b"corruption")
            with self.assertRaises(Hold):
                intake(folder)

    def test_receive_and_final_clock_fingerprints_are_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            market=FakeMarket(2)
            proof=dict(status="SYNTHETIC_TEST_CLOCK",witness_sha256="a"*64)
            client=Client(Budget(folder,"cycle"),get=market.get,guard=lambda:True,
                          stamp=market.stamp,clock_receipt=lambda:proof)
            result=scan(client,boundary_ms=market.boundary,wall=lambda:market.epoch,stamp=market.stamp)
            self.assertEqual(result["decision_clock"],proof)
            self.assertEqual(result["metrics"]["requests_measured"],11)
            self.assertGreaterEqual(result["metrics"]["p95_request_seconds"],0)
            for path in Path(folder).glob("*.receipt.json"):
                receipt=json.loads(path.read_bytes())
                self.assertEqual(receipt["started_clock"],proof)
                self.assertEqual(receipt["received_clock"],proof)
