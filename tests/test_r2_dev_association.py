"""Focused 008 boundary/selection and baseline tests, entirely synthetic fixtures."""
import dataclasses
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("zs03_008_assoc_tests",
                                            ROOT/"scripts/r2-dev-association.py")
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)


def source(n, first=0):
    bars=[]
    for i in range(n):
        t=first+i*m.mod.FIVE_MIN
        p=Decimal(10+i)
        bars.append(m.mod.HistoricalOHLCV(
            t,t+m.mod.FIVE_MIN,p,p+Decimal(1),p-Decimal(1),
            p+Decimal(".25"),Decimal(100)))
    return bars


class AssociationBoundaryTests(unittest.TestCase):
    def test_outcome_starts_at_next_open_and_requires_complete_future(self):
        bars=source(70)
        starts=[b.start for b in bars]
        parent_end=6*m.mod.FIVE_MIN
        four_h=m.FUTURES["INTRADAY"]
        val,reason=m.exact_future_label(bars,starts,parent_end,four_h,
                                        100*m.mod.FIVE_MIN,"UP")
        self.assertIsNone(reason)
        self.assertGreater(val,0)
        entry=bars[6].o
        last=bars[6+48-1].c
        self.assertEqual(val,Decimal(100)*(last-entry)/entry)
        neg,_=m.exact_future_label(bars,starts,parent_end,four_h,
                                   100*m.mod.FIVE_MIN,"DOWN")
        self.assertEqual(val,-neg)

    def test_dev_end_purge_even_if_future_bytes_exist(self):
        bars=source(120)
        starts=[b.start for b in bars]
        end=6*m.mod.FIVE_MIN
        val,reason=m.exact_future_label(
            bars,starts,end,m.FUTURES["INTRADAY"],
            end+m.FUTURES["INTRADAY"]-m.mod.FIVE_MIN,"UP")
        self.assertIsNone(val)
        self.assertEqual(reason,"LABEL_CROSSES_DEV_END_PURGED")

    def test_future_gap_cannot_get_valid_label(self):
        bars=source(70)
        altered=list(bars)
        altered[15]=dataclasses.replace(altered[15],
                                       start=altered[15].start+m.mod.FIVE_MIN,
                                       end=altered[15].end+m.mod.FIVE_MIN)
        value,reason=m.exact_future_label(altered,[b.start for b in altered],
            6*m.mod.FIVE_MIN,m.FUTURES["INTRADAY"],
            100*m.mod.FIVE_MIN,"UP")
        self.assertIsNone(value)
        self.assertEqual(reason,"LABEL_FUTURE_GAP_REJECTED")

    def test_per_asset_direction_top20_selection_before_any_label(self):
        records=[{"start":i*100, "end":(i+1)*100,
                  "value":Decimal("0.5") if i>=3 else Decimal("0.25"),
                  "week":0} for i in range(10)]
        grouped={"INTRADAY":{"UP":records,"DOWN":records}}
        with tempfile.TemporaryDirectory() as p:
            out=Path(p)
            selections,counts,sha=m.select_before_future(grouped,out,"BTCUSDT")
            self.assertEqual(counts["INTRADAY"]["UP"]["top_selected"],2)
            self.assertEqual(selections["INTRADAY"]["UP"],{300,400})
            self.assertEqual(selections["INTRADAY"]["DOWN"],{300,400})
            self.assertEqual(len(sha),64)
            self.assertTrue((out/"assignment-seal-008-BTCUSDT.json").exists())
            with self.assertRaises(FileExistsError):
                m.select_before_future(grouped,out,"BTCUSDT")

    def test_negative_effect_is_retained_and_block_warning(self):
        top=[{"return_pct":Decimal(-2), "week":1},
             {"return_pct":Decimal(-1), "week":2}]
        rest=[{"return_pct":Decimal(1), "week":1},
              {"return_pct":Decimal(2), "week":2}]
        c=m.compare(top,rest)
        self.assertEqual(c["mean_difference_pct_points"],-3)
        self.assertEqual(c["top"]["negative"],2)
        self.assertEqual(c["top"]["positive_fraction"],0)
        w=m.block_compare(top,rest)
        self.assertEqual(w["weeks_treatment_mean_below_control"],2)
        self.assertEqual(w["top_weighted_within_week_difference_pct_points"],-3)
        self.assertIsNone(w["confidence_interval"])
        self.assertIn("UNCERTAINTY_NOT_RELIABLY_ESTIMABLE",w["uncertainty_status"])

    def test_no_fake_receipts_or_market_trading_path(self):
        import inspect
        s=inspect.getsource(m)
        self.assertNotIn("SourceReceipt(",s)
        self.assertNotIn("ClockWitness(",s)
        self.assertNotIn("evaluate_r2(",s)
        self.assertNotIn("SYNTHETIC:CANDLE",s)
        self.assertIn("HISTORICAL_REPLAY_PIT_UNVERIFIED",s)


if __name__=="__main__":
    unittest.main()
