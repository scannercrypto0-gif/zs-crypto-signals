import json
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zs_smart_gate.windows_operations import (
    d_path, storage_audit, ENV_DIRS, verify_deployment, canonical_sha,
    load_config, write_bounded_result,
)
from zs_smart_gate.windows_adapter import research_fixture, live_gate, CUTOFF
from zs_smart_gate.windows_runner import Event, Scope, ClockProof
from test_stage03b1 import FixtureTransport, ANCHOR, NOW, Horizon


class StorageTests(unittest.TestCase):
    def test_d_and_canonical_target(self):
        self.assertEqual(str(d_path('D:/safe',resolver=lambda p:p)),str(Path('D:/safe')))
        for value in ('C:/bad','relative','D:relative','//host/share','\\\\?\\D:\\raw'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                d_path(value,resolver=lambda p:p)
        with self.assertRaises(ValueError): d_path('D:/junction',resolver=lambda p:'C:/escape')
        with self.assertRaises(FileNotFoundError):
            d_path('D:/absent',resolver=lambda p: (_ for _ in ()).throw(FileNotFoundError()))

    def test_temp_fallback_rejected(self):
        args=dict(repo='D:/repo',state='D:/state',logs='D:/logs',executable='D:/venv/python.exe',
                  prefix='D:/venv',temp='D:/temp',resolver=lambda p:p)
        env={k:'D:/cache' for k in ENV_DIRS}
        self.assertEqual(storage_audit(**args,environ=env)['status'],'D_ONLY_PROJECT_STORAGE_PASS')
        for key in ENV_DIRS:
            with self.subTest(key=key), self.assertRaises(ValueError):
                storage_audit(**args,environ={**env,key:'C:/fallback'})

    def test_config_changes_and_checksum(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'src').mkdir(); (root/'scripts').mkdir()
            source=root/'src/example.py'; source.write_text('safe')
            config={'version':1,'revision':'a'*40,'mode':'SIMULATION_ONLY','scope':[],
                    'files':{'src/example.py':hashlib.sha256(source.read_bytes()).hexdigest()}}
            sha=verify_deployment(config,root)
            config_path=root/'config.json'; config_path.write_text(json.dumps(config))
            self.assertEqual(load_config(config_path,sha),config)
            with self.assertRaises(ValueError): load_config(config_path,'f'*64)
            source.write_text('changed')
            with self.assertRaises(ValueError): verify_deployment(config,root)
            source.write_text('safe'); (root/'src/extra.py').write_text('unexpected')
            with self.assertRaises(ValueError): verify_deployment(config,root)

    def test_bounded_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for _ in range(30): write_bounded_result(root,{'mode':'DRY_RUN','http_attempts':0})
            self.assertLessEqual(len(list(root.glob('*.json'))),17)
            with self.assertRaises(ValueError): write_bounded_result(root,{'too_large':'x'*70000})


class AdapterTests(unittest.TestCase):
    def test_live_gate_never_arms_transport(self):
        self.assertIn('FROZEN_03B3_ACTIVE',live_gate(CUTOFF-timedelta(seconds=1)))
        self.assertIn('PM_PINNED_CODE',live_gate(CUTOFF))
        self.assertIn('GITHUB_EVIDENCE_POLICY',live_gate(CUTOFF,pm_accepted=True,timer_verified=True,clock_verified=True))
        self.assertIn('NO_APPROVED_TRANSPORT',live_gate(CUTOFF,pm_accepted=True,timer_verified=True,clock_verified=True,evidence_approved=True))

    def test_accepted_mtf_core_fixture_no_http(self):
        # Fixture server clock is 12:15; use a deliberately generous fake proof
        # anchored to 12:00+2 seconds, and move fixture metadata to that instant.
        for horizon, frame in ((Horizon.INTRADAY,'30m'),(Horizon.SWING,'4h')):
            now=ANCHOR+timedelta(seconds=2)
            event=Event('BTCUSDT',frame,ANCHOR)
            transport=FixtureTransport(horizon)
            def getter(path,params=None,*,on_attempt=None):
                payload,meta=transport(path,params,on_attempt=on_attempt)
                delta=(NOW-now).total_seconds()*1000
                meta['t0_local_ms']-=delta; meta['received_local_ms']-=delta
                if path=='/api/v3/time': payload={'serverTime':int(now.timestamp()*1000)}
                return payload,meta
            with patch('socket.socket',side_effect=AssertionError('HTTP forbidden')):
                result=research_fixture(event,Scope((event,)),ClockProof(now,0,.1,.1),
                                        getter=getter,clock=lambda:now,monotonic=lambda:0)
            self.assertEqual(result['status'],'PASS',result)
            self.assertLessEqual(result['fixture_attempts'],8)
            self.assertIsNone(result['signal_id'])
            self.assertEqual(result['score_status'],'SCORE_UNAVAILABLE')

    def test_late_never_dispatches(self):
        event=Event('BTCUSDT','30m',ANCHOR)
        result=research_fixture(event,Scope((event,)),ClockProof(NOW,0,.1,.1),
            getter=lambda *a,**k:self.fail('dispatch'),clock=lambda:NOW,monotonic=lambda:0)
        self.assertEqual(result['status'],'BLOCKED')

    def test_retry_cap(self):
        now=ANCHOR+timedelta(seconds=2)
        event=Event('BTCUSDT','30m',ANCHOR)
        calls=[]
        def getter(path,params=None,*,on_attempt=None):
            for _ in range(20):
                on_attempt(path); calls.append(path)
            self.fail('budget hook failed')
        result=research_fixture(event,Scope((event,)),ClockProof(now,0,.1,.1),
             getter=getter,clock=lambda:now,monotonic=lambda:0)
        self.assertEqual(len(calls),8)
        self.assertEqual(result['status'],'BLOCKED')
