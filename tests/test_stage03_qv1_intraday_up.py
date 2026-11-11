from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from test_stage51_material import fixture, bind
from test_stage03_qv1_boundary import bound
from zs_smart_gate.core import MarketSnapshot
from zs_smart_gate.mtf_contracts import CandleWindow, ReconciliationTolerance
from zs_smart_gate.stage03_qv1_intraday_up import Inputs, POLICY_SHA256, evaluate_up, inputs_sha256, persist_up
from zs_smart_gate.stage05_contracts import ContractError, parse_utc
from zs_smart_gate.stage05_custody import LocalOutbox


def sample(*, close_price="103", volume="1200", stale=False, missing_context=False):
    row = fixture()
    close = parse_utc(row["event_close_at"])
    recv = close + timedelta(seconds=1)
    decision = recv + timedelta(seconds=91 if stale else 1)
    row["decision_at"] = decision.isoformat().replace("+00:00", "Z")
    row["candles"]["5m"].update(received_at=recv.isoformat().replace("+00:00","Z"),
                               available_at=recv.isoformat().replace("+00:00","Z"))
    raw = []
    for i in range(22):
        opened = int(close.timestamp()*1000) - (22-i)*300000
        raw.append([opened,"100","102","99","101","10",opened+299999,"1000",10,"5","500","0"])
    raw[-1][2:5] = ["103","99",close_price]
    raw[-1][7] = volume
    row = bound(row, {})
    def window(frame, high="102", end="101", base="10", quote="1000"):
        bar = row["candles"][frame]
        return CandleWindow(frame, *(parse_utc(bar[k]) for k in ("open_at","close_at","received_at","available_at")),
                            row["source"]["feed"], "100",high,"99",end,base,quote)
    parent = window("30m","103",close_price,"60",str(5000+int(volume)))
    context = () if missing_context else (window("1h"),window("4h"))
    market = MarketSnapshot("BTCUSDT","USDT",True,"TRADING","300000000","100.99","101.00",recv)
    data = Inputs(row,raw,market,parent,context,ReconciliationTolerance(0,0,0,"SYNTHETIC_EXACT"),recv)
    row["source"]["joined_inputs_sha256"] = inputs_sha256(data)
    bind(row)
    return data


class IntradayUpTests(unittest.TestCase):
    def test_real_detector_threshold_and_closed_join(self):
        for price, volume, state in (("103","1200","DETECTED_SIGNAL"),("102","1200","RESEARCH_CANDIDATE"),
                                     ("103","1199","RESEARCH_CANDIDATE")):
            with self.subTest(price=price, volume=volume):
                out = evaluate_up(sample(close_price=price,volume=volume), policy_sha256=POLICY_SHA256)
                self.assertEqual(out["reconciliation"],"PASS")
                self.assertEqual(out["state"],state)
                self.assertEqual(out["qualification_state"],"UNKNOWN")
                self.assertIsNone(out["signal_id"])

    def test_stale_missing_context_wrong_policy_and_tampering(self):
        self.assertEqual(evaluate_up(sample(stale=True),policy_sha256=POLICY_SHA256)["setup_reason"],"STALE_OBSERVATION")
        self.assertEqual(evaluate_up(sample(missing_context=True),policy_sha256=POLICY_SHA256)["state"],"UNKNOWN")
        data=sample()
        with self.assertRaisesRegex(ContractError,"POLICY_FINGERPRINT"):
            evaluate_up(data,policy_sha256="0"*64)
        with self.assertRaisesRegex(ContractError,"JOINED_INPUT_HASH"):
            evaluate_up(replace(data,klines=data.klines[:-1]),policy_sha256=POLICY_SHA256)

    def test_stable_sqlite_readback_without_qualification(self):
        data=sample()
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            p=Path(temp)/"q.sqlite"
            result=persist_up(data,LocalOutbox(p),policy_sha256=POLICY_SHA256)
            self.assertEqual(result,persist_up(data,LocalOutbox(p),policy_sha256=POLICY_SHA256))
            self.assertIsNone(result["signal_id"])

    def test_research_market_fail_unknown_and_pass_cannot_qualify(self):
        from test_stage51_material import bind
        for bid, volume, gate in (("100.99", "10000000", "PASS"),
                                  ("100.99", "9999999", "FAIL"),
                                  ("100.00", "300000000", "FAIL"),
                                  ("0", "300000000", "UNKNOWN")):
            with self.subTest(bid=bid, volume=volume):
                data = sample()
                data = replace(data, market=replace(data.market, bid=bid, quote_volume_24h=volume))
                data.evidence["source"]["joined_inputs_sha256"] = inputs_sha256(data)
                bind(data.evidence)
                result = evaluate_up(data, policy_sha256=POLICY_SHA256)
                self.assertEqual(result["research_market_gate"], gate)
                self.assertEqual(result["qualification_state"], "UNKNOWN")
                self.assertIsNone(result["signal_id"])
