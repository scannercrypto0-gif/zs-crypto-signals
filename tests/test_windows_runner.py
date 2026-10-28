import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from zs_smart_gate.windows_runner import (
    UTC, RIYADH, Event, Scope, ClockProof, SimulatedTransport, admission,
    estimate_clock, tick, process_lock, main, ELIGIBLE, LATE,
)

CLOSE = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
EVENT = Event('BTCUSDT', '5m', CLOSE)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.scope = Scope((EVENT,))
        self.now = CLOSE + timedelta(seconds=2)
        self.proof = ClockProof(CLOSE, 0, .1, .1)

    def run_tick(self, **kwargs):
        return tick(kwargs.pop('scope', self.scope), self.directory,
                    kwargs.pop('clock', lambda: self.now),
                    kwargs.pop('monotonic', lambda: 0),
                    kwargs.pop('proof', self.proof), **kwargs)

    def test_boundaries(self):
        for seconds, expected in [(-1,'NOT_YET_CLOSED'),(0,'NOT_YET_CLOSED'),(.1,ELIGIBLE),(29.9,LATE),(31,LATE)]:
            now = CLOSE + timedelta(seconds=seconds)
            proof = ClockProof(now,0,.1,.1)
            self.assertEqual(admission(EVENT,self.scope,now,proof),expected)

    def test_explicit_scope_and_alignment(self):
        for event in (Event('ETHUSDT','5m',CLOSE), Event('BTCUSDT','1m',CLOSE), Event('BTCUSDT','5m',self.now)):
            self.assertEqual(admission(event,Scope((event,)),self.now,self.proof),'UNAPPROVED_SCOPE')
        self.assertEqual(admission(EVENT,Scope(),self.now,self.proof),'UNAPPROVED_SCOPE')

    def test_parent_horizons(self):
        for horizon in ('30m','4h'):
            event=Event('BTCUSDT',horizon,CLOSE)
            self.assertEqual(admission(event,Scope((event,)),self.now,self.proof),ELIGIBLE)

    def test_clock_unknown_skew_stale_nonfinite(self):
        for proof in (None, ClockProof(CLOSE,0,.1,None), ClockProof(CLOSE,2,.1,.1), ClockProof(CLOSE,0,2,1), ClockProof(CLOSE,0,.1,float('nan')), ClockProof(CLOSE-timedelta(minutes=1),0,.1,.1)):
            self.assertEqual(admission(EVENT,self.scope,self.now,proof),'CLOCK_UNTRUSTED')

    def test_independent_exchange_proof(self):
        proof=estimate_clock(CLOSE,CLOSE+timedelta(seconds=.2),CLOSE+timedelta(seconds=.1))
        self.assertAlmostEqual(proof.offset_seconds,0)
        self.assertFalse(proof.trusted(self.now))
        self.assertFalse(proof.simulated)

    def test_aware_utc_riyadh_dst(self):
        self.assertEqual(CLOSE.astimezone(RIYADH).hour,15)
        other=CLOSE.astimezone(timezone(timedelta(hours=-4)))
        self.assertEqual(Event('BTCUSDT','5m',other).id,EVENT.id)
        with self.assertRaises(ValueError): Event('BTCUSDT','5m',CLOSE.replace(tzinfo=None)).id

    def test_no_http_default_and_cli(self):
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            result=self.run_tick()
            self.assertEqual(result['http_attempts'],0)
            self.assertEqual(result['attempts'],0)
            self.assertEqual(main(['--dry-run','--once','--state-dir',str(self.directory)]),0)

    def test_restart_and_interrupted_claim_never_retry(self):
        transport=SimulatedTransport(['TIMEOUT'])
        self.assertEqual(self.run_tick(transport=transport)['events'][0]['status'],LATE)
        result=self.run_tick(transport=SimulatedTransport())
        self.assertEqual(result['attempts'],0)
        self.assertEqual(result['events'][0]['reason'],'DUPLICATE_OR_INTERRUPTED')

    def test_corrupt_receipt(self):
        for content in ('{','{}','[]','{"version":1,"claims":[],"last_utc":null}'):
            (self.directory/'receipts.json').write_text(content)
            self.assertEqual(self.run_tick()['reason'],'CORRUPT_RECEIPT')

    def test_backward_restart(self):
        self.run_tick()
        self.now -= timedelta(seconds=1)
        self.assertEqual(self.run_tick()['reason'],'BACKWARD_CLOCK')

    def test_sleep_wake_outage_no_catchup(self):
        self.now += timedelta(hours=1)
        result=self.run_tick(proof=ClockProof(self.now,0,.1,.1),transport=SimulatedTransport())
        self.assertEqual(result['attempts'],0)
        self.assertEqual(result['events'][0]['status'],LATE)

    def test_429_timeout_offline_no_retry(self):
        for outcome in ('429','TIMEOUT','OFFLINE'):
            with tempfile.TemporaryDirectory() as directory:
                transport=SimulatedTransport([outcome])
                result=tick(self.scope,directory,lambda:self.now,lambda:0,self.proof,transport)
                self.assertEqual(result['attempts'],1)
                self.assertEqual(result['events'][0]['reason'],outcome)

    def test_eight_attempt_bound(self):
        symbols=tuple('FIXTURE'+str(i) for i in range(8))
        scope=Scope(tuple(Event(s,'5m',CLOSE) for s in symbols),symbols=symbols)
        self.assertEqual(self.run_tick(scope=scope,transport=SimulatedTransport())['attempts'],8)
        with self.assertRaises(ValueError): Scope(max_attempts=9)
        with self.assertRaises(ValueError): Scope(simulation_only=False)
        with self.assertRaises(ValueError): self.run_tick(transport=object())

    def test_receipt_decision_expiry(self):
        times=iter([self.now,self.now,self.now,CLOSE+timedelta(seconds=30),CLOSE+timedelta(seconds=30)])
        monotonic=iter([0,0,0,28])
        result=self.run_tick(clock=lambda:next(times),monotonic=lambda:next(monotonic),transport=SimulatedTransport())
        self.assertEqual(result['events'][0]['status'],LATE)

    def test_time_jump_during_request(self):
        times=iter([self.now,self.now,self.now,self.now,self.now+timedelta(seconds=3)])
        result=self.run_tick(clock=lambda:next(times),transport=SimulatedTransport())
        self.assertEqual(result['events'][0]['status'],'CLOCK_UNTRUSTED')

    def test_slow_claim_does_not_dispatch(self):
        times=iter([self.now,self.now,self.now+timedelta(seconds=6)])
        monos=iter([0,0,6])
        result=self.run_tick(clock=lambda:next(times),monotonic=lambda:next(monos),transport=SimulatedTransport())
        self.assertEqual(result['attempts'],0)
        self.assertEqual(result['events'][0]['reason'],'DISPATCH_DEADLINE')

    def test_admission_only_decision_deadline(self):
        times=iter([self.now,self.now,self.now+timedelta(seconds=6)])
        monos=iter([0,0,6])
        result=self.run_tick(clock=lambda:next(times),monotonic=lambda:next(monos))
        self.assertEqual(result['events'][0]['status'],LATE)
        self.assertEqual(result['events'][0]['decision_utc'],(self.now+timedelta(seconds=6)).isoformat())

    def test_process_lock_and_crash_release(self):
        code='from pathlib import Path; from zs_smart_gate.windows_runner import process_lock; import sys;\nwith process_lock(Path(sys.argv[1])) as acquired: print(acquired, flush=True)'
        with process_lock(self.directory) as acquired:
            self.assertTrue(acquired)
            child=subprocess.run([sys.executable,'-c',code,str(self.directory)],capture_output=True,text=True,check=True)
            self.assertEqual(child.stdout.strip(),'False')
            self.assertEqual(self.run_tick()['status'],'LOCK_BUSY')
        crashcode='from pathlib import Path; from zs_smart_gate.windows_runner import process_lock; import sys,os;\nwith process_lock(Path(sys.argv[1])) as acquired: os._exit(7)'
        self.assertEqual(subprocess.run([sys.executable,'-c',crashcode,str(self.directory)]).returncode,7)
        with process_lock(self.directory) as acquired: self.assertTrue(acquired)

    def test_status_is_read_only(self):
        missing=self.directory/'missing'
        self.assertEqual(main(['--status','--state-dir',str(missing)]),0)
        self.assertFalse(missing.exists())


if __name__ == '__main__': unittest.main()
