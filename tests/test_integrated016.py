import copy
import hashlib
import json
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from dataclasses import replace
from zs_smart_gate.integrated_research016 import evaluate,aggregate,liquidity
from zs_smart_gate.evidence_journal import canonical_bytes,SingleStudyJournal
from zs_smart_gate.github_evidence_backend import GitHubEvidenceBackend
from zs_smart_gate.stage04_evidence_packet import make_record,prepare_manifest,persist_packet,restore_from_remote
from test_github_evidence_backend import MockContentsTransport

def fixture():
    start=1735689600000
    rows=[[start+i*300000,'100','102','99','101','10',start+(i+1)*300000-1,'1000',10,'5','500','0']for i in range(60)]
    # Keep child opens continuous, since strict source reconciliation rejects gaps.
    for i,r in enumerate(rows):
        if i:r[1]=rows[i-1][4]
    return dict(symbol='BTCUSDT',rows=rows,received_ms=rows[-1][6]+101,provenance={'mode':'SYNTHETIC'})

def decide(data=None,**kwargs):
    data=data or fixture();raw=canonical_bytes(data)
    return evaluate(raw,expected_sha256=hashlib.sha256(raw).hexdigest(),decision_ms=data['received_ms']+500,**kwargs)

class Integrated016Tests(unittest.TestCase):
    def setUp(self):
        self.data=fixture();self.decision=decide(self.data)
    def test_source_to_frames_to_24_features_and_explicit_blocked_decision(self):
        d=self.decision
        self.assertEqual(d['status'],'BLOCKED_RESEARCH_ONLY');self.assertEqual(d['reconciliation']['INTRADAY:1'],'PASS')
        self.assertEqual(d['reconciliation']['SWING:1'],'PASS')
        self.assertEqual(sum(len(x)for x in d['features'].values()),24)
        self.assertIsNone(d['features']['INTRADAY:1']['I6']['value'])
        self.assertIsNone(d['features']['SWING:1']['S6']['value'])
        self.assertIsNone(d['score']);self.assertFalse(d['publishable'])
    def test_modified_raw_fails_before_calculation(self):
        with self.assertRaisesRegex(ValueError,'RAW_SHA_CONFLICT'):
            evaluate(b'bad',expected_sha256='0'*64,decision_ms=1)
    def test_forming_candle_explicitly_rejected(self):
        self.data['received_ms']=self.data['rows'][-1][6]-100
        with self.assertRaisesRegex(ValueError,'CANDLE_NOT_FINAL'):decide(self.data)
    def test_late_source_context_rejected(self):
        raw=canonical_bytes(self.data)
        with self.assertRaisesRegex(ValueError,'SOURCE_RECEIVED_AFTER_DECISION'):
            evaluate(raw,expected_sha256=hashlib.sha256(raw).hexdigest(),decision_ms=self.data['received_ms']-1)
    def test_explicit_daily_weekly_contexts_are_accepted_only_when_already_received(self):
        def row(start,duration):return[start,'100','102','99','101','10',start+duration-1,'1000',10,'5','500','0']
        self.data['contexts']={
            '1d':dict(received_ms=self.data['received_ms'],rows=[row(1735603200000,86400000)]),
            '1w':dict(received_ms=self.data['received_ms'],rows=[row(1734912000000,604800000)])}
        d=decide(self.data);self.assertEqual(d['frames']['1d'],1);self.assertEqual(d['frames']['1w'],1)
        self.assertIsNotNone(d['features']['SWING:1']['S4']['value'])
        self.data['contexts']['1w']['received_ms']+=1000
        with self.assertRaisesRegex(ValueError,'CONTEXT_RECEIVED_AFTER_DECISION'):decide(self.data)
    def test_late_parent_context_cannot_be_used(self):
        original=aggregate
        def late(*args):
            values=original(*args)
            if args[1]=='30m':values=[replace(x,available_at=args[2].replace(year=2027))for x in values]
            return values
        with patch('zs_smart_gate.integrated_research016.aggregate',late):
            with self.assertRaises(ValueError):decide()
    def test_gap_and_duplicate_kline_rejected(self):
        self.data['rows'][4]=self.data['rows'][3]
        with self.assertRaisesRegex(ValueError,'KLINE_GAP_OR_DUPLICATE'):decide(self.data)
    def test_price_gaps_do_not_create_an_out_of_unit_normalized_feature(self):
        for i,r in enumerate(self.data['rows']):
            r[1:5]=[str(100+i),str(100+i+.2),str(100+i-.2),str(100+i+.1)]
        d=decide(self.data)
        self.assertIsNone(d['features']['INTRADAY:1']['I3']['value'])
        self.assertEqual(d['features']['INTRADAY:1']['I3']['reason'],'NON_UNIT_BODY_PATH_RATIO_GAPS_NOT_FILLED')
    def test_current_liquidity_cannot_be_backfilled_into_old_data(self):
        with self.assertRaisesRegex(ValueError,'CURRENT_LIQUIDITY_CANNOT_BACKFILL_HISTORY'):
            decide(market={})
    def test_future_path_requires_actual_monotonic_collector_provenance(self):
        with self.assertRaisesRegex(ValueError,'FUTURE_REQUIRES_REAL_RECEIPT'):
            decide(source_mode='NEW_FUTURE_OBSERVATION')
    def test_future_cannot_restart_hash_chain_at_each_decision(self):
        self.data.update(received_mono_ns=1000000000,collector_epoch='real-epoch')
        self.data['provenance']['mode']='NEW_AFTER_FREEZE_LIVE_RECEIPT'
        with self.assertRaisesRegex(ValueError,'FUTURE_REQUIRES_ADMITTED_CONTINUOUS_CHAIN'):
            decide(self.data,source_mode='NEW_FUTURE_OBSERVATION',decision_mono_ns=1500000000)
    def test_liquidity_missing_gapped_future_stale_crossed(self):
        self.assertEqual(liquidity(None,100)['status'],'MISSING')
        base=dict(received_at=99,bid='100',ask='100.1',quote_volume_24h='20000000')
        for bad in [dict(base,received_at=101),dict(base,received_at=80),dict(base,bid='102'),dict(base,gap=True)]:
            self.assertEqual(liquidity(bad,100)['status'],'INVALID')
        self.assertEqual(liquidity(base,100)['status'],'OBSERVED_UNQUALIFIED')
    def packet(self,transport):
        study='zs03-016-offline';at='2026-11-03T00:00:00+00:00'
        raw=canonical_bytes(self.data)
        records={
          'source':make_record(study_id=study,event_id='source',record_type='source_snapshot',source_id='synthetic-test',received_at=at,available_at=at,payload={'fixture_json':raw.decode(),'sha256':hashlib.sha256(raw).hexdigest()}),
          self.decision['event_id']:make_record(study_id=study,event_id=self.decision['event_id'],record_type='decision_context',source_id='synthetic-test',received_at=at,available_at=at,payload=self.decision)}
        manifest=prepare_manifest(study,records,created_at=at)
        journal=SingleStudyJournal(study,GitHubEvidenceBackend(study,branch='evidence-016-test',transport=transport,enabled=True),lambda:datetime.now(timezone.utc))
        result=persist_packet(journal,manifest,records)
        return result,journal,manifest,records
    def test_source_decision_journal_readback_restore_and_recompute(self):
        transport=MockContentsTransport();r,j,m,records=self.packet(transport);self.assertTrue(r.ok)
        restored=restore_from_remote(study_id=j.study_id,branch='evidence-016-test',transport=transport,expected_manifest_sha256=r.manifest_sha256)
        self.assertTrue(restored.ok)
        body=json.loads(transport.files['studies/'+j.study_id+'/receipts/source.json'])['payload']['payload']
        new=evaluate(body['fixture_json'].encode(),expected_sha256=body['sha256'],decision_ms=self.data['received_ms']+500)
        self.assertEqual(canonical_bytes(new),canonical_bytes(self.decision))
        self.assertFalse(persist_packet(j,m,records).ok)
    def test_write_failure_no_success_or_automatic_retry(self):
        transport=MockContentsTransport();transport.fail_status=503
        result,*_=self.packet(transport);self.assertFalse(result.ok)
        self.assertFalse(transport.files)
    def test_crash_or_network_after_claim_cannot_make_durable_decision(self):
        transport=MockContentsTransport()
        original=transport.put_file
        def interrupted(path,*args):
            if '/receipts/'in path:raise OSError('offline')
            return original(path,*args)
        transport.put_file=interrupted
        result,j,*_=self.packet(transport);self.assertFalse(result.ok)
        self.assertFalse(any('/receipts/'in x for x in transport.files))
    def test_conflicting_remote_sha_fails_closed(self):
        transport=MockContentsTransport();transport.conflict_next_put=True
        result,*_=self.packet(transport);self.assertFalse(result.ok)
