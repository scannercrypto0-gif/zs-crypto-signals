import copy
import hashlib
import unittest
from unittest.mock import patch
from zs_smart_gate.evidence_journal import canonical_bytes
from zs_smart_gate.prospective_causality_v2 import VERSION, receipt
from zs_smart_gate.integrated_research018 import evaluate
from zs_smart_gate.forward_slot018 import capture_slot
from test_integrated016 import fixture
from test_prospective018 import proof, pin
import test_forward_slot016 as old_fixture


class Integration018Tests(unittest.TestCase):
    def bundle(self, *, wall_delay_ms=2500):
        data=fixture()
        data['received_ms']=data['rows'][-1][6]+1+wall_delay_ms
        data.update(received_mono_ns=1000000000,collector_epoch='test-epoch')
        # A synthetic provenance double exercises the new entry point only.
        data['provenance']['mode']='NEW_AFTER_FREEZE_LIVE_RECEIPT'
        raw=canonical_bytes(data);sha=hashlib.sha256(raw).hexdigest()
        event=receipt(raw,source_event_id='synthetic018',seq=1,epoch='test-epoch',previous='a'*64,
            received_wall=data['received_ms']/1000,received_mono=1000000000,closed_at=(data['rows'][-1][6]+1)/1000)
        w=proof(wall=data['received_ms']/1000)
        args=dict(expected_sha256=sha,decision_ms=data['received_ms']+500,decision_mono_ns=1500000000,
            witness=w,reviewed_proof_hashes=pin(w),reviewed_chain_anchors={'a'*64},
            causal_bundle=dict(events=[event],raw_by_hash={sha:raw},anchor='a'*64,used_digests=[event['digest']]))
        return data,raw,args

    def test_new_decision_routes_through_v2_and_stays_research_only(self):
        data,raw,args=self.bundle()
        result=evaluate(raw,**args)
        self.assertEqual(result['causality']['version'],VERSION)
        self.assertEqual(result['causality']['status'],'PROSPECTIVE_CAUSALITY_PASS_CANDIDATE')
        self.assertIsNone(result['score']);self.assertFalse(result['publishable'])
        self.assertEqual(result['forward_state'],'NOT_ARMED');self.assertFalse(result['new_oos_eligible'])

    def test_previous_study_cannot_be_relabelled_with_v2(self):
        with self.assertRaisesRegex(ValueError,'V2_REQUIRES_NEW_FUTURE'):
            evaluate(b'old study',expected_sha256='0'*64,decision_ms=0,source_mode='HISTORICAL_ARCHIVE')

    def test_integration_candle_uncertainty_margin_is_enforced(self):
        _,raw,args=self.bundle(wall_delay_ms=100)
        result=evaluate(raw,**args)
        self.assertEqual(result['causality']['status'],'FAIL')
        self.assertIn('CANDLE_FINALITY_INSIDE_CLOCK_UNCERTAINTY',result['causality']['reasons'])

    def test_future_context_rejected_before_use(self):
        data,_,args=self.bundle()
        data['contexts']={'1d':dict(received_ms=args['decision_ms']+1,rows=[])}
        raw=canonical_bytes(data);args['expected_sha256']=hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(ValueError,'CONTEXT_RECEIVED_AFTER_DECISION'):
            evaluate(raw,**args)

    def test_latency_limit_is_separate_and_not_changed_to_1p5(self):
        data,raw,args=self.bundle();args['decision_ms']=data['received_ms']+2000;args['decision_mono_ns']=3000000000
        self.assertEqual(evaluate(raw,**args)['causality']['status'],'PROSPECTIVE_CAUSALITY_PASS_CANDIDATE')
        args['decision_ms']=data['received_ms']+10001
        with self.assertRaisesRegex(ValueError,'LATE_DECISION'):
            evaluate(raw,**args)

    def options(self):
        f=old_fixture.ForwardSlot016Tests();f.setUp()
        f.scope['causality_version']=VERSION
        f.witness=proof()
        # Match the existing dormant slot fixture epoch.
        f.witness['epoch']='e';pin(f.witness)
        return f,f.options()

    def test_dormant_scope_v2_is_required_before_any_io(self):
        f,options=self.options();f.scope.pop('causality_version')
        self.assertEqual(capture_slot(f.scope,f.plan,**options)['attempts'],0)
        self.assertFalse(f.calls)

    def test_v2_without_clock_admission_performs_zero_gets(self):
        f,options=self.options();options['reviewed_clock_pins']=set()
        self.assertEqual(capture_slot(f.scope,f.plan,**options)['attempts'],0)

    def test_bound_above_v1_below_v2_injected_slot_still_claims_once(self):
        f,options=self.options()
        r=capture_slot(f.scope,f.plan,**options)
        self.assertEqual(r['attempts'],1);self.assertFalse(r['continuous_collector_started'])
        self.assertEqual(capture_slot(f.scope,f.plan,**options)['attempts'],0)

    def test_exact_ceiling_prevents_transport(self):
        f,options=self.options();f.witness=proof(1.5);f.witness['epoch']='e'
        options['witness']=f.witness;options['reviewed_clock_pins']=pin(f.witness)
        self.assertEqual(capture_slot(f.scope,f.plan,**options)['attempts'],0)

    def test_expiry_mid_slot_consumes_claim_without_retry(self):
        f,options=self.options()
        f.witness['valid_until_mono_ns']=1500000000
        options['reviewed_clock_pins']=pin(f.witness)
        # Explicitly advance one tick; some Windows runners legitimately
        # return the same monotonic reading for consecutive fast calls.
        with patch('zs_smart_gate.forward_slot018.time.monotonic_ns',side_effect=[1000000000,1000000001]), \
             patch('zs_smart_gate.forward_slot018.time.time_ns',side_effect=[100000000000,100000000001]):
            result=capture_slot(f.scope,f.plan,**options)
        self.assertEqual(result['status'],'STOPPED_NO_AUTOMATIC_RETRY')
        self.assertEqual(result['attempts'],0)
        self.assertEqual(capture_slot(f.scope,f.plan,**options)['attempts'],0)

