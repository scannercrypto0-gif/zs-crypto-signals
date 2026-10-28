"""03B3 deterministic futures, source receipt, finite budgets, immutable study E2E.

No network in this suite; actual LIVE requires manual post-close dispatch.
"""
from __future__ import annotations

import dataclasses
import io
import json
import unittest
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from unittest.mock import patch

from zs_smart_gate.binance_live import LiveBlocked
from zs_smart_gate.core import score_v1_partial
from zs_smart_gate.stage03a_contracts import Horizon
from zs_smart_gate.stage03b1_live import DURATION_MS
from zs_smart_gate.stage03b2_manifest import MANIFEST as OLD_MANIFEST
from zs_smart_gate.stage03b3_manifest import (
    MANIFEST,SELECTION_EVIDENCE_RUN,ELIGIBLE_UNIVERSE_SHA,Slot,
)
from zs_smart_gate.stage03b3_selection import choose_third,preselect_once
from zs_smart_gate.stage03b3_capture import capture_once,main as capture_main
from zs_smart_gate.stage03b3_terminal import terminal_report
from zs_smart_gate.stage03b2_research import frozen_hash,seal_record

UTC=timezone.utc


def raw_candle(start_ms,duration_ms,base="10",quote="1000"):
    return [start_ms,"100","102","99","101",base,
            start_ms+duration_ms-1,quote,42,"5","500","0"]


class Fake:
    def __init__(self,horizon=Horizon.INTRADAY,slot="I1",symbol="BTCUSDT"):
        self.horizon=horizon
        self.slot=MANIFEST.slot(symbol,horizon,slot)
        self.symbol=symbol
        self.now_ms=int(self.slot.close_at.timestamp()*1000)+1000
        self.physical=0
        self.mode=None
        self.extras=0
        self.paths=[]
    def clock(self):
        return self.now_ms+200
    def __call__(self,path,params=None,*,on_attempt=None):
        for _ in range(self.extras):
            on_attempt(path)
            self.physical+=1
        on_attempt(path)
        self.physical+=1
        self.paths.append(path)
        at=self.now_ms+25*self.physical
        meta={"path":path,"t0_local_ms":at-20,
              "received_local_ms":at,"latency_ms":20,
              "http_status":200,"used_weight_1m":str(self.physical*2)}
        if self.mode=="network_block" and path=="/api/v3/klines":
            raise LiveBlocked("PROVIDER_BLOCKED_TEST")
        if path=="/api/v3/time":
            return {"serverTime":self.now_ms if self.mode!="server_early"
                    else self.now_ms-2000},meta
        if path=="/api/v3/exchangeInfo":
            return {"symbols":[{"symbol":self.symbol,"quoteAsset":"USDT",
                                "status":"TRADING","isSpotTradingAllowed":True}]},meta
        if path=="/api/v3/ticker/24hr":
            return {"symbol":self.symbol,"quoteVolume":
                    "2000" if self.mode=="ineligible" else "60000000"},meta
        if path=="/api/v3/ticker/bookTicker":
            return {"symbol":self.symbol,"bidPrice":"100","askPrice":"100.01"},meta
        if path!="/api/v3/klines":
            raise AssertionError("UNEXPECTED_ROUTE")
        length=int(params["limit"])
        duration=DURATION_MS[params["interval"]]
        first=int(params["startTime"])
        rows=[raw_candle(first+i*duration,duration) for i in range(length)]
        if params["interval"] in ("30m","4h"):
            n=6 if params["interval"]=="30m" else 4
            rows[0][5]=str(n*10)
            rows[0][7]=str(n*1000)
            if self.mode=="parent_current":
                rows[0][0]+=duration
                rows[0][6]+=duration
            if self.mode=="base_mismatch":
                rows[0][5]=str(n*10+1)
            if self.mode=="quote_mismatch":
                rows[0][7]=str(n*1000+1)
        else:
            if self.mode=="missing":
                rows=rows[:-1]
            if self.mode=="duplicate":
                rows[-1]=rows[-2][:]
            if self.mode=="stale":
                for row in rows:
                    row[0]-=duration
                    row[6]-=duration
            if self.mode=="invalid_timestamp":
                rows[-1][6]+=1
        if self.mode=="early_receipt" and path=="/api/v3/klines":
            meta["received_local_ms"]=self.now_ms-4000
        if self.mode=="late_receipt" and path=="/api/v3/klines":
            meta["received_local_ms"]=int(self.slot.close_at.timestamp()*1000)+601000
        return rows,meta


