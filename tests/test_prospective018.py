"""Synthetic trust doubles test policy, never create admitted field clock proof."""
import copy
import hashlib
import math
import unittest
from zs_smart_gate.evidence_journal import canonical_bytes
from zs_smart_gate.prospective_causality import utc_gate as v1_gate
from zs_smart_gate.prospective_causality_v2 import VERSION, utc_gate, assess, receipt, digest, timing_diagnostics, forward_gate


def proof(bound=1.499, *, wall=100., mono=1000000000):
    return dict(origin='EXTERNAL_INDEPENDENT_ATTESTATION', synthetic=False,
        causality_version=VERSION, epoch='test-epoch', reference_wall=wall,
        reference_mono_ns=mono, valid_until_mono_ns=mono+100000000000,
        absolute_error_seconds=bound, max_drift_ppm=0,
        counter_calibrated=True, maximum_future_drift_proved=True,
        counter_calibration_proof_sha256='c'*64, drift_proof_sha256='d'*64,
        error_budget_seconds=dict(source=bound, transfer_and_timestamping=0, local_counter_calibration=0))


def pin(w):
    w['proof_sha256'] = hashlib.sha256(canonical_bytes({k:v for k,v in w.items() if k!='proof_sha256'})).hexdigest()
    return {w['proof_sha256']}


