import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
from zs_smart_gate.pilot020 import WS_URL,SYMBOLS,REST_PLAN,Budget,canonical,sha,validate_manifest,permit,stream_payload,decision
from zs_smart_gate.pilot020_runner import Journal,run_capture,verify_chunks
from zs_smart_gate.pilot020_native import Store,load_review,on_d,credentials
from zs_smart_gate.pilot020_io import WireCapSocket,WebSocketOnce


def manifest():
    t=1800000000
    return dict(version='BOUNDED_MANUAL_FIELD_020_V1',symbols=list(SYMBOLS),ws_url=WS_URL,
        rest_host='data-api.binance.vision',ws_connections=1,ws_seconds=720,ws_messages=1200,ws_raw_bytes=2097152,
        rest_GETs=6,rest_weight_cap=24,rest_seconds_per_response=5,rest_bytes_per_response=65536,rest_total_bytes=262144,
        study_bytes=3145728,research_total_cap_bytes=10485760,reconnect=False,trading=False,publishable=False,
        owner_windows_only=True,frozen_at=t-3600,target_close=t,start_at=t-240,end_at=t+120,expires_at=t-3600+86400,
        code_sha='c'*40,plan_sha256='a'*64,host_fingerprint_sha256='b'*64,
        study_id='zs03-020-'+str(t),evidence_branch='evidence-stage03-020',rest_plan=[dict(path=p,params=q,weight=w) for p,q,w in REST_PLAN])


def review(m):
    return dict(decision='020_FIELD_PREFLIGHT_PASS',review_role='PM 1.3',code_sha=m['code_sha'],
        manifest_sha256=sha(m),plan_sha256=m['plan_sha256'],study_id=m['study_id'],
        host_fingerprint_sha256=m['host_fingerprint_sha256'],native_github_storage_pass=True,
        source_rights_and_quota_pass=True,single_event_scope_pass=True,comment_id=123,
        independence_statement='PM_REVIEW_NOT_EXECUTOR')


def raw_kline(symbol='BTCUSDT',t=1800000000,closed=True):
    return canonical(dict(stream=symbol.lower()+'@kline_5m',data=dict(e='kline',E=t*1000+1,s=symbol,
        k=dict(t=(t-300)*1000,T=t*1000-1,s=symbol,i='5m',x=closed,o='100',h='102',l='99',c='101',v='10',q='1000'))))


class Clock:
    def __init__(self,m):self.wall=m['target_close']-60;self.mono=100000000000
    def time(self):return self.wall
    def monotonic(self):return self.mono/1e9
    def monotonic_ns(self):return self.mono
    def time_ns(self):return int(self.wall*1e9)
    def advance(self,n):self.wall+=n;self.mono+=int(n*1e9)


class Memory:
    def __init__(self):self.files={};self.fail=False
    def create(self,name,body):
        if self.fail:raise OSError('STORAGE_OFFLINE')
        if name in self.files:raise ValueError('DUPLICATE_NO_RETRY')
        self.files[name]=body


class Stream:
    def __init__(self,m,c,raws=None):self.m=m;self.c=c;self.budget=Budget();self.raws=list(raws or [raw_kline(s,m['target_close']) for s in SYMBOLS])
    def connect(self):self.budget.connect()
    def receive(self):
        if self.c.wall<self.m['target_close']:self.c.advance(self.m['target_close']-self.c.wall+.01)
        self.c.advance(.01)
        if not self.raws:raise OSError('DISCONNECTED_NO_RECONNECT')
        raw=self.raws.pop(0);self.budget.wire_received(len(raw));self.budget.message()
        return raw,self.c.monotonic_ns(),self.c.time_ns()
    def close(self):pass


def responses(m,c,entries,on_attempt):
    values=[]
    for path,params,w in entries:
        on_attempt((path,params,w));sent=c.monotonic_ns();c.advance(.01)
        if path.endswith('/time'):data=dict(serverTime=int(c.wall*1000))
        elif path.endswith('/bookTicker'):data=dict(symbol=params['symbol'],bidPrice='100',askPrice='100.1')
        else:data=dict(symbol=params['symbol'],quoteVolume='20000000')
        raw=canonical(data)
        values.append(dict(path=path,params=params,weight=w,status=200,elapsed_seconds=.01,
            sent_mono_ns=sent,received_mono_ns=c.monotonic_ns(),raw_base64=base64.b64encode(raw).decode()))
    return values