class UniversePreselectionTests(unittest.TestCase):
    def test_first_sorted_asset_and_reject_tampered_order(self):
        self.assertEqual(choose_third(["AAVEUSDT","BTCUSDT","ETHUSDT"]),"AAVEUSDT")
        self.assertEqual(choose_third(["BTCUSDT","ETHUSDT"]),None)
        with self.assertRaisesRegex(ValueError,"NOT_SORTED"):
            choose_third(["ETHUSDT","BTCUSDT","AAVEUSDT"])
        with self.assertRaisesRegex(ValueError,"NOT_SORTED"):
            choose_third(["AAVEUSDT","AAVEUSDT","BTCUSDT"])

    def test_selection_real_universe_module_and_four_attempts(self):
        class UniverseFake:
            def __init__(self):
                self.physical=0
            def __call__(self,path,params=None,*,on_attempt):
                on_attempt(path)
                self.physical+=1
                t=1761654200000
                meta={"path":path,"t0_local_ms":t-50,"received_local_ms":t,
                      "latency_ms":50,"used_weight_1m":"2","http_status":200}
                if path=="/api/v3/time":
                    return {"serverTime":t},meta
                if path=="/api/v3/exchangeInfo":
                    return {"symbols":[{"symbol":s,"quoteAsset":"USDT",
                            "status":"TRADING","isSpotTradingAllowed":True}
                            for s in ["ETHUSDT","AAVEUSDT","BTCUSDT"]]},meta
                if path=="/api/v3/ticker/24hr":
                    return [{"symbol":s,"quoteVolume":"30000000"}
                            for s in ["BTCUSDT","ETHUSDT","AAVEUSDT"]],meta
                if path=="/api/v3/ticker/bookTicker":
                    return [{"symbol":s,"bidPrice":"100","askPrice":"100.01"}
                            for s in ["AAVEUSDT","BTCUSDT","ETHUSDT"]],meta
                raise AssertionError("BAD_ROUTE")
        fake=UniverseFake()
        result=preselect_once(getter=fake)
        self.assertEqual(result["status"],"PRESELECTED",result)
        self.assertEqual(result["selected_third"],"AAVEUSDT")
        self.assertEqual(result["physical_attempts"],4)
        self.assertEqual(fake.physical,4)
        self.assertEqual(result["eligible_universe_sha256"],
                         frozen_hash(["AAVEUSDT","BTCUSDT","ETHUSDT"]))