class Prospective018Tests(unittest.TestCase):
    def gate(self, w, **kwargs):
        args=dict(wall=100.,mono=1000000000,epoch='test-epoch',reviewed_proof_hashes=pin(w))
        args.update(kwargs)
        return utc_gate(w, **args)

    def causal(self, w=None, *, closed=98., received=100., d_wall=100.5, d_mono=1500000000, **kwargs):
        raw=b'018 synthetic closed candle'
        event=receipt(raw,source_event_id='BTCUSDT/5m/test',seq=1,epoch='test-epoch',previous='a'*64,
                      received_wall=received,received_mono=1000000000,closed_at=closed)
        args=dict(anchor='a'*64,decision_wall=d_wall,decision_mono=d_mono,epoch='test-epoch',
                  source_mode='NEW_FUTURE_OBSERVATION',used_digests=[event['digest']],witness=w,
                  reviewed_proof_hashes=pin(w) if w else frozenset())
        args.update(kwargs)
        return assess([event],{event['raw_sha256']:raw},**args)

    def test_1499_accepts_only_complete_independently_admitted_double(self):
        self.assertEqual(self.gate(proof())['status'],'UTC_BOUND_VERIFIED')
        result=self.causal(proof())
        self.assertEqual(result['status'],'PROSPECTIVE_CAUSALITY_PASS_CANDIDATE')
        self.assertEqual(result['version'],VERSION)

    def test_1500_rejected(self):
        self.assertEqual(self.gate(proof(1.500))['status'],'HOLD')

    def test_1501_rejected(self):
        self.assertEqual(self.gate(proof(1.501))['status'],'HOLD')

    def test_accumulated_drift_exactly_reaches_1500_not_rounded_into_pass(self):
        w=proof();w['max_drift_ppm']=1000
        r=self.gate(w,wall=101.,mono=2000000000)
        self.assertEqual(r['clock_uncertainty_bound_seconds'],1.5)
        self.assertEqual(r['status'],'HOLD')

    def test_unknown_drift_is_hold_even_with_admitted_document(self):
        for missing in (None,math.nan,True):
            w=proof();w['max_drift_ppm']=missing
            # Nonfinite canonical JSON itself is invalid and must not pass.
            if missing is not None and type(missing) is float:
                w['proof_sha256']='f'*64
                self.assertNotEqual(utc_gate(w,wall=100,mono=1000000000,epoch='test-epoch',reviewed_proof_hashes={'f'*64})['status'],'UTC_BOUND_VERIFIED')
            else:self.assertEqual(self.gate(w)['status'],'HOLD')

    def test_counter_calibration_and_drift_claims_are_mandatory(self):
        for key in ('counter_calibrated','maximum_future_drift_proved','counter_calibration_proof_sha256','drift_proof_sha256'):
            w=proof();w.pop(key)
            self.assertEqual(self.gate(w)['status'],'HOLD')

    def test_absent_unreviewed_or_synthetic_witness_is_hold(self):
        self.assertEqual(utc_gate(None,wall=100,mono=1,epoch='x')['status'],'HOLD')
        w=proof();pin(w)
        self.assertEqual(utc_gate(w,wall=100,mono=1000000000,epoch='test-epoch')['status'],'HOLD')
        w['synthetic']=True
        self.assertEqual(self.gate(w)['status'],'HOLD')

    def test_v1_not_silently_promoted_and_v1_numeric_limit_unchanged(self):
        w=proof();p=pin(w)
        self.assertEqual(v1_gate(w,wall=100,mono=1000000000,epoch='test-epoch',reviewed_proof_hashes=p)['status'],'HOLD')
        w.pop('causality_version')
        self.assertEqual(self.gate(w)['status'],'HOLD')

    def test_tampered_admitted_attestation_is_fail(self):
        w=proof();p=pin(w);w['absolute_error_seconds']=0
        self.assertEqual(utc_gate(w,wall=100,mono=1000000000,epoch='test-epoch',reviewed_proof_hashes=p)['status'],'FAIL')

    def test_error_budget_components_cannot_be_hidden(self):
        w=proof();w['error_budget_seconds']['transfer_and_timestamping']=.01
        self.assertEqual(self.gate(w)['status'],'FAIL')
        w=proof();w.pop('error_budget_seconds')
        self.assertEqual(self.gate(w)['status'],'HOLD')

    def test_invalid_or_negative_clock_fields(self):
        for key,value in [('absolute_error_seconds',-1),('max_drift_ppm',-1),('reference_mono_ns',True)]:
            w=proof();w[key]=value
            self.assertEqual(self.gate(w)['status'],'FAIL')

    def test_expired_calibration_and_reboot_epoch_hold(self):
        self.assertEqual(self.gate(proof(),mono=200000000000)['status'],'HOLD')
        self.assertEqual(self.gate(proof(),epoch='after-reboot')['status'],'HOLD')

    def test_wall_residual_contributes_to_total_uncertainty(self):
        result=self.gate(proof(),wall=100.002)
        self.assertEqual(result['clock_uncertainty_bound_seconds'],1.501)
        self.assertEqual(result['status'],'HOLD')

    def test_unclosed_candle_rejected(self):
        self.assertEqual(self.causal(proof(),closed=100.1)['status'],'FAIL')

    def test_close_inside_uncertainty_margin_rejected(self):
        r=self.causal(proof(),closed=99.)
        self.assertEqual(r['status'],'FAIL')
        self.assertIn('CANDLE_FINALITY_INSIDE_CLOCK_UNCERTAINTY',r['reasons'])

    def test_receipt_after_decision_cannot_use_new_1500ms_slack(self):
        r=self.causal(proof(),received=100.501)
        self.assertEqual(r['status'],'FAIL')
        self.assertIn('INPUT_RECEIVED_AFTER_DECISION',r['reasons'])

    def test_monotonic_future_input_is_rejected(self):
        self.assertEqual(self.causal(proof(),d_mono=999999999)['status'],'FAIL')

    def test_late_unknown_context_digest_rejected(self):
        self.assertEqual(self.causal(proof(),used_digests=['f'*64])['status'],'FAIL')

    def test_archive_not_new_oos(self):
        self.assertEqual(self.causal(proof(),source_mode='HISTORICAL_ARCHIVE')['status'],'HOLD')

    def test_receipt_outside_calibration_hold_even_if_decision_inside(self):
        self.assertEqual(self.causal(proof(wall=100.5,mono=1500000000))['status'],'HOLD')

    def test_decision_can_cross_ceiling_after_valid_receipt(self):
        w=proof();w['max_drift_ppm']=4000
        self.assertEqual(self.causal(w)['status'],'HOLD')

    def test_latency_is_separate_from_clock_uncertainty(self):
        r=timing_diagnostics(received_mono_ns=1,decision_mono_ns=10_000_000_001,
                             alert_sent_mono_ns=70_000_000_001)
        self.assertEqual(r['receipt_to_decision_seconds'],10)
        self.assertEqual(r['decision_to_alert_seconds'],60)
        self.assertIsNone(r['source_to_receipt_delay_seconds'])
        with self.assertRaises(ValueError):
            timing_diagnostics(received_mono_ns=2,decision_mono_ns=1)

    def test_no_forward_admission_or_automatic_activation(self):
        self.assertEqual(forward_gate()['status'],'NOT_ARMED')
        c=self.causal(proof())
        r=forward_gate(owner_scope={'causality_version':VERSION},causality=c,durable_storage=True,protocol_pinned=True)
        self.assertEqual(r['status'],'READY_FOR_SEPARATE_OWNER_ACTIVATION')
        self.assertFalse(r['collector_started'])
        c['version']='PROSPECTIVE_RECEIPT_CAUSALITY_V1'
        self.assertEqual(forward_gate(owner_scope={'causality_version':VERSION},causality=c,durable_storage=True,protocol_pinned=True)['status'],'NOT_ARMED')
