"""Synthetic fixture for the REAL-SOURCE ADAPTER contract only. NO live/PIT claims."""
import unittest
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
from decimal import Decimal

from zs_smart_gate import stage03_field_real_e2e as e2e


def ms(dt):
    return int(dt.timestamp()*1000)

def row(at,step,price="100",base="0.01",quote="1"):
    return {"open_ms":ms(at),"close_exclusive_ms":ms(at+step),
            "open":price,"high":price,"low":price,"close":price,
            "base_volume":base,"quote_volume":quote}

def rec(frame,rows,when):
    return {"selected":{"interval":frame,"bars":rows},
            "received_utc_unattested":when.isoformat(),
            "fake_upper":when+timedelta(milliseconds=50),
            "raw_sha256":"f"*64}

class TestOfflineRealAdapter(unittest.TestCase):
    def test_original_typed_research_bridge_no_fake_score(self):
        start=datetime(2026,11,8,4,tzinfo=timezone.utc)
        end=start+timedelta(hours=4)
        pretime=start-timedelta(minutes=2)
        posttime=end+timedelta(seconds=4)
        dt=timedelta(hours=4)
        old=[row(start-dt*(33-i),dt) for i in range(32)]
        pre={"parent_open_utc":start.isoformat(),
             "requests":[{"selected":{"status":"TRADING","symbol":"BTCUSDT","quoteAsset":"USDT"},
                          "fake_upper":pretime},
                         rec("4h",old,pretime),
                         rec("1d",[row(start-timedelta(days=i+1),
                                       timedelta(days=1)) for i in range(19,0,-1)],pretime),
                         rec("1w",[row(start-timedelta(weeks=i+1),
                                       timedelta(weeks=1)) for i in range(19,0,-1)],pretime)]}
        h=timedelta(hours=1)
        hours=[row(start+i*h,h,base="0.12",quote="12") for i in range(4)]
        f=timedelta(minutes=5)
        five=[row(end-f*(21-i),f) for i in range(21)]
        parent=row(start,dt,base="0.48",quote="48")
        post={"requests":[rec("5m",five,posttime),
                           rec("30m",[row(start+timedelta(minutes=30)*i,
                                       timedelta(minutes=30),base="0.06",quote="6") for i in range(8)],posttime),
                           rec("1h",hours,posttime),
                           rec("4h",[parent],posttime),
                           {"selected":{"symbol":"BTCUSDT","bidPrice":"100","askPrice":"100.1"},
                            "fake_upper":posttime},
                           {"selected":{"symbol":"BTCUSDT","quoteVolume":"20000000"},
                            "fake_upper":posttime}],
              "decision_witness":{"at_local_utc_unattested":(end+timedelta(seconds=5)).isoformat(),
                                  "earliest_utc":(end+timedelta(seconds=4, milliseconds=500)).isoformat()}}
        review={"pre_receipt_sha256":"a"*64,"post_receipt_sha256":"b"*64,
                "rights_evidence_sha256":"c"*64}
        def fake_check(path):
            return pre if path=="pre" else post
        def fake_received(item):
            return item["fake_upper"]
        with patch.object(e2e,"verify",return_value=review),\
             patch.object(e2e,"check_file",side_effect=fake_check),\
             patch.object(e2e,"received_time",side_effect=fake_received),\
             patch.object(e2e,"asof_request",return_value=None):
            result=e2e.run("pre","post","rights")
            again=e2e.run("pre","post","rights")
        self.assertEqual(result["packet_sha256"],again["packet_sha256"])
        self.assertEqual(result["schema"],e2e.CONTRACT)
        self.assertEqual(result["real_03a_status"],"RESEARCH_CANDIDATE")
        self.assertEqual(result["intraday_03a_status"],"RESEARCH_CANDIDATE")
        self.assertEqual(result["intraday_reconciliation"]["status"],"PASS")
        self.assertTrue(result["stage03_to_03a_research_functional_pass"])
        self.assertEqual(result["reconciliation"]["status"],"PASS")
        self.assertIsNone(result["score"])
        self.assertIsNone(result["signal_id"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["r2_n01_to_n12_real_source_qualified"])
        self.assertFalse(result["scientific_stage03_closed"])


if __name__=="__main__":
    unittest.main()
