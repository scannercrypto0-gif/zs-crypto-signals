from decimal import Decimal as D
import unittest
from zs_smart_gate.stage03_science_expanded import (Bar,Series,aggregate,aligned_context,
    confirmed_pivots,setup_label,fit_models,normalized,holm,compare,forward_admission,verify_frozen_build,overlap_audit)

def bar(start=0,size=300,o=100,h=102,l=99,c=101):
    return Bar(start,start+size,D(o),D(h),D(l),D(c),D(1),D(100))

class ExpandedScienceTests(unittest.TestCase):
    def test_exact_reconciliation_and_gap(self):
        bars=[bar(i*300) for i in range(6)]
        merged=aggregate(bars,1800)
        self.assertEqual(merged.base,D(6));self.assertEqual(merged.quote,D(600))
        self.assertIsNone(aggregate(bars[:3]+bars[4:],1800))
        self.assertIsNone(aggregate([bars[0],bar(600)],600))
    def test_no_open_context_or_future_lookup(self):
        s=Series([bar(i*300) for i in range(12)])
        self.assertEqual(s.past(1800)[0].end,1800)
        self.assertEqual(s.past(1799)[0].end,1500)
        self.assertEqual(len(aligned_context(s.bars,1800)),2)
        self.assertEqual(len(aligned_context(s.bars[:-1],1800)),1)
    def test_pivot_confirmation_causal(self):
        bars=[bar(i*300,h=h) for i,h in enumerate([102,103,110,104,103,105,120])]
        pivots=confirmed_pivots(bars)
        self.assertIsNone(pivots[3][0]);self.assertEqual(pivots[4][0],110)
        changed=bars[:5]+[bar(1500,h=900),bar(1800,h=1000)]
        self.assertEqual(confirmed_pivots(changed)[:5],pivots[:5])
    def test_early_and_reversal_are_distinct(self):
        parent=bar(o=100,c=102,h=103)
        self.assertEqual(setup_label(parent,bar(o=100,c=100),D(2),D(101),1),'EARLY')
        self.assertEqual(setup_label(parent,bar(o=102,c=100,h=103),D(2),D(101),1),'REVERSAL')
        self.assertEqual(setup_label(parent,bar(o=102,c=100,h=103),D(2),None,1),'UNKNOWN')
    def test_dev_fit_and_frozen_oos_application(self):
        records=[{'horizon':'INTRADAY','direction':1,'raw':{'I3':v}} for v in (1.,2.,2.,4.)]
        m=fit_models(records,'DEV')
        self.assertEqual(normalized(records[1],'I3',m),.5)
        with self.assertRaises(ValueError):fit_models(records,'OOS')
        self.assertEqual(normalized({'horizon':'INTRADAY','direction':1,'raw':{'I3':100}},'I3',m),1)
        self.assertIsNone(normalized(records[0],'I6',m))
    def test_holm_keeps_missing_hypotheses_in_family(self):
        values=holm({'a':.001,'b':.02,'missing':None},40)
        self.assertAlmostEqual(values['a'],.04)
        self.assertAlmostEqual(values['b'],.78)
        self.assertIsNone(values['missing'])
        with self.assertRaises(ValueError):holm({'bad':-1},40)
    def test_permutation_is_reproducible_and_not_certificate(self):
        records=[];x=[];z=[]
        for week in (0,604800):
            for slot in range(42):
                for direction in (-1,1):
                    records.append({'asset':'fixture','week':week,'slot':slot,'direction':direction,'horizon':'SWING','outcome':direction*(slot%7)})
                    x.append(direction*(slot%5));z.append(direction*(slot%7))
        a=compare(records,x,z,permutations=16,bootstraps=16)
        self.assertEqual(a,compare(records,x,z,permutations=16,bootstraps=16))
        self.assertFalse(a['independent_PIT']);self.assertIsNone(a['N_effective'])
    def test_forward_unknown_late_and_clock_no_transport(self):
        args=dict(now=1000,close=900,publication_attested=True,clock_age=3,uncertainty=.1,pinned=True,frozen=True,evidence_approved=True)
        self.assertTrue(forward_admission(**args).startswith('ELIGIBLE_CONTRACT_ONLY'))
        for changes in ({'publication_attested':False},{'now':1500},{'uncertainty':None},{'now':float('nan')},{'clock_age':31},{'uncertainty':1},{'frozen':False}):
            self.assertFalse(forward_admission(**{**args,**changes}).startswith('ELIGIBLE'))
    def test_nondirectional_volume_cannot_be_tested_on_signed_pooled_labels(self):
        records=[];a=[];b=[]
        for slot in range(42):
            for direction in (-1,1):
                records.append({'asset':'fixture','week':0,'slot':slot,'direction':direction,'horizon':'SWING','outcome':direction*(slot%7)})
                a.append(slot%5);b.append(slot%3)
        result=compare(records,a,b,permutations=16,bootstraps=16)
        self.assertEqual(result['status'],'UNIDENTIFIABLE_NON_DIRECTIONAL_FEATURE_SIGNED_POOL')
        self.assertIsNone(result['p'])
        with self.assertRaises(ValueError):compare(records,a,b[:-1])
    def test_imported_source_digest_cannot_be_changed_under_frozen_runner(self):
        import hashlib
        m={'runner_sha256':hashlib.sha256(b'runner').hexdigest(),'expanded_module_sha256':hashlib.sha256(b'module').hexdigest()}
        verify_frozen_build(m,b'runner',b'module')
        with self.assertRaisesRegex(ValueError,'FROZEN_CODE_CHANGED'):verify_frozen_build(m,b'runner',b'changed')
        with self.assertRaisesRegex(ValueError,'MISSING_FROZEN_BUILD_DIGEST'):verify_frozen_build({'runner_sha256':m['runner_sha256']},b'runner',b'module')
    def test_overlap_audit_is_direction_conditional_and_label_free(self):
        records=[{'asset':'fixture','horizon':'INTRADAY','direction':1,'raw':{'I2':v,'I4':v/10}} for v in (1.,2.,3.)]
        result=overlap_audit(records,fit_models(records,'DEV'))['I2xI4']
        self.assertFalse(result['uses_outcome_labels'])
        self.assertAlmostEqual(next(iter(result['strata'].values()))['descriptive_correlation'],1)
