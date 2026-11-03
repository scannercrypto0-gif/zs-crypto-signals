import copy
import hashlib
import unittest
from zs_smart_gate.prospective_causality import receipt,assess,utc_gate,forward_gate,digest
from zs_smart_gate.evidence_journal import canonical_bytes
from zs_smart_gate.science016 import interval,cost_scenario,winner_gate
from zs_smart_gate.science016 import prediction_gain,fit_ecdf,ecdf_value,partition,dependence_diagnostic

class Receipt016Tests(unittest.TestCase):
    def setUp(self):
        self.raw=b'original source snapshot';self.sha=hashlib.sha256(self.raw).hexdigest()
        self.event=receipt(self.raw,source_event_id='BTCUSDT/5m/1',seq=1,epoch='e1',previous='0'*64,
            received_wall=100.,received_mono=1000000000,closed_at=99.)
        self.proof=dict(origin='EXTERNAL_INDEPENDENT_ATTESTATION',proof_sha256='a'*64,synthetic=False,
            epoch='e1',reference_wall=100.,reference_mono_ns=1000000000,valid_until_mono_ns=61000000000,
            absolute_error_seconds=.1,max_drift_ppm=20)
    def trust_double(self):
        body={k:v for k,v in self.proof.items()if k!='proof_sha256'}
        self.proof['proof_sha256']=hashlib.sha256(canonical_bytes(body)).hexdigest()
        return {self.proof['proof_sha256']}
    def check(self,events=None,**kwargs):
        args=dict(anchor='0'*64,decision_wall=100.5,decision_mono=1500000000,epoch='e1',
            source_mode='NEW_FUTURE_OBSERVATION',used_digests=[self.event['digest']])
        args.update(kwargs)
        return assess(events if events is not None else[self.event],{self.sha:self.raw},**args)
    def test_receipt_is_separate_from_utc_and_publisher(self):
        r=self.check();self.assertEqual(r['receipt_evidence'],'RECEIVED_BEFORE_DECISION')
        self.assertEqual(r['status'],'HOLD');self.assertEqual(r['publisher_original_publication'],'MISSING')
        self.assertEqual(r['historical_publisher_pit'],'HOLD')
    def test_injected_independent_trust_double_exercises_candidate_only(self):
        r=self.check(witness=self.proof,reviewed_proof_hashes=self.trust_double())
        self.assertEqual(r['status'],'PROSPECTIVE_CAUSALITY_PASS_CANDIDATE')
        self.assertEqual(r['historical_publisher_pit'],'HOLD')
    def test_nts_authentication_or_unreviewed_pin_is_not_absolute_time(self):
        self.assertEqual(self.check(witness=self.proof)['status'],'HOLD')
        self.proof['origin']='AUTHENTICATED_NTS_ONLY'
        self.assertEqual(self.check(witness=self.proof,reviewed_proof_hashes=self.trust_double())['status'],'HOLD')
    def test_synthetic_proof_cannot_certify_utc(self):
        self.proof['synthetic']=True
        self.assertEqual(self.check(witness=self.proof,reviewed_proof_hashes=self.trust_double())['status'],'HOLD')
    def test_old_archive_never_new_oos_even_with_trust_double(self):
        r=self.check(source_mode='HISTORICAL_ARCHIVE',witness=self.proof,reviewed_proof_hashes=self.trust_double())
        self.assertEqual(r['status'],'HOLD')
    def test_tampered_hash_chain(self):
        e=copy.deepcopy(self.event);e['collector_received_at']=99
        self.assertEqual(self.check([e])['receipt_evidence'],'FAIL')
    def test_raw_tamper(self):
        r=assess([self.event],{self.sha:b'bad'},anchor='0'*64,decision_wall=100.5,decision_mono=1500000000,
            epoch='e1',source_mode='NEW_FUTURE_OBSERVATION',used_digests=[self.event['digest']])
        self.assertIn('RAW_HASH_OR_SIZE_CONFLICT',r['reasons'])
    def test_late_receipt(self):
        self.assertEqual(self.check(decision_mono=999999999)['status'],'FAIL')
    def test_gap_sequence(self):
        e=copy.deepcopy(self.event);e['seq']=2;e['digest']=digest(e)
        self.assertEqual(self.check([e])['status'],'FAIL')
    def test_source_gap_barrier(self):
        e=copy.deepcopy(self.event);e['kind']='GAP';e['digest']=digest(e)
        self.assertEqual(self.check([e])['status'],'FAIL')
    def test_forming_candle(self):
        e=copy.deepcopy(self.event);e['closed_at']=101;e['digest']=digest(e)
        self.assertEqual(self.check([e])['status'],'FAIL')
    def test_reconnect_epoch(self):
        self.assertEqual(self.check(epoch='e2')['status'],'FAIL')
    def test_decision_wall_step(self):
        self.assertEqual(self.check(decision_wall=102)['status'],'FAIL')
    def test_duplicate(self):
        e=receipt(self.raw,source_event_id=self.event['source_event_id'],seq=2,epoch='e1',previous=self.event['digest'],
             received_wall=100.1,received_mono=1100000000,closed_at=99.)
        self.assertIn('DUPLICATE_OR_UNLINKED_CORRECTION',self.check([self.event,e])['reasons'])
    def test_linked_revision_supersedes_old_inputs_without_rewriting_history(self):
        e=receipt(self.raw,source_event_id=self.event['source_event_id'],seq=2,epoch='e1',previous=self.event['digest'],
             received_wall=100.1,received_mono=1100000000,closed_at=99.,revision=1,supersedes=self.event['digest'])
        self.assertEqual(self.check([self.event,e])['status'],'FAIL')
        self.assertEqual(self.check([self.event,e],used_digests=[e['digest']])['receipt_evidence'],'RECEIVED_BEFORE_DECISION')
    def test_unknown_future_variable(self):
        self.assertEqual(self.check(used_digests=['f'*64])['status'],'FAIL')
    def test_duplicate_decision_inputs_are_not_extra_evidence(self):
        self.assertEqual(self.check(used_digests=[self.event['digest']]*2)['status'],'FAIL')
    def test_expired_clock(self):
        self.proof['valid_until_mono_ns']=1200000000
        self.assertEqual(self.check(witness=self.proof,reviewed_proof_hashes=self.trust_double())['utc_evidence']['status'],'HOLD')
    def test_decision_calibration_cannot_certify_earlier_uncovered_receipts(self):
        self.proof['reference_mono_ns']=1200000000;self.proof['reference_wall']=100.2
        r=self.check(witness=self.proof,reviewed_proof_hashes=self.trust_double())
        self.assertEqual(r['utc_evidence']['reason'],'RECEIPT_OUTSIDE_ATTESTED_CALIBRATION')
    def test_finality_requires_margin_for_utc_uncertainty(self):
        e=copy.deepcopy(self.event);e['closed_at']=99.95;e['digest']=digest(e)
        r=self.check([e],used_digests=[e['digest']],witness=self.proof,reviewed_proof_hashes=self.trust_double())
        self.assertEqual(r['status'],'FAIL')
    def test_drift_bound(self):
        self.proof['max_drift_ppm']=2000000
        self.assertEqual(self.check(witness=self.proof,reviewed_proof_hashes=self.trust_double())['status'],'HOLD')
    def test_nonfinite_clock(self):
        self.proof['absolute_error_seconds']=float('nan')
        self.assertEqual(self.check(witness=self.proof,reviewed_proof_hashes=self.trust_double())['utc_evidence']['status'],'FAIL')
    def test_admitted_document_cannot_be_reused_with_smaller_error_bound(self):
        pins=self.trust_double();self.proof['absolute_error_seconds']=0
        r=self.check(witness=self.proof,reviewed_proof_hashes=pins)
        self.assertEqual(r['utc_evidence']['reason'],'ADMITTED_UTC_DOCUMENT_CHANGED')
    def test_forward_zero_capture_default(self):
        r=forward_gate();self.assertEqual(r['status'],'NOT_ARMED');self.assertEqual(r['live_capture_events'],0)
    def test_forward_network_clock_storage_and_recovery_fail_closed(self):
        r=forward_gate(owner_scope={'one':'test_double'},causality={'status':'HOLD'},durable_storage=False,
            recovery_gap=True,network_available=False,protocol_pinned=True)
        self.assertEqual(r['status'],'NOT_ARMED');self.assertFalse(r['collector_started'])
    def test_ready_is_not_started_even_for_mock_positive_dependencies(self):
        r=forward_gate(owner_scope={'scope':'test_double'},causality={'status':'PROSPECTIVE_CAUSALITY_PASS_CANDIDATE'},
            durable_storage=True,protocol_pinned=True)
        self.assertEqual(r['status'],'READY_FOR_SEPARATE_OWNER_ACTIVATION');self.assertFalse(r['collector_started'])

