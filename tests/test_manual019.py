import copy
import hashlib
import json
import unittest
from datetime import datetime,timezone
from zs_smart_gate.manual_alert019 import VERSION,evaluate,digest
from zs_smart_gate.manual_sensitivity019 import fixture,scenarios,comparison,rechain,change_raw,pack_fixture,unpack_fixture
from zs_smart_gate.evidence_journal import canonical_bytes,SingleStudyJournal
from zs_smart_gate.github_evidence_backend import GitHubEvidenceBackend
from zs_smart_gate.stage04_evidence_packet import make_record,prepare_manifest,persist_packet,restore_from_remote
from test_github_evidence_backend import MockContentsTransport

PASS_CASES={'ideal_wall','linked_correction','unconfirmed_latest_pivot',
    *(f'constant_wall_offset_{n:+g}s' for n in (-5,-3,-1.5,1.5,3,5))}


class Manual019Tests(unittest.TestCase):
    def test_no_absolute_witness_needed_for_relative_synthetic_candidate(self):
        r=evaluate(**fixture());self.assertEqual(r['status'],'RESEARCH_CAUSAL_ORDER_PASS_CANDIDATE')
        self.assertTrue(r['source_closed_confirmed']);self.assertTrue(r['received_before_decision']);self.assertTrue(r['data_fresh'])
        self.assertEqual(r['ABSOLUTE_UTC_PIT'],'HOLD');self.assertFalse(r['publishable']);self.assertFalse(r['OOS_QUALIFIED'])

    def test_eth_uses_same_explicit_gates(self):
        self.assertEqual(evaluate(**fixture('ETHUSDT'))['status'],'RESEARCH_CAUSAL_ORDER_PASS_CANDIDATE')

    def test_wall_offsets_do_not_change_eligible_inputs_or_indicators(self):
        rows=comparison()['cases']
        for r in rows:
            if not r['case'].startswith('constant_wall'):continue
            self.assertFalse(r['input_eligibility_changed']);self.assertFalse(r['decision_state_changed'])
            self.assertFalse(r['indicators_changed_when_defined'])

    def test_no_input_after_decision_even_one_nanosecond(self):
        r=evaluate(**scenarios()['future_by_one_nanosecond'])
        self.assertIn('INPUT_RECEIVED_AFTER_DECISION',r['reasons']);self.assertIsNone(r['indicators'])

    def test_unconfirmed_last_pivot_excluded(self):
        f=scenarios()['unconfirmed_latest_pivot'];r=evaluate(**f)
        self.assertFalse(r['indicators']['unconfirmed_latest_pivot_used'])
        last=max(x['declared_close_ms'] for x in r['inputs'] if x['frame']=='5m')
        self.assertNotIn(last,r['indicators']['confirmed_pivot_closes_ms'])

    def test_old_history_is_context_not_claim_of_fresh_current_candle(self):
        r=evaluate(**fixture())
        self.assertTrue(any(x['data_fresh'] is False and x['freshness_role']=='HISTORICAL_CLOSED_INPUT' for x in r['inputs']))
        self.assertTrue(r['data_fresh'])

    def test_unknown_delivery_bound_never_gives_full_quality(self):
        r=evaluate(**scenarios()['unknown_delivery_bound']);self.assertIsNone(r['indicators']);self.assertIsNone(r['score'])
        self.assertIn('INPUT_STALE_OR_FRESHNESS_UNKNOWN',r['reasons'])

    def test_close_plus_five_seconds_without_source_marker_still_unknown(self):
        f=scenarios()['missing_finality'];f['decision_mono_ns']+=5*10**9;f['decision_wall_ms']+=5000
        self.assertFalse(evaluate(**f)['source_closed_confirmed'])

    def test_timezone_offset_profile_is_not_silently_utc(self):
        f=fixture()
        for e in f['events']:
            if e['frame']=='liquidity':continue
            p=copy.deepcopy(f['profiles'][e['profile_sha256']]);p['timezone']='UTC+8'
            sha=digest(p);f['profiles'][sha]=p;f['admitted_profiles'].add(sha);e['profile_sha256']=sha
        rechain(f)
        self.assertIn('FINALITY_UNKNOWN_NO_QUALIFIED_SOURCE_MARKER',evaluate(**f)['reasons'])

    def test_parent_child_quote_volume_mismatch_rejected(self):
        f=fixture();e=next(e for e in f['events'] if e['frame']=='30m')
        change_raw(f,e,lambda p:p['k'].update(q='1'));rechain(f)
        self.assertIn('MISSING_DELAYED_OR_INCONSISTENT_PARENT_CHILD_CONTEXT',evaluate(**f)['reasons'])

    def test_source_bar_identity_cannot_be_substituted(self):
        f=fixture();e=next(e for e in f['events'] if e['frame']=='5m')
        change_raw(f,e,lambda p:p['k'].update(t=p['k']['t']+300000));rechain(f)
        self.assertIn('SOURCE_FRAME_OR_TIME_SCHEMA',evaluate(**f)['reasons'])

    def test_superseded_raw_cannot_be_selected(self):
        f=scenarios()['linked_correction'];f['used_digests'].append(f['events'][-2]['digest'])
        self.assertIn('FUTURE_UNKNOWN_OR_SUPERSEDED_INPUT',evaluate(**f)['reasons'])

    def test_epoch_change_rejects_history_stitch(self):
        f=fixture();f['events'][-1]['epoch']='after-reboot';rechain(f)
        self.assertIn('CHAIN_SEQUENCE_STUDY_OR_EPOCH_MISMATCH',evaluate(**f)['reasons'])

    def test_default_profile_anchor_and_readback_registries_block(self):
        f=fixture()
        for key in ('admitted_profiles','admitted_epoch_anchors','restored_digests'):f.pop(key)
        self.assertEqual(evaluate(**f)['status'],'HOLD')

    def test_missing_positive_lifecycle_coverage_holds(self):
        f=fixture();f['health_records']=[]
        self.assertIn('LIFECYCLE_COVERAGE_UNKNOWN',evaluate(**f)['reasons'])

    def test_watchdog_gap_is_not_silently_treated_as_active(self):
        f=fixture();del f['health_records'][2:5]
        self.assertIn('LIFECYCLE_GAP_OR_UNVERIFIED_STATE',evaluate(**f)['reasons'])

    def packet(self,transport):
        result=evaluate(**fixture());study='zs03-019-synthetic';at='2026-11-04T00:00:00+00:00'
        records={'decision':make_record(study_id=study,event_id='decision',record_type='decision_context',
            source_id='SYNTHETIC_ONLY',received_at=at,available_at=at,payload=result)}
        records['source']=make_record(study_id=study,event_id='source',record_type='source_snapshot',
            source_id='SYNTHETIC_ONLY',received_at=at,available_at=at,payload=pack_fixture(fixture()))
        manifest=prepare_manifest(study,records,created_at=at)
        journal=SingleStudyJournal(study,GitHubEvidenceBackend(study,branch='evidence-019-test',transport=transport,enabled=True),lambda:datetime.now(timezone.utc))
        r=persist_packet(journal,manifest,records)
        return r,journal,manifest,records

    def test_durable_readback_restore_preserves_relative_vs_absolute_states(self):
        transport=MockContentsTransport();r,j,m,records=self.packet(transport);self.assertTrue(r.ok)
        restored=restore_from_remote(study_id=j.study_id,branch='evidence-019-test',transport=transport,expected_manifest_sha256=r.manifest_sha256)
        self.assertTrue(restored.ok)
        result=json.loads(transport.files[f'studies/{j.study_id}/receipts/decision.json'])['payload']['payload']
        self.assertEqual(result['version'],VERSION);self.assertEqual(result['ABSOLUTE_UTC_PIT'],'HOLD')
        source=json.loads(transport.files[f'studies/{j.study_id}/receipts/source.json'])['payload']['payload']
        self.assertEqual(canonical_bytes(evaluate(**unpack_fixture(source))),canonical_bytes(result))
        self.assertFalse(result['publishable']);self.assertFalse(persist_packet(j,m,records).ok)

    def test_crash_after_claim_does_not_produce_evidence_or_allow_retry(self):
        transport=MockContentsTransport();put=transport.put_file
        def fail(path,*args):
            if '/receipts/' in path:raise OSError('SIMULATED_CRASH')
            return put(path,*args)
        transport.put_file=fail;r,j,m,records=self.packet(transport)
        self.assertFalse(r.ok);self.assertFalse(persist_packet(j,m,records).ok)

    def test_storage_offline_never_yields_durability(self):
        transport=MockContentsTransport();transport.fail_status=503
        self.assertFalse(self.packet(transport)[0].ok)


def case_test(name):
    def check(self):
        result=evaluate(**scenarios()[name])
        self.assertEqual(result['status'],'RESEARCH_CAUSAL_ORDER_PASS_CANDIDATE' if name in PASS_CASES else 'HOLD')
        self.assertEqual(result['ABSOLUTE_UTC_PIT'],'HOLD');self.assertFalse(result['publishable'])
        if name not in PASS_CASES:self.assertIsNone(result['indicators'])
    return check


for _name in scenarios():
    setattr(Manual019Tests,'test_sensitivity_'+_name.replace('.','p').replace('+','plus').replace('-','minus'),case_test(_name))