class FrozenProtocolTests(unittest.TestCase):
    def test_study_id_deterministic_and_prior_study_unchanged(self):
        self.assertEqual(MANIFEST.study_id,dataclasses.replace(MANIFEST).study_id)
        self.assertTrue(MANIFEST.study_id.startswith("PROSPECTIVE-SHA256-"))
        self.assertEqual(MANIFEST.planned_observations,12)
        self.assertEqual(MANIFEST.assets,("BTCUSDT","ETHUSDT","AAVEUSDT"))
        self.assertEqual(MANIFEST.selection_run,SELECTION_EVIDENCE_RUN)
        self.assertEqual(MANIFEST.eligible_universe_sha256,ELIGIBLE_UNIVERSE_SHA)
        self.assertEqual(OLD_MANIFEST.study_id,
            "STUDY-SHA256-d5e70d796516f68e00e2c132f09f4201a65942189727c9e00a1a451ec9ec4f62")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            MANIFEST.start_at=MANIFEST.stop_at

    def test_all_changes_new_fingerprint_or_explicit_rejection(self):
        new=dataclasses.replace(MANIFEST,metrics=MANIFEST.metrics+("new_metric",))
        self.assertNotEqual(new.study_id,MANIFEST.study_id)
        with self.assertRaisesRegex(ValueError,"THREE_IMMUTABLY_SELECTED"):
            dataclasses.replace(MANIFEST,assets=("BTCUSDT","ETHUSDT","ADAUSDT"))
        with self.assertRaisesRegex(ValueError,"BUDGET"):
            dataclasses.replace(MANIFEST,total_slot_attempt_ceiling=97)
        with self.assertRaisesRegex(ValueError,"ONE_FINITE_24H"):
            dataclasses.replace(MANIFEST,stop_at=MANIFEST.stop_at+timedelta(hours=1))

    def test_two_future_utc_aligned_per_horizon_and_strict_24h_stop(self):
        self.assertEqual([s.label for s in MANIFEST.slots],["I1","I2","S1","S2"])
        self.assertEqual(MANIFEST.stop_at-MANIFEST.start_at,timedelta(hours=24))
        self.assertLess(MANIFEST.selection_at,MANIFEST.start_at)
        self.assertEqual([s.close_at.hour for s in MANIFEST.slots],[14,14,16,20])
        with self.assertRaisesRegex(ValueError,"INVALID_UTC_CLOSE"):
            Slot(Horizon.INTRADAY,datetime(2026,10,28,14,1,tzinfo=UTC),"bad")
        with self.assertRaisesRegex(ValueError,"INVALID_UTC_CLOSE"):
            Slot(Horizon.SWING,datetime(2026,10,29,0,0,1,tzinfo=UTC),"bad")
        with self.assertRaisesRegex(ValueError,"EXACTLY_FOUR"):
            dataclasses.replace(MANIFEST,slots=MANIFEST.slots[::-1])
        with self.assertRaisesRegex(ValueError,"UNDECLARED"):
            MANIFEST.slot("BTCUSDT",Horizon.INTRADAY,"S1")


