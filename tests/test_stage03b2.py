"""03B2 full offline manifest/PIT/anti-tamper/transport/cross-stage E2E.

Test GET responses imitate public Binance inclusive closeTime; NEVER network.
"""
from __future__ import annotations

import dataclasses
import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from zs_smart_gate.binance_live import LiveBlocked
from zs_smart_gate.mtf_contracts import CandleWindow
from zs_smart_gate.stage03a_contracts import Direction, Horizon
from zs_smart_gate.stage03b1_live import DURATION_MS, parse_kline
from zs_smart_gate.stage03b2_manifest import (
    MANIFEST, AssetSpec, Partition, StudyManifest, WindowSpec,
    RETROSPECTIVE_EVIDENCE,
)
from zs_smart_gate.stage03b2_research import (
    compare_study, competing_features, frozen_hash, seal_record,
)
from zs_smart_gate.stage03b2_live import main, run_session

UTC=timezone.utc
NOW=datetime(2026,10,28,12,30,tzinfo=UTC)
NOW_MS=int(NOW.timestamp()*1000)


def exchange_row(open_ms: int, size_ms: int, *, base="10",quote="1000"):
    return [open_ms,"100","102","99","101",base,
            open_ms+size_ms-1,quote,42,"5","500","0"]


class FakeBinance:
    """Source payloads and physical pre-request attempt accounting."""
    def __init__(self, symbol="BTCUSDT",horizon=Horizon.INTRADAY):
        self.symbol=symbol
        self.horizon=horizon
        self.actual_attempts=0
        self.logical_calls=0
        self.mode=None
        self.attempt_extra=0
        self.last_requested=[]
        self.weight=0

    def __call__(self,path,params=None,*,on_attempt=None):
        for _ in range(self.attempt_extra):
            on_attempt(path)
            self.actual_attempts+=1
        on_attempt(path)
        self.actual_attempts+=1
        self.logical_calls+=1
        self.last_requested.append((path,params))
        stamp=NOW_MS+self.logical_calls*25
        meta={"path":path,"t0_local_ms":stamp-50,
              "received_local_ms":stamp,"http_status":200,
              "used_weight_1m":str(self.logical_calls*2),
              "latency_ms":50}
        if path=="/api/v3/time":
            return {"serverTime":NOW_MS if self.mode!="future_parent"
                    else int(datetime(2026,10,13,tzinfo=UTC).timestamp()*1000)},meta
        if path=="/api/v3/exchangeInfo":
            return {"symbols":[{"symbol":self.symbol,"status":"TRADING",
                                "quoteAsset":"USDT","isSpotTradingAllowed":True}]},meta
        if path=="/api/v3/ticker/24hr":
            return {"symbol":self.symbol,"quoteVolume":"60000000"},meta
        if path=="/api/v3/ticker/bookTicker":
            return {"symbol":self.symbol,"bidPrice":"100","askPrice":"100.01"},meta
        if path!="/api/v3/klines":
            raise AssertionError("non-public unexpected endpoint")
        limit=int(params["limit"])
        duration=DURATION_MS[params["interval"]]
        start=int(params["startTime"])
        rows=[exchange_row(start+i*duration,duration) for i in range(limit)]
        if params["interval"] in ("30m","4h"):
            rows[0][5]=str(limit*(6 if params["interval"]=="30m" else 4)*10)
            rows[0][7]=str((6 if params["interval"]=="30m" else 4)*1000)
            if self.mode=="wrong_parent":
                rows[0][0]+=duration
                rows[0][6]+=duration
            if self.mode=="base_delta":
                rows[0][5]="60.001" if params["interval"]=="30m" else "40.001"
            if self.mode=="quote_delta":
                rows[0][7]="6000.001" if params["interval"]=="30m" else "4000.001"
        if params["interval"] in ("5m","1h"):
            if self.mode=="missing":
                rows=rows[:-1]
            if self.mode=="duplicate":
                rows[-1]=rows[-2][:]
            if self.mode=="stale":
                for row in rows:
                    row[0]-=duration
                    row[6]-=duration
            if self.mode=="tampered_close":
                rows[0][6]+=1
        if self.mode=="receipt_before_close" and path=="/api/v3/klines":
            meta["received_local_ms"]=int(datetime(
                2026,10,1,tzinfo=UTC).timestamp()*1000)
        return rows,meta


