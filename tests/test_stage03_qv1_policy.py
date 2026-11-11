from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from test_stage03_qv1_intraday_up import sample
from test_stage51_material import bind
from zs_smart_gate.stage03_qv1_intraday_up import inputs_sha256
from zs_smart_gate.stage03_qv1_policy import Policy, evaluate_and_store, verify_clock
from zs_smart_gate.stage05_contracts import ContractError, canonical, digest, parse_utc
from zs_smart_gate.stage05_custody import LocalOutbox


def stamp(dt):
    return dt.isoformat().replace("+00:00", "Z")


def evidence(data):
    row = data.evidence
    src = row["source"]
    market = data.market
    src["joined_inputs_sha256"] = inputs_sha256(data)
    quote = src["liquidity"]
    quote.update(book_symbol=market.symbol, ticker_symbol=market.symbol,
                 quote_asset=market.quote_asset, window="ROLLING_24H",
                 bid=str(market.bid), ask=str(market.ask), quote_volume=str(market.quote_volume_24h))
    for kind in ("book", "ticker"):
        for field in ("observed_at", "received_at", "available_at"):
            quote[kind + "_" + field] = stamp(market.observed_at)
    bind(row)
    t = stamp(data.received_at)
    return dict(identity="FIXTURE_INDEPENDENT", calibration_ref="FIXTURE", method="FIXTURE_INTERVAL",
                source_sha256=row["source_sha256"], decision_at=row["decision_at"],
                measured_at=t, received_at=t, available_at=t, offset_us=0, uncertainty_us=10, drift_ppm=1)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.tmp.cleanup)
        self.policy = Policy("SYNTHETIC_TEST_ONLY","SYNTHETIC_TEST_ONLY","0.925",100,2000000)

    def run_case(self,data,*,policy=None, witness=True, name="db"):
        p = policy or self.policy
        proof = evidence(data) if witness else None
        return evaluate_and_store(data, LocalOutbox(Path(self.tmp.name)/name),
                                  policy=p, expected_sha=p.sha256, witness=proof,
                                  witness_pin=digest(canonical(proof)) if proof else None)

    def test_fixture_pass_reopen_scoreless_and_fail(self):
        data = sample()
        first = self.run_case(data)
        self.assertEqual(first["qualification_state"],"QUALIFIED")
        self.assertTrue(first["signal_id"].startswith("fixture-sig-"))
        self.assertIsNone(first["score"])
        self.assertEqual(first,self.run_case(data))
        failed = self.run_case(sample(),policy=replace(self.policy,n01_min="0.926"),name="fail")
        self.assertEqual(failed["gates"]["N01"],"FAIL")
        self.assertEqual(failed["qualification_state"],"REJECTED")
        market = replace(data.market, quote_volume_24h="9999999")
        thin = self.run_case(replace(data,market=market),name="thin")
        self.assertEqual(thin["gates"]["LIQUIDITY"],"FAIL")
        self.assertIsNone(thin["signal_id"])

    def test_market_and_context_boundary_and_absence(self):
        data=sample()
        stale=replace(data.context[0],open_at=data.context[0].open_at-timedelta(hours=1),
                      close_at=data.context[0].close_at-timedelta(hours=1))
        frame=data.evidence["candles"]["1h"]
        frame.update(open_at=stamp(stale.open_at),close_at=stamp(stale.close_at))
        out=self.run_case(replace(data,context=(stale,data.context[1])))
        self.assertEqual(out["gates"]["CONTEXT"],"UNKNOWN")
        data=sample()
        for delta in ("0.01","-0.01"):
            parent=replace(data.parent,quote_volume=data.parent.quote_volume+Decimal(delta))
            out=self.run_case(replace(data,parent=parent),name=delta)
            self.assertEqual(out["gates"]["EXACT_RECONCILIATION"],"UNKNOWN")
        self.assertEqual(self.run_case(sample(),witness=False,name="missing")["gates"]["UTC_WITNESS"],"UNKNOWN")

    def test_clock_bounds_tampering_and_future(self):
        data=sample()
        w=evidence(data)
        decision=parse_utc(data.evidence["decision_at"])
        def verify():
            return verify_clock(w,digest(canonical(w)),data.evidence["source_sha256"],
                                decision,data.received_at,self.policy)
        self.assertEqual(verify(),"PASS")
        with self.assertRaisesRegex(ContractError,"DIGEST"):
            verify_clock(w,"0"*64,data.evidence["source_sha256"],decision,data.received_at,self.policy)
        w["uncertainty_us"]=100
        self.assertEqual(verify(),"UNKNOWN") # drift crosses the bound
        w["available_at"]=stamp(decision+timedelta(seconds=1))
        with self.assertRaisesRegex(ContractError,"FUTURE"):
            verify()

    def test_absent_unapproved_and_mismatched_policy(self):
        data=sample()
        store=LocalOutbox(Path(self.tmp.name)/"hold")
        self.assertEqual(evaluate_and_store(data,store)["qualification_state"],"UNKNOWN")
        with self.assertRaisesRegex(ContractError,"SHA_MISMATCH"):
            evaluate_and_store(data,store,policy=self.policy,expected_sha="0"*64)
        data.evidence["source_scope"]="APPROVED_REAL_SOURCE"
        data.evidence["source"]["scope"]="APPROVED_REAL_SOURCE"
        real=replace(self.policy,scope="APPROVED_REAL_SOURCE",authority="SELF_DECLARED")
        result=self.run_case(data,policy=real,name="real")
        self.assertEqual(result["qualification_state"],"UNKNOWN")
        self.assertIsNone(result["signal_id"])