class Pilot020Tests(unittest.TestCase):
    def options(self,m):return dict(now=m['start_at']+1,code_sha=m['code_sha'],host_fingerprint=m['host_fingerprint_sha256'],windows=True)
    def simulate(self,raws=None,rest_mutator=None,fail=False,cancel=False):
        m=manifest();c=Clock(m);s=Stream(m,c,raws);store=Memory();store.fail=fail
        with tempfile.TemporaryDirectory() as tmp:
            j=Journal(tmp,store,m['study_id'])
            def rest(entries,*,on_attempt):
                values=responses(m,c,entries,on_attempt)
                if rest_mutator:rest_mutator(values)
                return values
            report=run_capture(m,journal=j,stream=s,rest=rest,clock=c,cancel=lambda:cancel)
            return report,store
    def test_fixed_manifest_and_planned_weight_10(self):
        self.assertTrue(validate_manifest(manifest()));self.assertEqual(sum(w for p,q,w in REST_PLAN),10)
    def test_missing_pm_review_blocks(self):
        m=manifest()
        with self.assertRaisesRegex(ValueError,'PREFLIGHT_BLOCKED'):permit(m,{},**self.options(m))
    def test_synthetic_review_exercises_exact_gate_only(self):
        m=manifest();self.assertTrue(permit(m,review(m),**self.options(m)))
    def test_changed_code_plan_manifest_or_host_not_admitted(self):
        m=manifest()
        for key in ('code_sha','manifest_sha256','plan_sha256','host_fingerprint_sha256'):
            r=review(m);r[key]='f'*len(r[key])
            with self.assertRaises(ValueError):permit(m,r,**self.options(m))
    def test_ci_or_nonwindows_cannot_field_capture(self):
        m=manifest()
        for windows,ci in [(False,False),(True,True)]:
            a=self.options(m);a.update(windows=windows,ci=ci)
            with self.assertRaises(ValueError):permit(m,review(m),**a)
    def test_no_old_target_or_rollover(self):
        m=manifest();a=self.options(m);a['now']=m['target_close']
        with self.assertRaises(ValueError):permit(m,review(m),**a)
    def test_early_window_not_authorized(self):
        m=manifest();a=self.options(m);a['now']=m['start_at']-1
        with self.assertRaises(ValueError):permit(m,review(m),**a)
    def test_cannot_increase_any_cap_or_change_market_scope(self):
        for key in ('ws_connections','ws_seconds','ws_messages','ws_raw_bytes','rest_GETs','rest_weight_cap','study_bytes'):
            m=manifest();m[key]+=1
            with self.assertRaises(ValueError):validate_manifest(m)
        m=manifest();m['symbols'].append('SOLUSDT')
        with self.assertRaises(ValueError):validate_manifest(m)
    def test_frozen_time_must_be_at_least_ten_minutes_before_target(self):
        m=manifest();m['frozen_at']=m['target_close']-599;m['expires_at']=m['frozen_at']+86400
        with self.assertRaises(ValueError):validate_manifest(m)
    def test_no_reconnect_or_seventh_get(self):
        b=Budget();b.connect()
        with self.assertRaises(ValueError):b.connect()
        for e in REST_PLAN:b.request(e)
        with self.assertRaises(ValueError):b.request(REST_PLAN[0])
    def test_rest_endpoint_or_symbol_undeclared_is_rejected(self):
        b=Budget()
        with self.assertRaises(ValueError):b.request(('/api/v3/klines',{},2))
    def test_exact_byte_message_caps(self):
        b=Budget();b.wire_received(2097152)
        with self.assertRaises(ValueError):b.wire_received(1)
        for i in range(1200):b.message()
        with self.assertRaises(ValueError):b.message()
    def test_rest_bad_status_deadline_and_sizes_stop(self):
        for status,n,elapsed in [(403,1,.1),(418,1,.1),(429,1,.1),(200,65537,.1),(200,1,5)]:
            with self.assertRaises(ValueError):Budget().response(status,b'x'*n,elapsed)
        b=Budget();b.response(200,b'x'*65536,.1);b.response(200,b'x'*65536,.1);b.response(200,b'x'*65536,.1);b.response(200,b'x'*65536,.1)
        with self.assertRaises(ValueError):b.response(200,b'x',.1)
    def test_target_final_and_forming_are_distinct(self):
        s,c,t=stream_payload(raw_kline(),manifest()['target_close']);self.assertEqual(t,'TARGET_SOURCE_CLOSED')
        self.assertIsNone(stream_payload(raw_kline(closed=False),manifest()['target_close'])[1])
    def test_wrong_symbol_and_truncated_payload_rejected(self):
        for raw in (b'{',raw_kline('SOLUSDT')):
            with self.assertRaises(ValueError):stream_payload(raw,manifest()['target_close'])
    def test_normal_one_event_retains_context_hold_and_no_signal(self):
        r,s=self.simulate();self.assertEqual(r['GET_attempts'],6);self.assertEqual(r['ws_connection_attempts'],1)
        self.assertEqual(r['execution_status'],'SYNTHETIC_CAPTURE_SIMULATION_ONLY')
        self.assertEqual(r['result']['field_relative_status'],'FIELD_RELATIVE_CAUSALITY_CANDIDATE')
        self.assertEqual(r['result']['status'],'HOLD');self.assertIsNone(r['result']['score'])
        self.assertFalse(r['result']['publishable']);self.assertFalse(r['result']['OOS_QUALIFIED'])
        self.assertTrue(r['result']['data_fresh']);self.assertEqual(set(r['result']['per_symbol']),set(SYMBOLS))
    def test_all_raw_claim_chain_survives_storage_replay(self):
        r,s=self.simulate();chunks=[json.loads(v) for k,v in sorted(s.files.items()) if k.startswith('receipts/')]
        self.assertGreater(verify_chunks(chunks)['records'],8)
        chunks[0]['events'][0]['payload']['phase']='FAKE'
        with self.assertRaises(ValueError):verify_chunks(chunks)
    def test_storage_failure_before_socket_is_zero_connections(self):
        r,s=self.simulate(fail=True);self.assertEqual(r['ws_connection_attempts'],0);self.assertEqual(r['GET_attempts'],0)
    def test_cancel_before_socket_is_zero_connections(self):
        r,s=self.simulate(cancel=True);self.assertEqual(r['ws_connection_attempts'],0)
    def test_source_disconnect_holds_no_rest_retry(self):
        r,s=self.simulate(raws=[raw_kline()]);self.assertEqual(r['GET_attempts'],0);self.assertEqual(r['ws_connection_attempts'],1)
    def test_open_only_never_reaches_rest(self):
        r,s=self.simulate(raws=[raw_kline(closed=False)]);self.assertEqual(r['GET_attempts'],0)
    def test_inconsistent_source_time_references_hold(self):
        def change(v):
            v[1]['raw_base64']=base64.b64encode(canonical(dict(serverTime=1800000000000+99999))).decode()
        r,s=self.simulate(rest_mutator=change);self.assertEqual(r['result']['field_relative_status'],'HOLD')
    def test_input_after_decision_or_wrong_epoch_never_qualifies(self):
        for mutate in ('late','epoch'):
            def change(v):
                if mutate=='late':v[-1]['received_mono_ns']=10**30
                else:v[-1]['epoch']='wrong'
            # Epoch is attached by engine, so verify epoch directly on raw record.
            if mutate=='late':self.assertEqual(self.simulate(rest_mutator=change)[0]['result']['field_relative_status'],'HOLD')
        m=manifest();raw=raw_kline();r=dict(kind='ws',raw_base64=base64.b64encode(raw).decode(),raw_sha256=hashlib.sha256(raw).hexdigest(),claimed_mono_ns=1,sent_mono_ns=2,received_mono_ns=3,epoch='wrong')
        self.assertEqual(decision(m,[r],decision_mono_ns=4,continuity_ok=True)['field_relative_status'],'HOLD')
    def test_stale_book_blocks(self):
        def change(v):v[2]['sent_mono_ns']-=11*10**9
        self.assertEqual(self.simulate(rest_mutator=change)[0]['result']['field_relative_status'],'HOLD')
    def test_http_failure_preserves_arrived_raw_and_stops(self):
        def change(v):v[0]['status']=429
        r,s=self.simulate(rest_mutator=change);self.assertEqual(r['result']['field_relative_status'],'HOLD')
        chunks=[json.loads(v) for k,v in s.files.items() if k.startswith('receipts/')]
        self.assertTrue(any(e['kind']=='RAW_REST' for c in chunks for e in c['events']))
    def test_duplicate_final_is_not_an_extra_sample(self):
        r,s=self.simulate(raws=[raw_kline(),raw_kline()]);self.assertEqual(r['GET_attempts'],0)
    def test_serialized_capacity_fails_before_source_read(self):
        m=manifest();c=Clock(m);s=Stream(m,c)
        with tempfile.TemporaryDirectory() as tmp:
            r=run_capture(m,journal=Journal(tmp,Memory(),m['study_id'],initial_bytes=3000000),stream=s,
                rest=lambda *a,**k:[],clock=c)
            self.assertEqual(r['GET_attempts'],0);self.assertEqual(r['ws_data_messages'],0)
    def test_corrupt_or_missing_chunks_rejected(self):
        with self.assertRaises(ValueError):verify_chunks([dict(chunk=1,events=[],last='0'*64)])
    def test_review_needs_machine_readable_external_pins(self):
        with self.assertRaises(ValueError):load_review(dict(id=1,user={'login':'scannercrypto0-gif'},body='020_FIELD_PREFLIGHT_PASS'))
    def test_no_credential_manager_fallback_even_on_missing_token(self):
        with patch.dict(os.environ, {'ZS020_GITHUB_TOKEN':''}):
            with patch('subprocess.run', side_effect=AssertionError('GIT_CREDENTIAL_ACCESS_FORBIDDEN')):
                with self.assertRaisesRegex(ValueError,'NO_EXPLICIT_TOKEN'):credentials()

    def test_d_drive_policy(self):
        self.assertTrue(on_d('D:\\project'));self.assertFalse(on_d('C:\\project'))
    def test_wire_guard_never_reads_past_remaining(self):
        class Sock:
            def recv(self,n):return b'x'*n
        b=Budget();b.wire_received(2097150);s=WireCapSocket(Sock(),b)
        self.assertEqual(s.recv(500),b'xx')
        with self.assertRaises(ValueError):s.recv(1)
    def test_empty_approval_never_converted_to_self_pass(self):
        m=manifest();r=review(m);r['decision']='020_FIELD_PREFLIGHT_PENDING'
        with self.assertRaises(ValueError):permit(m,r,**self.options(m))

    def test_lifecycle_fault_after_receive_preserves_arrived_raw(self):
        m=manifest();c=Clock(m);s=Stream(m,c);store=Memory();checks=[]
        def health():
            checks.append(1)
            if len(checks)==3:raise ValueError('SIMULATED_SLEEP_OR_JUMP')
        with tempfile.TemporaryDirectory() as tmp:
            r=run_capture(m,journal=Journal(tmp,store,m['study_id']),stream=s,rest=lambda *a,**k:[],clock=c,health=health)
        chunks=[json.loads(v) for k,v in store.files.items() if k.startswith('receipts/')]
        self.assertTrue(any(e['kind']=='RAW_WS' for c in chunks for e in c['events']))
        self.assertEqual(r['GET_attempts'],0)

    def test_elapsed_target_before_connect_is_zero_source(self):
        m=manifest();c=Clock(m);c.advance(61);s=Stream(m,c)
        with tempfile.TemporaryDirectory() as tmp:
            r=run_capture(m,journal=Journal(tmp,Memory(),m['study_id']),stream=s,rest=lambda *a,**k:[],clock=c)
        self.assertEqual(r['ws_connection_attempts'],0)

    def test_idle_source_hard_deadline_stops_without_rest(self):
        m=manifest();c=Clock(m)
        class Idle(Stream):
            def receive(self):self.c.advance(30);return None,self.c.monotonic_ns(),self.c.time_ns()
        s=Idle(m,c)
        with tempfile.TemporaryDirectory() as tmp:
            r=run_capture(m,journal=Journal(tmp,Memory(),m['study_id']),stream=s,rest=lambda *a,**k:[],clock=c)
        self.assertEqual(r['GET_attempts'],0);self.assertIn('HARD_END',str(r['errors']))

    def test_native_store_readback_failure_stops_and_never_retries_put(self):
        class T:
            def __init__(self):self.puts=0;self.reads=0
            def get_file(self,*a):self.reads+=1;return None
            def put_file(self,*a):self.puts+=1;return True
        t=T();s=Store(t,manifest())
        with self.assertRaisesRegex(ValueError,'READBACK_UNKNOWN'):s.create('probe.json',b'{}')
        self.assertEqual(t.puts,1)

    def test_partial_batch_counts_only_dispatched_attempts(self):
        m=manifest();c=Clock(m);s=Stream(m,c)
        def rest(entries,*,on_attempt):
            on_attempt(entries[0]);return dict(results=[],unavailable=[dict(index=0,reason='TIMEOUT')])
        with tempfile.TemporaryDirectory() as tmp:
            r=run_capture(m,journal=Journal(tmp,Memory(),m['study_id']),stream=s,rest=rest,clock=c)
        self.assertEqual(r['GET_attempts'],1);self.assertEqual(r['declared_weight_attempted'],1)
        self.assertEqual(r['result']['field_relative_status'],'HOLD')

    def test_future_record_flag_is_not_masked_by_generic_error(self):
        m=manifest();raw=raw_kline();r=dict(kind='ws',raw_base64=base64.b64encode(raw).decode(),raw_sha256=hashlib.sha256(raw).hexdigest(),claimed_mono_ns=1,sent_mono_ns=2,received_mono_ns=5,epoch=m['study_id'])
        self.assertFalse(decision(m,[r],decision_mono_ns=4,continuity_ok=True)['received_before_decision'])
