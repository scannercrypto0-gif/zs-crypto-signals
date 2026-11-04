import copy,hashlib
from datetime import datetime,timezone
import unittest
from zs_smart_gate.forward_slot016 import capture_slot
from zs_smart_gate.evidence_journal import canonical_bytes,SingleStudyJournal
from zs_smart_gate.github_evidence_backend import GitHubEvidenceBackend
from test_github_evidence_backend import MockContentsTransport

class ForwardSlot016Tests(unittest.TestCase):
    def setUp(self):
        self.plan=[dict(path='/api/v3/time',params={},weight=1)]
        self.scope=dict(host='data-api.binance.vision',slots=14,max_GETs_per_slot=10,max_weight_per_slot=40,
            explicit_owner_activation=True,start_at=100,end_at=101000,study_id='forward-test',
            plan_sha256=hashlib.sha256(canonical_bytes(self.plan)).hexdigest())
        self.witness=dict(origin='EXTERNAL_INDEPENDENT_ATTESTATION',synthetic=False,epoch='e',reference_wall=100,
            reference_mono_ns=1000000000,valid_until_mono_ns=61000000000,absolute_error_seconds=.1,max_drift_ppm=20)
        sha=hashlib.sha256(canonical_bytes(self.witness)).hexdigest();self.witness['proof_sha256']=sha
        self.transport=MockContentsTransport()
        self.journal=SingleStudyJournal('forward-test',GitHubEvidenceBackend('forward-test',branch='evidence-forward-test',
            enabled=True,transport=self.transport),lambda:datetime.now(timezone.utc))
        self.calls=[]
    def options(self):
        return dict(slot_index=0,wall=100.5,mono=1500000000,epoch='e',witness=self.witness,
            reviewed_clock_pins={self.witness['proof_sha256']},admitted_owner_scopes={hashlib.sha256(canonical_bytes(self.scope)).hexdigest()},
            journal=self.journal,transport=self.get)
    def get(self,*args,**kwargs):
        self.calls.append(args);return dict(body=b'{"serverTime":100000}',status=200,elapsed_seconds=.01)
    def test_default_admission_is_zero_capture(self):
        r=capture_slot(self.scope,self.plan,slot_index=0,wall=100,mono=1000000000,epoch='e')
        self.assertEqual(r['status'],'NOT_ARMED');self.assertEqual(r['attempts'],0)
    def test_injected_approval_double_still_claims_once_and_never_starts_service(self):
        r=capture_slot(self.scope,self.plan,**self.options());self.assertEqual(r['attempts'],1)
        self.assertFalse(r['continuous_service']);self.assertFalse(r['continuous_collector_started'])
        again=capture_slot(self.scope,self.plan,**self.options());self.assertEqual(again['attempts'],0);self.assertEqual(len(self.calls),1)
    def test_missing_clock_proof_stops_before_any_get(self):
        options=self.options();options['reviewed_clock_pins']=set()
        self.assertEqual(capture_slot(self.scope,self.plan,**options)['attempts'],0)
    def test_github_offline_claim_stops_before_any_get(self):
        self.transport.fail_status=503
        self.assertEqual(capture_slot(self.scope,self.plan,**self.options())['attempts'],0)
    def test_network_failure_consumes_claim_and_never_retries(self):
        def fail(*args,**kwargs):self.calls.append(args);raise OSError('offline')
        options=self.options();options['transport']=fail
        r=capture_slot(self.scope,self.plan,**options);self.assertEqual(r['attempts'],1)
        self.assertEqual(r['status'],'STOPPED_NO_AUTOMATIC_RETRY')
        self.assertEqual(capture_slot(self.scope,self.plan,**options)['attempts'],0)
    def test_receipt_failure_does_not_repeat_captured_get(self):
        original=self.transport.put_file
        def interrupted(path,*args):
            if '/receipts/'in path:raise OSError('interrupted')
            return original(path,*args)
        self.transport.put_file=interrupted
        r=capture_slot(self.scope,self.plan,**self.options())
        self.assertEqual(r['status'],'UNKNOWN_RECEIPT_FAILURE_NO_RETRY')
        self.assertEqual(capture_slot(self.scope,self.plan,**self.options())['attempts'],0)
    def test_missed_slot_never_backfilled(self):
        options=self.options();options['wall']=300
        self.assertEqual(capture_slot(self.scope,self.plan,**options)['attempts'],0)
    def test_changed_or_expanded_plan_is_not_authorized(self):
        self.plan.append(dict(path='/api/v3/order',params={},weight=1))
        self.assertEqual(capture_slot(self.scope,self.plan,**self.options())['attempts'],0)
