from datetime import date,datetime,timedelta,timezone
import unittest
from unittest.mock import patch,Mock
from zs_smart_gate.windows_source import fixture_symbol,clock_sample
from zs_smart_gate.windows_prospective import proposal,freeze,ClockEvidence,AttemptBudget
from test_stage03b1 import FixtureTransport,Horizon

class SourceTests(unittest.TestCase):
    def setUp(self):
        self.manifest=freeze(proposal(date(2026,10,31),'a'*40),
            now=datetime(2026,10,29,tzinfo=timezone.utc),accepted_runner_sha='a'*40,storage_decision_id='FIXTURE_ONLY')
    def test_twelve_slots_use_accepted_source_and_shared_budget(self):
        budget=AttemptBudget();total=0
        for group in self.manifest['plan']['groups']:
            now=datetime.fromisoformat(group['close'])+timedelta(seconds=60)
            proof=ClockEvidence(now,0,.1,.1,.1,True)
            for symbol in self.manifest['plan']['symbols']:
                fake=FixtureTransport(Horizon.INTRADAY if group['frame']=='30m' else Horizon.SWING)
                def getter(path,params=None,*,on_attempt):
                    data,meta=fake(path,params,on_attempt=on_attempt)
                    if isinstance(data,dict):
                        if 'symbol' in data:data['symbol']=symbol
                        for item in data.get('symbols',[]):item['symbol']=symbol
                    return data,meta
                with patch('test_stage03b1.NOW_MS',int(now.timestamp()*1000)):
                    result=fixture_symbol(self.manifest,group,symbol,getter=getter,clock=lambda:now,
                        proof=proof,monotonic=lambda:0,budget=budget)
                self.assertEqual(result['http_attempts'],6 if group['frame']=='30m' else 7)
                self.assertEqual(result['live_permission'],'OFF')
                total+=result['http_attempts']
        self.assertEqual(total,78)
        self.assertEqual(sum(budget.counts.values()),78)
    def test_late_or_unknown_clock_zero_transport(self):
        group=self.manifest['plan']['groups'][0];now=datetime.fromisoformat(group['close'])+timedelta(seconds=600)
        getter=Mock()
        result=fixture_symbol(self.manifest,group,'BTCUSDT',getter=getter,clock=lambda:now,
            proof=None,monotonic=lambda:0,budget=AttemptBudget())
        self.assertEqual(result['http_attempts'],0);getter.assert_not_called()
    def test_measured_clock_uncertainty_and_wall_jump(self):
        meta={'t0_local_ms':100000,'received_local_ms':100100,'latency_ms':100}
        proof=clock_sample({'serverTime':100050},meta,.1,True)
        self.assertTrue(proof.trusted(proof.sampled_at))
        self.assertGreater(proof.uncertainty_seconds,.05)
        with self.assertRaises(ValueError):clock_sample({'serverTime':100050},{**meta,'latency_ms':1},.1,True)
