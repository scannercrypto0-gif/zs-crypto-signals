"""007A minimal negative/aggregation tests; synthetic price fixtures are not DEV outcomes."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from decimal import Decimal
from zs_smart_gate.stage03a_contracts import Direction

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("zs03_r2_hist_007a", ROOT/"scripts/r2-historical-dev.py")
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)


def b(start,price,volume="100"):
    p=Decimal(str(price))
    return m.HistoricalOHLCV(start,start+m.FIVE_MIN,p,p+1,p-1,p+Decimal(".2"),Decimal(volume))


class HistoricalR2BoundaryTests(unittest.TestCase):
    def test_real_price_type_has_no_fabricated_receipt_or_clock(self):
        row=b(0,10)
        self.assertFalse(hasattr(row,"received_at"))
        self.assertFalse(hasattr(row,"available_at"))
        self.assertFalse(hasattr(row,"source_id"))
        self.assertFalse(hasattr(row,"independent_reference"))

    def test_aggregate_reuses_real_price_only_math_deterministically(self):
        rows=[b(i*m.FIVE_MIN,10+i) for i in range(26)]
        parent=m.aggregate(rows[-6:],6*m.FIVE_MIN)
        self.assertEqual(parent.start,20*m.FIVE_MIN)
        self.assertEqual(parent.end,26*m.FIVE_MIN)
        frames={"5m":rows,"1h":[],"4h":[]}
        ends={k:[x.end for x in v] for k,v in frames.items()}
        x, miss=m.numeric_groups(parent,rows[-6:],frames,ends,Direction.UP,"INTRADAY")
        y, miss2=m.numeric_groups(parent,rows[-6:],frames,ends,Direction.UP,"INTRADAY")
        self.assertEqual(x,y)
        self.assertEqual(miss,miss2)
        self.assertIsNotNone(x["30M_STRONG_CLOSE"])
        self.assertIsNotNone(x["SIX_5M_INTERNAL_QUALITY"])
        self.assertIsNotNone(x["VOLUME_CONTINUITY"])
        self.assertIsNone(x["MTF_NEARBY_STRUCTURE"])
        self.assertEqual(miss["MOMENTUM_EARLY_TIMING"],"UNAVAILABLE_FULL_IMPULSE_UNFROZEN")
        self.assertEqual(miss["LIQUIDITY_QUALITY"],"UNAVAILABLE_HISTORICAL_BOOK_24H")

    def test_noncontiguous_parent_cannot_be_rolled_up(self):
        rows=[b(i*m.FIVE_MIN,10+i) for i in range(6)]
        bad=rows[:3]+rows[4:]
        with self.assertRaisesRegex(m.Unavailable,"INCOMPLETE|GAP"):
            m.aggregate(bad,6*m.FIVE_MIN)
        self.assertEqual(m.resample(bad,6*m.FIVE_MIN),[])

    def test_no_stale_parent_context_or_future_use(self):
        rows=[b(i*m.FIVE_MIN,10+i) for i in range(20)]
        ends=[x.end for x in rows]
        with self.assertRaisesRegex(m.Unavailable,"CONTEXT_STALE|CONTEXT_WARMUP"):
            m.history_before(rows,ends,30*m.FIVE_MIN,20,m.FIVE_MIN)
        with self.assertRaisesRegex(m.Unavailable,"CONTEXT"):
            m.history_before(rows,ends,rows[-1].end+m.FIVE_MIN,20,m.FIVE_MIN,
                             aligned_last=True)

    def test_real_input_preflight_rejects_wrong_manifest_sha(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"manifest.json").write_text("{}")
            (root/"dataset-index.json").write_text("{}")
            with self.assertRaisesRegex(m.ResearchBlocked,"MANIFEST_OR_INDEX"):
                m.source_preflight(root)

    def test_missing_groups_cannot_be_zero_or_qualified(self):
        rows=[b(i*m.FIVE_MIN,10+i) for i in range(48)]
        parent=m.aggregate(rows, m.FOUR_HOUR)
        frames={"5m":rows,"1h":m.resample(rows,m.HOUR),"4h":m.resample(rows,m.FOUR_HOUR)}
        ends={k:[x.end for x in v] for k,v in frames.items()}
        groups,reasons=m.numeric_groups(parent,frames["1h"],frames,ends,
                                         Direction.DOWN,"SWING")
        self.assertIsNone(groups["MARKET_STRUCTURE"])
        self.assertIsNone(groups["LIQUIDITY_QUALITY"])
        self.assertIsNone(groups["DAILY_WEEKLY_CONTEXT"])
        self.assertEqual(reasons["MARKET_STRUCTURE"],
                         "UNAVAILABLE_VERIFIED_STRUCTURAL_LIQUIDITY")
        self.assertIsNotNone(groups["FOUR_H_STRONG_CLOSE"])
        self.assertIsNotNone(groups["FOUR_1H_INTERNAL_QUALITY"])

    def test_stats_directional_mirrors_not_independent_events(self):
        values={"30M_STRONG_CLOSE":Decimal(".5"),"LIQUIDITY_QUALITY":None}
        missing={"LIQUIDITY_QUALITY":"UNAVAILABLE_HISTORICAL_BOOK_24H"}
        stats=m.Stats(tuple(values))
        stats.add(b(0,10),values,missing)
        x=stats.export()
        self.assertEqual(x["observed_closed_windows"],1)
        self.assertEqual(x["groups"]["30M_STRONG_CLOSE"]["n"],1)
        self.assertEqual(x["groups"]["LIQUIDITY_QUALITY"]["missing_n"],1)


if __name__=="__main__":
    unittest.main()
