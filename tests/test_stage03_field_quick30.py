"""Offline only: quick30 prospective window fail-close and real typed E2E fixture."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

from zs_smart_gate import stage03_field_quick30 as q

UTC=timezone.utc

def dt(t):
    return datetime(2026,11,8,t,tzinfo=UTC)

def bar(start,minutes,base="1",quote="100"):
    end=start+timedelta(minutes=minutes)
    return {"open_ms":int(start.timestamp()*1000),
            "close_exclusive_ms":int(end.timestamp()*1000),
            "open":"100","high":"100","low":"100","close":"100",
            "base_volume":base,"quote_volume":quote}

def rec(frame,bars,end):
    return {"selected":{"interval":frame,"bars":bars},
            "received_utc_unattested":end.isoformat()}

class QuickThirtySafety(unittest.TestCase):
    def test_parent_is_original_4h_boundary_not_arbitrary_retro(self):
        self.assertEqual(q.validate_open("2026-11-08T08:00:00Z"),dt(8))
        for t in ("2026-11-08T07:30:00Z","2026-11-08T08:30:00Z",
                  "2026-11-08T20:00:00Z"):
            with self.assertRaises(ValueError):
                q.validate_open(t)

    def test_existing_pre_not_modified_and_distinct_quick_post(self):
        a,b,c=q.paths(Path("safe"),dt(8))
        self.assertEqual(a.name,"zs03-20261108T0800Z-pre.json")
        self.assertEqual(b.name,"zs03-20261108T0800Z-quick30-post.json")
        self.assertNotEqual(b.name,"zs03-20261108T0800Z-post.json")
        self.assertNotEqual(b,c)

    def test_pre_absent_fails_no_get(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                q.precheck(Path(d)/"missing.json",dt(8),Path(d)/"rights",fresh=True)

    def test_early_post_denied_without_issuing_get_or_file(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"quick30-post.json"
            with patch.object(q,"precheck",return_value={"record_sha256":"a"*64}):
                with patch.object(q,"utcnow",return_value=dt(8)+timedelta(minutes=20)):
                    with patch.object(q,"acquire",side_effect=AssertionError("GET_FORBIDDEN")):
                        with self.assertRaisesRegex(ValueError,"QUICK30_POST_MUST_RUN"):
                            q.capture(Path("pre"),path,dt(8),Path("rights"))
            self.assertFalse(path.exists())

    def test_write_once_no_retry_even_when_early(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"quick30-post.json"
            path.write_text("failure preserved",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"ATTEMPT_EXISTS_NO_RETRY"):
                q.capture(Path("pre"),path,dt(8),Path("rights"))

    def test_real_typed_30m_e2e_fixture_no_promotion(self):
        parent=dt(8);end=parent+timedelta(minutes=30)
        received=end+timedelta(seconds=4)
        pre={"record_sha256":"a"*64,"requests":[
            {"selected":{"status":"TRADING","symbol":"BTCUSDT"}},
            {"selected":{"bars":[]}}]}
        five=[bar(end-timedelta(minutes=5*(21-i)),5,base="0.01",quote="1")
              for i in range(21)]
        thirty=bar(parent,30,base="0.06",quote="6")
        first=rec("5m",five,received)
        second=rec("30m",[thirty],received)
        book={"selected":{"bidPrice":"100","askPrice":"100.1",
                           "symbol":"BTCUSDT"}}
        ticker={"selected":{"quoteVolume":"20000000","symbol":"BTCUSDT"}}
        post={"record_sha256":"b"*64,
              "requests":[first,second,book,ticker]}
        receipt_utc=received+timedelta(milliseconds=25)
        def receipt(item):
            return receipt_utc
        with patch.object(q,"verify",return_value=(pre,post,end+timedelta(seconds=5))):
            with patch.object(q,"instant",side_effect=lambda x:(received,receipt_utc)):
                with patch.object(q,"strict_pivot_mode",return_value={"status":"UNAVAILABLE"}):
                    result=q.e2e(Path("pre"),Path("post"),parent,Path("rights"))
        self.assertEqual(result["real_30m_03a_e2e"],"PASS")
        self.assertEqual(result["reconciliation"]["status"],"PASS")
        self.assertEqual(result["real_03a_status"],"RESEARCH_CANDIDATE")
        self.assertFalse(result["stage03_closed"])
        self.assertIsNone(result["score"])
        self.assertIsNone(result["signal_id"])
        self.assertFalse(result["r2_n01_to_n12_real_source_qualified"])
        self.assertFalse(result["publishable"])

if __name__=="__main__":
    unittest.main()