class ProspectiveCaptureTests(unittest.TestCase):
    def run_sample(self,horizon=Horizon.INTRADAY,label=None,symbol="BTCUSDT",
                   fake=None,**kwargs):
        label=label or ("I1" if horizon is Horizon.INTRADAY else "S1")
        f=fake or Fake(horizon,label,symbol)
        return capture_once(symbol=symbol,horizon=horizon,slot_label=label,
                            getter=f,local_ms=f.clock,**kwargs)

    def test_future_not_attempted_no_network(self):
        f=Fake()
        # The supplied local_clock() adds 200ms; remain strictly before the close.
        f.now_ms=int(f.slot.close_at.timestamp()*1000)-500
        data=self.run_sample(fake=f)
        self.assertEqual(data["status"],"NOT_ATTEMPTED")
        self.assertEqual(data["telemetry"]["physical_http_attempts"],0)
        self.assertEqual(f.physical,0)
        self.assertIsNone(data["signal_id"])

    def test_ten_minute_expiry_no_retroactive_http(self):
        for horizon,label in ((Horizon.INTRADAY,"I2"),(Horizon.SWING,"S2")):
            f=Fake(horizon,label)
            f.now_ms=int(f.slot.close_at.timestamp()*1000)+601000
            data=self.run_sample(horizon,label,fake=f)
            self.assertEqual(data["status"],"LATE")
            self.assertEqual(f.physical,0)
            self.assertNotIn("features",data)

    def test_six_and_four_child_real_cross_stage_pit_e2e(self):
        results=[]
        for symbol in MANIFEST.assets:
            for horizon,label in ((Horizon.INTRADAY,"I1"),(Horizon.SWING,"S1")):
                f=Fake(horizon,label,symbol)
                data=self.run_sample(horizon,label,symbol,f)
                self.assertEqual(data["status"],"OBSERVED_PIT",data)
                self.assertEqual(data["reconciliation"]["status"],"PASS")
                self.assertEqual(data["coverage"]["children_fetched"],
                                 6 if horizon is Horizon.INTRADAY else 4)
                self.assertEqual(data["telemetry"]["physical_http_attempts"],6)
                self.assertEqual(data["source_payload_sha256"],frozen_hash(
                    data["source_parsed_original_numeric_strings"]))
                self.assertTrue(all(Decimal(x)==0 for x in data["deltas"].values()))
                self.assertEqual(set(data["features"]),{"UP","DOWN"})
                self.assertIsNone(data["score"])
                self.assertIsNone(data["source_publication_at"])
                self.assertEqual(data["trade_plan_status"],"RESEARCH_ONLY")
                self.assertIsNone(data["forward_outcome"])
                results.append(data)
        report=terminal_report(results,as_of=MANIFEST.start_at+timedelta(hours=12))
        self.assertEqual(report["observed_pit"],6)
        self.assertEqual(report["accounted_slots"],12)
        self.assertEqual(report["statuses"]["NOT_ATTEMPTED"],6)
        self.assertEqual(report["actual_http_attempts"],36)
        self.assertEqual(report["capture_state"],"PENDING_FUTURE_WINDOWS")
        self.assertEqual(report["predictive_inference"],"INSUFFICIENT_EVIDENCE")

    def test_explicit_time_exclusion_per_step(self):
        f=Fake()
        f.mode="server_early"
        d=self.run_sample(fake=f)
        self.assertEqual(d["status"],"NOT_ATTEMPTED")
        self.assertEqual(d["telemetry"]["physical_http_attempts"],1)
        self.assertEqual(f.physical,1)

    def test_current_ineligibility_not_historical_eligibility(self):
        f=Fake()
        f.mode="ineligible"
        d=self.run_sample(fake=f)
        self.assertEqual(d["status"],"INELIGIBLE",d)
        self.assertEqual(f.physical,4)
        self.assertIsNone(d["historical_eligibility"])
        self.assertNotIn("features",d)

    def test_bad_source_inputs_fail_closed(self):
        for mode in ("missing","duplicate","stale","parent_current",
                     "base_mismatch","quote_mismatch","invalid_timestamp",
                     "early_receipt","late_receipt","network_block"):
            for horizon,label in ((Horizon.INTRADAY,"I1"),(Horizon.SWING,"S1")):
                with self.subTest(mode=mode,horizon=horizon):
                    f=Fake(horizon,label)
                    f.mode=mode
                    d=self.run_sample(horizon,label,fake=f)
                    self.assertIn(d["status"],("FAILED","LATE"),d)
                    self.assertNotIn("features",d)
                    self.assertIsNone(d["signal_id"])
                    self.assertLessEqual(d["telemetry"]["physical_http_attempts"],8)

    def test_max_eight_physical_gets_including_retries(self):
        f=Fake()
        f.extras=2
        result=self.run_sample(fake=f)
        self.assertEqual(result["status"],"FAILED")
        self.assertEqual(result["telemetry"]["physical_http_attempts"],8)
        self.assertEqual(f.physical,8)
        self.assertIn("PHYSICAL_ATTEMPT_BUDGET_EXHAUSTED",result["reason"])

    def test_no_request_after_soft_60s_guard(self):
        f=Fake()
        ticks=iter([0,61,61,61,61])
        d=self.run_sample(fake=f,monotonic=lambda:next(ticks))
        self.assertEqual(d["status"],"FAILED")
        self.assertEqual(f.physical,0)
        self.assertIn("SOFT_PRE_REQUEST_GUARD",d["reason"])

    def test_live_opt_in_is_mandatory(self):
        with patch("sys.stderr",new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as ex:
                capture_main(["--symbol","BTCUSDT","--horizon","INTRADAY","--slot","I1"])
        self.assertEqual(ex.exception.code,2)


class TerminalTests(unittest.TestCase):
    def sample(self):
        f=Fake()
        return capture_once(symbol="BTCUSDT",horizon=Horizon.INTRADAY,slot_label="I1",
                            getter=f,local_ms=f.clock)

    def test_forged_sha_or_raw_content_rejected(self):
        data=self.sample()
        forged={**data,"status":"LATE"}
        with self.assertRaisesRegex(ValueError,"UNSEALED_OR_TAMPERED"):
            terminal_report([forged],as_of=MANIFEST.stop_at)
        content={**data,"source_parsed_original_numeric_strings":{**data[
            "source_parsed_original_numeric_strings"],"symbol":"ETHUSDT"}}
        content=seal_record(content)
        with self.assertRaisesRegex(ValueError,"RAW_CANDLE_CONTENT_REVISED"):
            terminal_report([content],as_of=MANIFEST.stop_at)

    def test_duplicate_captures_rejected_prevent_false_12_of_12(self):
        sample=self.sample()
        with self.assertRaisesRegex(ValueError,"DUPLICATE_PROSPECTIVE"):
            terminal_report([sample,sample],as_of=MANIFEST.stop_at)
        fake=seal_record({**sample,"study_id":"FOREIGN"})
        with self.assertRaisesRegex(ValueError,"UNAPPROVED_OR_CHANGED"):
            terminal_report([fake],as_of=MANIFEST.stop_at)

    def test_backdated_pit_or_future_receipt_rejected(self):
        data=self.sample()
        early=seal_record({**data,"decision_at":
                    (MANIFEST.slots[0].close_at-timedelta(seconds=1)).isoformat()})
        with self.assertRaisesRegex(ValueError,"BACKDATED_OR_LATE"):
            terminal_report([early],as_of=MANIFEST.stop_at)
        late=seal_record({**data,"receipt_at":{**data["receipt_at"],
                    "parent":(MANIFEST.slots[0].close_at+timedelta(minutes=20)).isoformat()}})
        with self.assertRaisesRegex(ValueError,"PIT_RECEIPT_OUTSIDE"):
            terminal_report([late],as_of=MANIFEST.stop_at)

    def test_terminal_twelve_exact_and_twentyfour_hour_cap(self):
        all_rows=[]
        for symbol in MANIFEST.assets:
            for slot in MANIFEST.slots:
                f=Fake(slot.horizon,slot.label,symbol)
                row=capture_once(symbol=symbol,horizon=slot.horizon,slot_label=slot.label,
                                 getter=f,local_ms=f.clock)
                self.assertEqual(row["status"],"OBSERVED_PIT",row)
                all_rows.append(row)
        report=terminal_report(all_rows,as_of=MANIFEST.stop_at)
        self.assertEqual(report["capture_state"],"TERMINAL")
        self.assertEqual(report["observed_pit"],12)
        self.assertEqual(report["actual_http_attempts"],72)
        self.assertLessEqual(report["actual_http_attempts"],96)
        self.assertEqual(report["accounted_slots"],12)
        self.assertEqual(report["terminal_evidence_status"],"INSUFFICIENT_EVIDENCE")

    def test_expired_missing_slots_are_explicit_blocked_data(self):
        report=terminal_report([],as_of=MANIFEST.stop_at+timedelta(seconds=1))
        self.assertEqual(report["statuses"]["NOT_ATTEMPTED"],12)
        self.assertEqual(report["terminal_evidence_status"],"BLOCKED_DATA")
        self.assertFalse(report["numeric_trade_authorization"])

    def test_forbidden_score_or_trade_plan_and_attempt_overrun(self):
        d=self.sample()
        tampered=seal_record({**d,"score":72})
        with self.assertRaisesRegex(ValueError,"FORBIDDEN_SIGNAL"):
            terminal_report([tampered],as_of=MANIFEST.stop_at)
        t={**d,"telemetry":{**d["telemetry"],"physical_http_attempts":9}}
        with self.assertRaisesRegex(ValueError,"PER_SLOT_PHYSICAL"):
            terminal_report([seal_record(t)],as_of=MANIFEST.stop_at)

    def test_old_v1_research_unmodified(self):
        r=score_v1_partial(Decimal("1"),Decimal("2"),Decimal("12"))
        self.assertEqual(r["version"],"V1_PARTIAL_RESEARCH_ONLY")
        self.assertIsNone(r["total"])
        self.assertEqual(r["status"],"SCORE_UNAVAILABLE")


if __name__=="__main__":
    unittest.main()