class Inference016Tests(unittest.TestCase):
    def test_prefrozen_paired_loss_and_missing_domain(self):
        self.assertEqual(prediction_gain(1,100,direction=1,scale_bps=100),.25)
        self.assertEqual(prediction_gain(1,-100,direction=1,scale_bps=100),-.75)
        with self.assertRaises(ValueError):prediction_gain(None,100,direction=1,scale_bps=100)
    def test_exploratory_cdf_is_dev_only_and_ties_are_explicit(self):
        model=fit_ecdf([1,1,1],phase='DEV');self.assertEqual(ecdf_value(1,model),.5)
        with self.assertRaisesRegex(ValueError,'OOS_REFIT_FORBIDDEN'):fit_ecdf([1,2],phase='OOS')
    def test_old_or_unadmitted_data_never_new_oos(self):
        event=dict(raw_sha256='x',source_mode='NEW_AFTER_FREEZE_LIVE_RECEIPT',causality='PROSPECTIVE_CAUSALITY_PASS_CANDIDATE',decision_at=1000000)
        kwargs=dict(freeze_at=0,dev_end=10,oos_start=700000,admitted_hashes={'x'},previously_viewed_hashes={'x'})
        self.assertEqual(partition(event,**kwargs),'INELIGIBLE_OLD_VIEWED_OR_UNADMITTED_DATA')
        kwargs['previously_viewed_hashes']=set();self.assertEqual(partition(event,**kwargs),'OOS')
        event['source_mode']='HISTORICAL_ARCHIVE';self.assertTrue(partition(event,**kwargs).startswith('INELIGIBLE'))
    def test_insufficient_purge_is_rejected(self):
        with self.assertRaises(ValueError):partition({},freeze_at=0,dev_end=10,oos_start=20,admitted_hashes=set(),previously_viewed_hashes=set())
    def test_estimated_effectiveN_never_qualified(self):
        d=dependence_diagnostic(list(range(20)));self.assertLess(d['N_effective_diagnostic_not_qualified'],20)
        self.assertIsNone(d['N_required_qualified']);self.assertFalse(d['independence_proved'])
    def test_actual_N_never_certified_by_event_count(self):
        r=interval([.1]*256);self.assertIsNone(r['N_effective']);self.assertEqual(r['status'],'HOLD_UNPROVED_BLOCK_INDEPENDENCE')
    def test_multiplicity_widens_bound(self):
        self.assertGreater(interval([0]*64,24)['radius'],interval([0]*64,1)['radius'])
    def test_nonbounded_or_nonfinite_loss_rejected(self):
        for data in [[],[2],[float('nan')],[True]]:
            with self.assertRaises(ValueError):interval(data)
    def test_cost_sensitivity_does_not_claim_fills(self):
        r=cost_scenario(20,direction=1,fees_bps=10,slippage_bps=5,spread_bps=8)
        self.assertEqual(r['net_scenario_bps'],-3);self.assertFalse(r['actual_execution_or_profitability_proved'])
    def test_valid_negative_study_has_no_winner(self):
        self.assertEqual(winner_gate(lower_bound=-.1,independent_oos=True,clock_pass=True,liquidity_pass=True,cost_review_pass=True),'NO_WINNER_WITH_VALID_EVIDENCE')
    def test_synthetic_or_old_oos_cannot_create_winner(self):
        self.assertEqual(winner_gate(lower_bound=.5,independent_oos=False,clock_pass=True,liquidity_pass=True,cost_review_pass=True),'HOLD_NO_QUALIFIED_WINNER')
