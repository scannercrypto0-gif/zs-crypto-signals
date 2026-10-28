"""03B3 scheduled batch safety: deterministic clock + network-free source E2E."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zs_smart_gate.stage03b3_manifest import MANIFEST
from zs_smart_gate.stage03b2_manifest import MANIFEST as PREVIOUS_STUDY
from zs_smart_gate.stage03b3_auto import (
    DAY, PER_BATCH_MAX, SCHEDULE, emit_artifacts, main, resolve_schedule,
    run_batch,
)

UTC = timezone.utc
EXPECTED_STUDY = "PROSPECTIVE-SHA256-6db82e807757262a7b1a54b4f533c5c1e155aa968ec2aafdb3d9d8cabc8a4422"
OLD_STUDY = "STUDY-SHA256-d5e70d796516f68e00e2c132f09f4201a65942189727c9e00a1a451ec9ec4f62"


class FakePublicBinance:
    def __init__(self, slot, now_ms=None, ineligible=(), crash=()):
        self.slot = slot
        self.now_ms = int(slot.close_at.timestamp()*1000) + 5000 if now_ms is None else now_ms
        self.ineligible = set(ineligible)
        self.crash = set(crash)
        self.symbol = None
        self.requests = []
        self.actual_physical = 0
        self.after_first = False

    def clock(self):
        return self.now_ms

    def __call__(self, path, params=None, *, on_attempt=None):
        if params and "symbol" in params:
            self.symbol = params["symbol"]
        # All "real" fake physical attempts only after accepted hook.
        on_attempt(path)
        self.actual_physical += 1
        self.requests.append((self.symbol,path,params))
        if self.symbol in self.crash and path == "/api/v3/ticker/24hr":
            raise RuntimeError("TEST_TRANSPORT_FAILURE")
        at = self.now_ms + self.actual_physical
        meta = {
            "path":path,"t0_local_ms":at-50,"received_local_ms":at,
            "http_status":200,"latency_ms":50,"used_weight_1m":"4",
        }
        if path == "/api/v3/time":
            return {"serverTime":self.now_ms},meta
        if path == "/api/v3/exchangeInfo":
            return {"symbols":[{
                "symbol":self.symbol,"status":"TRADING","quoteAsset":"USDT",
                "isSpotTradingAllowed":True}]},meta
        if path == "/api/v3/ticker/24hr":
            return {"symbol":self.symbol,
                    "quoteVolume":"1000" if self.symbol in self.ineligible
                    else "50000000"},meta
        if path == "/api/v3/ticker/bookTicker":
            return {"symbol":self.symbol,"bidPrice":"100","askPrice":"100.01"},meta
        if path != "/api/v3/klines":
            raise AssertionError("UNAUTHORIZED_ENDPOINT")
        duration={"30m":1800000,"5m":300000,"4h":14400000,"1h":3600000}[params["interval"]]
        count=int(params["limit"])
        start=int(params["startTime"])
        raw=[[start+i*duration,"100","102","99","101","10",
              start+(i+1)*duration-1,"1000",12,"5","500","0"]
             for i in range(count)]
        if params["interval"] in ("30m","4h"):
            n=6 if params["interval"]=="30m" else 4
            raw[0][5]=str(n*10)
            raw[0][7]=str(n*1000)
        return raw,meta


class AutoScheduleTests(unittest.TestCase):
    def batch(self, idx=0, *, seconds=5, fake=None):
        cron,label,horizon=SCHEDULE[idx]
        slot=MANIFEST.slot("BTCUSDT",horizon,label)
        if fake is None:
            fake=FakePublicBinance(slot)
        instant=slot.close_at+timedelta(seconds=seconds)
        return run_batch(cron=cron,now=instant,getter=fake,clock_ms=fake.clock), fake

    def test_four_exact_utc_crons_and_same_unchanged_protocol(self):
        self.assertEqual([x[0] for x in SCHEDULE],[
            "1 14 28 10 *","31 14 28 10 *",
            "1 16 28 10 *","1 20 28 10 *"])
        self.assertEqual([x[1] for x in SCHEDULE],["I1","I2","S1","S2"])
        self.assertEqual(DAY,(2026,10,28))
        for cron,label,horizon in SCHEDULE:
            self.assertEqual(resolve_schedule(cron),(label,horizon))
        self.assertEqual(MANIFEST.study_id,EXPECTED_STUDY)
        self.assertEqual(PREVIOUS_STUDY.study_id,OLD_STUDY)
        self.assertEqual(MANIFEST.assets,("BTCUSDT","ETHUSDT","AAVEUSDT"))
        self.assertEqual(MANIFEST.planned_observations,12)
        self.assertEqual(PER_BATCH_MAX,24)
        with self.assertRaisesRegex(ValueError,"UNKNOWN_SCHEDULE"):
            resolve_schedule("1 14 29 10 *")
        with self.assertRaisesRegex(ValueError,"UNKNOWN_SCHEDULE"):
            resolve_schedule("1 14 28 10 3")
        with self.assertRaisesRegex(ValueError,"UNKNOWN_SCHEDULE"):
            resolve_schedule(None)

    def test_wrong_year_and_dates_never_get_network(self):
        cron,label,h= SCHEDULE[0]
        for instant in (datetime(2025,10,28,14,1,tzinfo=UTC),
                        datetime(2027,10,28,14,1,tzinfo=UTC),
                        datetime(2026,11,28,14,1,tzinfo=UTC),
                        datetime(2026,10,29,14,1,tzinfo=UTC)):
            def forbidden(*args,**kwargs):
                raise AssertionError("NO_BINANCE_GET_ON_WRONG_DATE")
            batch=run_batch(cron=cron,now=instant,getter=forbidden)
            self.assertEqual(len(batch["rows"]),3)
            self.assertTrue(all(x["telemetry"]["physical_http_attempts"]==0
                                for x in batch["rows"]))
            self.assertTrue(all(x["status"] in ("LATE","NOT_ATTEMPTED")
                                for x in batch["rows"]))
            self.assertEqual(batch["http_attempts"],0)
            self.assertEqual(batch["study_id"],EXPECTED_STUDY)

    def test_wrong_actual_time_before_declared_parent_never_get(self):
        for idx in range(4):
            cron,label,h=SCHEDULE[idx]
            slot=MANIFEST.slot("BTCUSDT",h,label)
            batch=run_batch(cron=cron,now=slot.close_at-timedelta(seconds=1),
                            getter=lambda *a,**k: self.fail("BEFORE_CLOSE_HTTP"))
            self.assertEqual(batch["states"],dict.fromkeys(MANIFEST.assets,"NOT_ATTEMPTED"))
            self.assertEqual(batch["http_attempts"],0)

    def test_late_scheduler_strict_600_seconds_and_no_retro_fetch(self):
        for idx in range(4):
            cron,label,h=SCHEDULE[idx]
            slot=MANIFEST.slot("BTCUSDT",h,label)
            batch=run_batch(cron=cron,
                now=slot.close_at+timedelta(seconds=601),
                getter=lambda *a,**k:self.fail("LATE_RETROSPECTIVE_HTTP"))
            self.assertEqual(batch["states"],dict.fromkeys(MANIFEST.assets,"LATE"))
            self.assertEqual(batch["http_attempts"],0)
            self.assertEqual(batch["audit"]["observed_pit"],0)

    def test_all_four_frozen_horizons_three_symbols_true_fixture_e2e(self):
        for idx in range(4):
            batch,fake=self.batch(idx)
            self.assertEqual(batch["states"],dict.fromkeys(MANIFEST.assets,"OBSERVED_PIT"),batch["states"])
            self.assertEqual(len(batch["rows"]),3)
            self.assertEqual(fake.actual_physical,18)
            self.assertEqual(batch["http_attempts"],18)
            self.assertEqual(batch["audit"]["observed_pit"],3)
            self.assertLessEqual(batch["http_attempts"],PER_BATCH_MAX)
            self.assertEqual(len(set(x["symbol"] for x in batch["rows"])),3)
            for row in batch["rows"]:
                self.assertIsNone(row["score"])
                self.assertIsNone(row["signal_id"])
                self.assertEqual(row["score_status"],"SCORE_UNAVAILABLE")
                self.assertEqual(row["trade_plan_status"],"RESEARCH_ONLY")
                self.assertFalse(row["qualified_signal"])
                self.assertEqual(row["reconciliation"]["status"],"PASS")
                self.assertTrue(all(Decimal(v)==0 for v in row["deltas"].values()))
                self.assertIsNone(row["source_publication_at"])
                self.assertEqual(row["telemetry"]["physical_http_attempts"],6)
                self.assertIsNone(row["forward_outcome"])
                self.assertEqual(row["source_payload_sha256"].__len__(),64)

    def test_one_ineligible_not_erase_other_two_sealed_rows(self):
        cron,label,h=SCHEDULE[2]
        slot=MANIFEST.slot("BTCUSDT",h,label)
        fake=FakePublicBinance(slot,ineligible={"ETHUSDT"})
        result,_=self.batch(2,fake=fake)
        self.assertEqual(result["states"],{
            "BTCUSDT":"OBSERVED_PIT","ETHUSDT":"INELIGIBLE",
            "AAVEUSDT":"OBSERVED_PIT"})
        self.assertEqual(result["http_attempts"],16)
        self.assertEqual(result["audit"]["observed_pit"],2)
        self.assertEqual(result["audit"]["statuses"]["INELIGIBLE"],1)
        self.assertEqual(len(result["rows"]),3)
        self.assertTrue(all("evidence_sha256" in r for r in result["rows"]))

    def test_unexpected_per_symbol_failure_records_actual_physical_attempts(self):
        cron,label,h=SCHEDULE[0]
        slot=MANIFEST.slot("BTCUSDT",h,label)
        fake=FakePublicBinance(slot,crash={"ETHUSDT"})
        batch,_=self.batch(fake=fake)
        self.assertEqual(batch["states"]["ETHUSDT"],"FAILED")
        self.assertEqual(batch["states"]["AAVEUSDT"],"OBSERVED_PIT")
        self.assertEqual(batch["states"]["BTCUSDT"],"OBSERVED_PIT")
        self.assertEqual(batch["http_attempts"],fake.actual_physical)
        self.assertEqual(batch["rows"][1]["telemetry"]["physical_http_attempts"],3)
        self.assertEqual(batch["http_attempts"],15)
        self.assertTrue(batch["rows"][1]["reason"].startswith("UNEXPECTED_CAPTURE_ERROR_"))

    def test_capture_window_can_expire_mid_batch(self):
        cron,label,h=SCHEDULE[0]
        slot=MANIFEST.slot("BTCUSDT",h,label)
        fake=FakePublicBinance(slot)
        original=fake.__call__
        class Jump:
            def __call__(self,path,params=None,*,on_attempt=None):
                response=original(path,params,on_attempt=on_attempt)
                if path=="/api/v3/klines" and params["interval"]=="5m" and fake.symbol=="BTCUSDT":
                    fake.now_ms=int(slot.close_at.timestamp()*1000)+601000
                return response
        batch=run_batch(cron=cron,now=slot.close_at+timedelta(seconds=5),
                        getter=Jump(),clock_ms=fake.clock)
        self.assertEqual(batch["states"]["BTCUSDT"],"LATE")
        self.assertEqual(batch["states"]["ETHUSDT"],"LATE")
        self.assertEqual(batch["states"]["AAVEUSDT"],"LATE")
        self.assertEqual(batch["http_attempts"],6)

    def test_per_symbol_attempt_guard_retries_eighth_blocks_ninth(self):
        cron,label,h=SCHEDULE[0]
        slot=MANIFEST.slot("BTCUSDT",h,label)
        fake=FakePublicBinance(slot)
        class Retrier:
            def __call__(self,path,params=None,*,on_attempt):
                # Three extras to simulate retries, each accepted attempt
                for _ in range(3):
                    on_attempt(path)
                    fake.actual_physical+=1
                return fake(path,params,on_attempt=on_attempt)
        batch=run_batch(cron=cron,now=slot.close_at+timedelta(seconds=5),
                        getter=Retrier(),clock_ms=fake.clock)
        self.assertEqual(len(batch["rows"]),3)
        self.assertEqual(batch["http_attempts"],24)
        self.assertTrue(all(x["telemetry"]["physical_http_attempts"]==8
                            for x in batch["rows"]))
        self.assertTrue(all(x["status"]=="FAILED" for x in batch["rows"]))

    def test_exclusive_artifact_per_asset_and_no_overwrite(self):
        batch,_=self.batch()
        with tempfile.TemporaryDirectory() as root:
            folder=os.path.join(root,"one-shot")
            emit_artifacts(batch,folder)
            self.assertEqual(len(list(Path(folder).glob("*.json"))),4)
            for symbol in MANIFEST.assets:
                content=json.loads((Path(folder)/f"{symbol}_I1.json").read_text())
                self.assertEqual(content["symbol"],symbol)
                self.assertEqual(content["study_id"],MANIFEST.study_id)
            with self.assertRaises(FileExistsError):
                emit_artifacts(batch,folder)

    def test_invalid_schedule_rejected_before_any_transport(self):
        with self.assertRaisesRegex(ValueError,"UNKNOWN_SCHEDULE"):
            run_batch(cron="* * * * *",getter=lambda *a,**kw:self.fail("NETWORK"))

    def test_capture_cli_refuses_any_manual_dispatch_or_rerun(self):
        for environ in (
            {"GITHUB_EVENT_NAME":"workflow_dispatch",
             "GITHUB_REF":"refs/heads/main","GITHUB_RUN_ATTEMPT":"1"},
            {"GITHUB_EVENT_NAME":"schedule",
             "GITHUB_REF":"refs/heads/main","GITHUB_RUN_ATTEMPT":"2"},
            {"GITHUB_EVENT_NAME":"schedule",
             "GITHUB_REF":"refs/heads/develop","GITHUB_RUN_ATTEMPT":"1"}
        ):
            with patch.dict(os.environ,environ,clear=True):
                with patch("sys.stderr",new_callable=io.StringIO):
                    with self.assertRaises(SystemExit) as ctx:
                        main(["--scheduled","--cron",SCHEDULE[0][0],"--output-dir","not-created"])
            self.assertEqual(ctx.exception.code,2)

    def test_workflow_crons_main_only_no_rerun_and_cleanup_required(self):
        workflow=(Path(__file__).resolve().parent.parent/
                  ".github/workflows/stage03b3-auto.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("- cron:"),4)
        for expr,_,_ in SCHEDULE:
            self.assertIn("cron: '"+expr+"'",workflow)
        self.assertIn("github.run_attempt == 1",workflow)
        self.assertIn("github.ref == 'refs/heads/main'",workflow)
        self.assertIn("cancel-in-progress: false",workflow)
        self.assertNotIn("workflow_dispatch:",workflow)
        self.assertNotIn("push:\n",workflow)
        self.assertIn("retention-days: 7",workflow)
        self.assertIn("PM must DELETE the schedule",workflow)


if __name__=="__main__":
    unittest.main()