class ManifestTests(unittest.TestCase):
    def test_frozen_sha_stability_and_immutable_fields(self):
        self.assertTrue(MANIFEST.study_id.startswith("STUDY-SHA256-"))
        self.assertEqual(MANIFEST.study_id,dataclasses.replace(MANIFEST).study_id)
        self.assertEqual(MANIFEST.study_id, MANIFEST.as_dict()["study_id"])
        self.assertEqual(MANIFEST.planned_sessions,12)
        self.assertEqual(MANIFEST.retrospective_assumption,RETROSPECTIVE_EVIDENCE)
        self.assertEqual(tuple(w.partition for w in MANIFEST.windows),
                         (Partition.DEVELOPMENT,Partition.HOLDOUT))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            MANIFEST.version="03B2_TAMPER"

    def test_any_change_requires_new_study_sha(self):
        changed=dataclasses.replace(MANIFEST,baseline_formulas=MANIFEST.baseline_formulas+("new",))
        self.assertNotEqual(changed.study_id,MANIFEST.study_id)
        changed2=dataclasses.replace(MANIFEST,assets=MANIFEST.assets[::-1])
        self.assertNotEqual(changed2.study_id,MANIFEST.study_id)
        self.assertEqual(changed2.planned_sessions,12)
        moved=dataclasses.replace(MANIFEST,windows=(
            MANIFEST.windows[0],
            WindowSpec(Partition.HOLDOUT,MANIFEST.windows[1].close_at+timedelta(days=7),
                       "HOLD_NEW")))
        self.assertNotEqual(moved.study_id,MANIFEST.study_id)

    def test_split_leakage_overlap_and_duplicate_window_rejected(self):
        dev,hold=MANIFEST.windows
        for w in ((hold,dev),(dev,dev),
                  (dev,WindowSpec(Partition.HOLDOUT,dev.close_at,"same"))):
            with self.assertRaisesRegex(ValueError,"SPLIT_LEAKAGE|DUPLICATE_STUDY_WINDOW"):
                dataclasses.replace(MANIFEST,windows=w)
        with self.assertRaisesRegex(ValueError,"WINDOWS_MUST_ALIGN"):
            dataclasses.replace(MANIFEST,windows=(
                dev,WindowSpec(Partition.HOLDOUT,
                               hold.close_at+timedelta(minutes=30),"late")))

    def test_asset_duplication_window_session_prohibited(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE_ASSET"):
            dataclasses.replace(MANIFEST,assets=(MANIFEST.assets[0],MANIFEST.assets[0]))
        with self.assertRaisesRegex(ValueError,"SESSION_NOT_IN"):
            MANIFEST.session("NOTREALUSDT",Horizon.SWING,Partition.HOLDOUT)
        with self.assertRaisesRegex(ValueError,"UNAPPROVED_COHORT"):
            AssetSpec("BTCUSDT","KNOWN_HISTORICAL_HIGH")
        with self.assertRaisesRegex(ValueError,"CANNOT_CLAIM"):
            dataclasses.replace(MANIFEST,retrospective_assumption="TRUE_HISTORICAL_PIT")
        with self.assertRaisesRegex(ValueError,"PHYSICAL_ATTEMPT"):
            dataclasses.replace(MANIFEST,transport_attempt_budget=100)
        with self.assertRaisesRegex(ValueError,"INVALID_FROZEN"):
            AssetSpec("BTC/USDT","MAJOR_REFERENCE")

    def test_chronological_split_and_utc_rollover(self):
        dev,hold=MANIFEST.windows
        self.assertLess(dev.close_at,hold.close_at)
        self.assertEqual((hold.close_at-dev.close_at).days,7)
        self.assertEqual(dev.close_at.utcoffset(),timedelta())
        with self.assertRaisesRegex(ValueError,"timezone-aware"):
            WindowSpec(Partition.HOLDOUT,datetime(2026,10,28),"bad")
        monday=WindowSpec(Partition.HOLDOUT,
                          datetime(2026,10,26,8,tzinfo=UTC),"WEEKLY_BOUNDARY")
        self.assertEqual(monday.close_at.weekday(),0)


class SessionTests(unittest.TestCase):
    def run_fake(self,symbol="BTCUSDT",horizon=Horizon.INTRADAY,
                 partition=Partition.DEVELOPMENT,fake=None,**kw):
        getter=fake or FakeBinance(symbol,horizon)
        return run_session(symbol=symbol,horizon=horizon,partition=partition,
                           getter=getter,clock_ms=lambda:NOW_MS+1500,**kw)

    def test_all_frozen_sessions_e2e_and_no_signal(self):
        results=[]
        for asset in MANIFEST.assets:
            for horizon in MANIFEST.horizons:
                for partition in Partition:
                    fake=FakeBinance(asset.symbol,horizon)
                    data=self.run_fake(asset.symbol,horizon,partition,fake)
                    self.assertEqual(data["status"],"OBSERVED_EXACT_RECONCILIATION",data)
                    self.assertEqual(data["reconciliation"]["status"],"PASS")
                    self.assertEqual(data["measurements"]["physical_http_attempts"],6)
                    self.assertEqual(fake.actual_attempts,6)
                    self.assertEqual(data["coverage"]["children_received"],
                                     6 if horizon is Horizon.INTRADAY else 4)
                    self.assertEqual(set(data["features"]),{"UP","DOWN"})
                    self.assertIsNone(data["signal_id"])
                    self.assertFalse(data["qualified_signal"])
                    self.assertIsNone(data["historical_eligibility"])
                    self.assertIsNone(data["source_publication_at"])
                    self.assertIsNone(data["historical_decision_at"])
                    self.assertEqual(data["study_id"],MANIFEST.study_id)
                    results.append(data)
        summary=compare_study(results)
        self.assertEqual(summary["observed_sessions"],12)
        self.assertEqual(summary["expected_sessions"],12)
        self.assertEqual(summary["observed_by_partition"],
                         {"DEVELOPMENT":6,"HOLDOUT":6})
        self.assertEqual(summary["status"],"INSUFFICIENT_EVIDENCE")
        self.assertFalse(summary["independent_predictive_evidence"])
        self.assertIsNone(summary["approved_threshold"])
        self.assertEqual(summary["failed_or_missing_sessions"],0)

    def test_invalid_or_missing_history_never_has_features(self):
        for mode in ("missing","duplicate","stale","wrong_parent",
                     "tampered_close","base_delta","quote_delta",
                     "receipt_before_close"):
            for horizon in Horizon:
                with self.subTest(mode=mode,horizon=horizon):
                    fake=FakeBinance(horizon=horizon)
                    fake.mode=mode
                    data=self.run_fake(horizon=horizon,fake=fake)
                    self.assertIn(data["status"],("FAIL","INVALID"),data)
                    self.assertNotIn("features",data)
                    self.assertIsNone(data["signal_id"])
                    self.assertEqual(data["score_status"],"SCORE_UNAVAILABLE")
                    self.assertEqual(data["measurements"]["physical_http_attempts"],6)
                    if mode=="quote_delta":
                        self.assertIn("QUOTE_VOLUME_AGGREGATION_MISMATCH",
                                      data["reconciliation"]["reason_codes"])

    def test_real_source_sha_cannot_be_confused_with_publication(self):
        data=self.run_fake()
        self.assertEqual(len(data["source_payload_sha256"]),64)
        self.assertGreater(datetime.fromisoformat(data["retrieved_at"]),
                           datetime.fromisoformat(data["parent_close_at"]))
        self.assertEqual(data["retrospective_assumption"],RETROSPECTIVE_EVIDENCE)
        self.assertTrue(data["evidence_sha256"])
        self.assertIsNone(data["measurements"]["true_clock_uncertainty_ms"])
        self.assertEqual(data["measurements"]["http_attempt_budget"],8)
        self.assertIsNone(data["historical_eligibility"])

    def test_future_parent_stops_after_time_only(self):
        fake=FakeBinance()
        fake.mode="future_parent"
        result=self.run_fake(fake=fake)
        self.assertEqual(result["status"],"FAIL")
        self.assertIn("FUTURE_PARENT_WINDOW",result["reason"])
        self.assertEqual(result["measurements"]["physical_http_attempts"],1)

    def test_bad_session_and_no_live_opt_in(self):
        with self.assertRaisesRegex(ValueError,"SESSION_NOT_IN"):
            self.run_fake("DOGEUSDT")
        with patch("sys.stderr",new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as cm:
                main(["--symbol","BTCUSDT","--horizon","SWING",
                      "--partition","HOLDOUT"])
        self.assertEqual(cm.exception.code,2)

    def test_retry_physical_attempt_stop_at_eight(self):
        fake=FakeBinance()
        fake.attempt_extra=2
        result=self.run_fake(fake=fake)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(fake.actual_attempts,8)
        self.assertEqual(result["measurements"]["physical_http_attempts"],8)
        self.assertIn("ATTEMPT_BUDGET_EXHAUSTED",result["reason"])
        self.assertLess(result["measurements"]["successful_calls"],6)

    def test_pre_attempt_guard_before_network(self):
        fake=FakeBinance()
        times=iter([0,61,61,61,61])
        result=self.run_fake(fake=fake,monotonic=lambda:next(times))
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(fake.actual_attempts,0)
        self.assertIn("SOFT_PRE_REQUEST_GUARD",result["reason"])

    def test_wrong_symbol_or_ineligible_today_fails_closed(self):
        fake=FakeBinance("ETHUSDT")
        d=self.run_fake("BTCUSDT",fake=fake)
        self.assertEqual(d["status"],"FAIL")
        self.assertIn("WRONG_SPOT_SYMBOL",d["reason"])
        class Ineligible(FakeBinance):
            def __call__(self,path,params=None,*,on_attempt=None):
                row,meta=super().__call__(path,params,on_attempt=on_attempt)
                if path=="/api/v3/ticker/24hr":
                    row["quoteVolume"]="1000"
                return row,meta
        d=self.run_fake(fake=Ineligible())
        self.assertEqual(d["status"],"FAIL")
        self.assertIn("CURRENT_MARKET_INELIGIBLE",d["reason"])
        self.assertEqual(d["measurements"]["physical_http_attempts"],4)


class FeatureAndStudyTests(unittest.TestCase):
    def sample(self):
        now=NOW
        start=datetime(2026,10,14,7,30,tzinfo=UTC)
        children=[]
        for i in range(6):
            t=start+timedelta(minutes=i*5)
            children.append(CandleWindow("5m",t,t+timedelta(minutes=5),
                now,now,MANIFEST.provider_source,
                "100","102","99","101","10","1000"))
        parent=CandleWindow("30m",start,start+timedelta(minutes=30),
                            now,now,MANIFEST.provider_source,
                            "100","102","99","101","60","6000")
        return parent,children

    def test_signed_up_down_and_gap_aware_comparison(self):
        p,cs=self.sample()
        up=competing_features(p,cs,direction=Direction.UP,decision_at=NOW)
        down=competing_features(p,cs,direction=Direction.DOWN,decision_at=NOW)
        self.assertEqual(Decimal(up["SIGNED_BODY_RANGE"]["value"]),
                         -Decimal(down["SIGNED_BODY_RANGE"]["value"]))
        self.assertEqual(Decimal(up["NET_OVER_GAP_AWARE_PATH"]["value"]),
                         -Decimal(down["NET_OVER_GAP_AWARE_PATH"]["value"]))
        self.assertEqual(Decimal(up["NET_OVER_BODY_PATH"]["value"]),Decimal("1")/6)
        self.assertEqual(Decimal(up["NET_OVER_GAP_AWARE_PATH"]["value"]),1)
        self.assertEqual(up["SECOND_HALF_BASE_SHARE"]["value"],"0.5")
        self.assertEqual(up["SECOND_HALF_QUOTE_SHARE"]["value"],"0.5")
        self.assertEqual(up["BASELINE_SIGNED_OC_PCT"]["value"],"1")
        self.assertTrue(all(m["status"]=="RESEARCH_METRIC_UNAPPROVED" for m in up.values()))
        self.assertTrue(all("score" not in m for m in up.values()))

    def test_zero_division_explicit_missing_and_source_future_rejected(self):
        p,cs=self.sample()
        p=dataclasses.replace(p,open=Decimal("100"),close=Decimal("100"),
                              low=Decimal("100"),high=Decimal("100"))
        cs=[dataclasses.replace(c,open=Decimal("100"),close=Decimal("100"),
                                high=Decimal("100"),low=Decimal("100"),
                                base_volume=Decimal(0),quote_volume=Decimal(0)) for c in cs]
        result=competing_features(p,cs,direction=Direction.DOWN,decision_at=NOW)
        for key in ("NET_OVER_GAP_AWARE_PATH","SECOND_HALF_BASE_SHARE",
                    "SECOND_HALF_QUOTE_SHARE","FAVORABLE_BASE_SHARE",
                    "FAVORABLE_QUOTE_SHARE","DIRECTIONAL_CLOSE_LOCATION"):
            self.assertIsNone(result[key]["value"])
            self.assertEqual(result[key]["missing_reason"],"ZERO_DENOMINATOR")
        with self.assertRaisesRegex(ValueError,"RESEARCH_FEATURE_PIT_INPUT_INVALID"):
            competing_features(p,[dataclasses.replace(cs[0],available_at=NOW+timedelta(seconds=1)),
                                  *cs[1:]],direction=Direction.UP,decision_at=NOW)
        with self.assertRaisesRegex(ValueError,"RESEARCH_FEATURE_PIT_INPUT_INVALID"):
            competing_features(p,[dataclasses.replace(cs[0],source_id="FORGED"),
                                  *cs[1:]],direction=Direction.UP,decision_at=NOW)

    def test_record_tampering_and_holdout_time_leakage_refused(self):
        s=run_session(symbol="BTCUSDT",horizon=Horizon.INTRADAY,
             partition=Partition.DEVELOPMENT,getter=FakeBinance(),
             clock_ms=lambda:NOW_MS)
        bad=dict(s)
        bad["status"]="OBSERVED_WIN"
        with self.assertRaisesRegex(ValueError,"STUDY_EVIDENCE_TAMPER"):
            compare_study([bad])
        changed=seal_record({**s,"partition":"HOLDOUT","parent_close_at":s["parent_close_at"]})
        with self.assertRaisesRegex(ValueError,"STUDY_SESSION_OR_TIME_SPLIT"):
            compare_study([changed])
        fake=seal_record({**s,"source_publication_at":s["retrieved_at"]})
        with self.assertRaisesRegex(ValueError,"FABRICATED_HISTORICAL_SOURCE"):
            compare_study([fake])
        wrong=seal_record({**s,"study_id":"STUDY-OTHER"})
        with self.assertRaisesRegex(ValueError,"STUDY_MANIFEST_MISMATCH"):
            compare_study([wrong])
        with self.assertRaisesRegex(ValueError,"DUPLICATE_FROZEN"):
            compare_study([s,s])

    def test_partial_coverage_is_not_extrapolated(self):
        s=run_session(symbol="BTCUSDT",horizon=Horizon.SWING,
                      partition=Partition.DEVELOPMENT,
                      getter=FakeBinance(horizon=Horizon.SWING),
                      clock_ms=lambda:NOW_MS)
        summary=compare_study([s])
        self.assertEqual(summary["observed_sessions"],1)
        self.assertEqual(summary["failed_or_missing_sessions"],11)
        self.assertEqual(summary["status"],"INSUFFICIENT_EVIDENCE")
        self.assertIsNone(summary["forward_outcomes"])
        self.assertIsNone(summary["fees"])


if __name__=="__main__":
    unittest.main()
