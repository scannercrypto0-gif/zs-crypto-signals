from datetime import datetime,timedelta,timezone
import unittest
from zs_smart_gate.stage03_science_pilot import *

class SciencePilotTests(unittest.TestCase):
    def test_dev_fit_ties_tails_and_holdout(self):
        f=ECDF.fit([1,2,2,4],phase='DEV')
        self.assertEqual(f.apply(2),.5)
        self.assertEqual(f.apply(0),0);self.assertEqual(f.apply(5),1)
        self.assertIsNone(f.apply(None))
        with self.assertRaises(ValueError):ECDF.fit([1],phase='OOS')
        with self.assertRaises(ValueError):ECDF.fit([float('nan')],phase='DEV')
        self.assertIsNone(robust(2,[1,1,1]))
    def test_zero_path_and_volume_never_zero_imputation(self):
        f=child_features([(100,100,100,100,0,0)]*6,1)
        self.assertIsNone(f['net_path']);self.assertIsNone(f['half_quote_share'])
        self.assertIsNone(relative_volume(10,[0]*20))
        self.assertEqual(relative_volume(20,[10]*20),2)
    def test_direction_and_price_volume_separation(self):
        cs=[(100+i,102+i,99+i,101+i,10,1000) for i in range(6)]
        up=child_features(cs,1);down=child_features(cs,-1)
        self.assertEqual(up['net_path'],-down['net_path'])
        self.assertEqual(up['half_quote_share'],down['half_quote_share'])
        self.assertEqual(up['half_quote_share'],.5)
    def test_pit_missing_stale_and_fake_authority(self):
        t=datetime(2026,1,1,tzinfo=timezone.utc)
        kw=dict(close=t,publication=t,source_available=t,received=t,decision=t,uncertainty=.1,independent=True)
        self.assertTrue(pit_status(**kw).startswith('PASS_INJECTED'))
        for change in ({'publication':None},{'publication':t+timedelta(seconds=1)}, {'uncertainty':1}, {'independent':False}, {'uncertainty':float('inf')}, {'received':t.replace(tzinfo=None)}):
            self.assertFalse(pit_status(**{**kw,**change}).startswith('PASS'))
    def test_purge_embargo_and_outcome_direction(self):
        b=datetime(2025,1,2,tzinfo=timezone.utc);h=timedelta(hours=1)
        self.assertFalse(split_admissible(b-h,b,phase='DEV',boundary=b,horizon=h))
        self.assertFalse(split_admissible(b,b+h,phase='OOS',boundary=b,horizon=h))
        self.assertTrue(split_admissible(b+h,b+2*h,phase='OOS',boundary=b,horizon=h))
        self.assertEqual(fixed_outcome(100,110,1),.1)
        self.assertEqual(fixed_outcome(100,110,-1),-.1)
    def test_barrier_order_censoring_and_power(self):
        self.assertEqual(first_hit([(102,98)],100,1),'UNKNOWN_SAME_BAR_ORDER')
        self.assertEqual(first_hit([(100,100)],100,1),'CENSORED')
        self.assertGreater(planned_independent_clusters(),1000)
        self.assertIsNone(correlation([1,1,1],[2,3,4]))
        self.assertAlmostEqual(correlation([1,2,3],[2,4,6]),1)
