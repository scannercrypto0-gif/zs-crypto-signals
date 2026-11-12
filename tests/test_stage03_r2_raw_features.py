"""R2 targeted raw-feature vectors only. Execute on owner Windows, not CI."""
import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import tempfile

from test_stage03_r1_closed_parent import CLOSE, DECISION, T, fixture, window
from zs_smart_gate.stage03_r0_identity import DiscoveryReference
from zs_smart_gate.stage03_r1_closed_parent import persist_local_research
from zs_smart_gate.stage03_r2_raw_features import (
    VERSION, evaluate_raw_research_batch, persist_raw_feature_snapshot,
)
from zs_smart_gate.stage05_contracts import ContractError
from zs_smart_gate.stage05_custody import LocalOutbox


def with_history(item, count=20, *, zero=False):
    history = []
    for i in range(count):
        opened = T-timedelta(minutes=30*(count-i))
        history.append(window("30m",opened,"100","102","99","101",
                              "0" if zero else "10", "0" if zero else "1000"))
    return replace(item, previous_30m=tuple(history))


class TestR2RawFeatures(unittest.TestCase):
    def one(self, item):
        return evaluate_raw_research_batch((item,),closed_at=CLOSE,decision_at=DECISION)[0]

    def test_f01_without_setup_strong_30m_raw_fields_no_qualification(self):
        row = self.one(fixture(discovery=DiscoveryReference("NO_BREAKOUT")))
        self.assertEqual(row["evaluation_status"], "POLICY_HOLD")
        f = row["raw_features"]
        self.assertEqual(f["closing_location"]["raw_value"],"0.875")
        self.assertEqual(f["body_to_range"]["raw_value"],"0.75")
        self.assertEqual(f["upper_wick_to_range"]["raw_value"],"0.125")
        self.assertEqual(f["lower_wick_to_range"]["raw_value"],"0.125")
        self.assertEqual(f["child_close_deltas"]["raw_value"],["1"]*6)
        self.assertEqual(f["child_base_volumes"]["raw_value"],["10"]*6)
        self.assertEqual(f["child_quote_volumes"]["raw_value"],["1000"]*6)
        self.assertEqual(f["net_price_move"]["raw_value"],"6")
        self.assertEqual(f["net_to_path_efficiency"]["raw_value"],"1")
        self.assertEqual(f["gain_retention"]["raw_value"],str(Decimal(6)/Decimal(7)))
        self.assertIsNone(row["signal_id"])
        self.assertFalse(row["publishable"])
        self.assertEqual(row["qualification_state"],"UNKNOWN")
        self.assertEqual(row["raw_feature_schema"],VERSION)

    def test_f02_5m_discovery_with_weak_30m_does_not_qualify(self):
        row=self.one(fixture(weak=True,discovery=DiscoveryReference("DETECTED_SETUP")))
        self.assertEqual(row["evaluation_status"],"POLICY_HOLD")
        self.assertEqual(row["raw_features"]["closing_location"]["raw_value"],"0.125")
        self.assertEqual(row["raw_features"]["signed_body_to_range"]["raw_value"],"-0.75")
        self.assertEqual(row["raw_features"]["net_to_path_efficiency"]["raw_value"],"-1")
        self.assertIsNone(row["signal_id"])
        self.assertEqual(row["score_status"],"SCORE_UNAVAILABLE")

    def test_rvol_prior_20_30m_base_quote_no_threshold(self):
        row=self.one(with_history(fixture()))
        f=row["raw_features"]
        self.assertEqual(f["rvol_base_20"]["raw_value"],"6")
        self.assertEqual(f["rvol_quote_20"]["raw_value"],"6")
        self.assertEqual(f["rvol_base_20"]["gate_result"],"NOT_EVALUATED")
        row=self.one(fixture())
        self.assertEqual(row["raw_features"]["rvol_base_20"]["availability"],
                         "INSUFFICIENT_HISTORY")
        zero=self.one(with_history(fixture(),zero=True))
        self.assertEqual(zero["raw_features"]["rvol_quote_20"]["availability"],"UNKNOWN")

    def test_history_gap_or_future_is_not_filled_or_scored(self):
        good=with_history(fixture())
        gap=replace(good.previous_30m[10],open_at=good.previous_30m[10].open_at+
                    timedelta(minutes=30),close_at=good.previous_30m[10].close_at+
                    timedelta(minutes=30))
        for source in (
            replace(good,previous_30m=good.previous_30m[:10]+(gap,)+good.previous_30m[11:]),
            replace(good,previous_30m=good.previous_30m[:10]+
                    (replace(good.previous_30m[10], available_at=DECISION+timedelta(seconds=1)),)+
                    good.previous_30m[11:]),
        ):
            row=self.one(source)
            self.assertEqual(row["raw_features"]["rvol_base_20"]["availability"],"UNKNOWN")

    def test_context_and_no_unapproved_n03_sem_or_probability(self):
        row=self.one(fixture())
        f=row["raw_features"]
        self.assertEqual(f["1h_directional_change_pct"]["availability"],"PRESENT")
        self.assertEqual(f["4h_closed_age_seconds"]["availability"],"PRESENT")
        for key in ("volatility_normalized_move", "n03_r2_numeric_normalizer",
                    "SEM_I_01","SEM_I_02","SEM_S_01","SEM_S_02"):
            self.assertEqual(f[key]["availability"],"NOT_IMPLEMENTED")
            self.assertIsNone(f[key]["raw_value"])
        self.assertIsNone(row["score"])
        self.assertIsNone(row["trade_plan"])

    def test_separate_versioned_sqlite_readback_and_no_v1_rewrite(self):
        item=with_history(fixture())
        r1 = __import__("zs_smart_gate.stage03_r1_closed_parent",
                        fromlist=["evaluate_local_universe"]).evaluate_local_universe(
                            (item,),closed_at=CLOSE,decision_at=DECISION)[0]
        r2=self.one(item)
        with tempfile.TemporaryDirectory() as folder:
            store=LocalOutbox(Path(folder)/"r2.sqlite")
            legacy=persist_local_research(store,r1)
            receipt=persist_raw_feature_snapshot(store,r2)
            self.assertEqual(receipt,persist_raw_feature_snapshot(LocalOutbox(store.path),r2))
            self.assertNotEqual(legacy["record_key"],receipt["record_key"])
            self.assertEqual(legacy["readback"],"PASS")
            self.assertFalse(receipt["dispatch_allowed"])
            with self.assertRaises(ContractError):
                persist_raw_feature_snapshot(store,{**r2,"raw_features_sha256":"0"*64})
            with self.assertRaises(ContractError):
                persist_raw_feature_snapshot(store,{**r2,"signal_id":"FORGED"})

    def test_invalid_reconciliation_does_not_emit_features(self):
        bad=fixture()
        bad=replace(bad,children=bad.children[:-1])
        row=self.one(bad)
        self.assertEqual(row["evaluation_status"],"INVALID")
        self.assertEqual(row["raw_features"],{})
        self.assertEqual(row["raw_features_status"],"NOT_ADMISSIBLE")
        self.assertIsNone(row["signal_id"])
