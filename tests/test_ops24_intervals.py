"""Adversarial adaptive provider counters; all responses are deterministic fixtures."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import tempfile
import unittest

from zs_smart_gate.ops24_intervals import Intervals,QuotaHold


def limits(cap=6000,extra=()):
    return [dict(rateLimitType='REQUEST_WEIGHT',interval='MINUTE',intervalNum=1,limit=cap),*extra]


def row(kind,interval,n,cap):
    return dict(rateLimitType=kind,interval=interval,intervalNum=n,limit=cap)


class AdaptiveIntervalsTests(unittest.TestCase):
    def make(self,root,cap=6000,extra=()):
        clock=[100.]
        q=Intervals(root,wall=lambda:clock[0])
        q.adopt(limits(cap,extra))
        return q,clock

    def measure(self,q,clock,count=4):
        for i in range(count):
            q.reserve('measure'+str(i),'klines',2)
            q.complete('measure'+str(i),dict(http_status=200,http_attempted=True),
                       {'X-MBX-USED-WEIGHT-1M':str(2*(i+1))})
            clock[0]+=.5

    def test_preferred_target_lower_and_higher_without_fixed_5500(self):
        for cap in (600,2000,6000,12000):
            with tempfile.TemporaryDirectory() as root:
                q,clock=self.make(root,cap)
                self.measure(q,clock)
                preferred=cap*59//60
                self.assertEqual(q.report()['limits'][0]['preferred'],preferred)
                q.reserve('near-target','synthetic-reservation',preferred-8)
                with self.assertRaises(QuotaHold):q.reserve('beyond-target','klines',1)

    def test_unknown_shared_usage_cannot_use_maximum_target_immediately(self):
        with tempfile.TemporaryDirectory() as root:
            q,_=self.make(root)
            with self.assertRaises(QuotaHold):q.reserve('unsafe','synthetic',5900)
            q.reserve('measured-low-cost','klines',2)

    def test_all_applicable_intervals_and_unobservable_raw_envelope(self):
        with tempfile.TemporaryDirectory() as root:
            q,clock=self.make(root,extra=[row('RAW_REQUESTS','MINUTE',5,61000),row('REQUEST_WEIGHT','SECOND',10,50)])
            q.reserve('forty','synthetic',40)
            with self.assertRaisesRegex(QuotaHold,'HEADROOM_REQUEST_WEIGHT_10'):
                q.reserve('cannot-pass-ten-seconds','synthetic',6)
        with tempfile.TemporaryDirectory() as root:
            q,_=self.make(root,extra=[row('RAW_REQUESTS','MINUTE',1,1000)])
            with self.assertRaisesRegex(QuotaHold,'RAW_REQUESTS'):
                q.reserve('raw-unknown-not-zero','klines',2)

    def test_raw_unknown_without_divisible_provider_bound_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            q,_=self.make(root,extra=[row('RAW_REQUESTS','SECOND',10,100)])
            with self.assertRaisesRegex(QuotaHold,'RAW_SHARED_IP_UNBOUNDED'):
                q.reserve('no-bound','klines',2)

    def test_shared_ip_jump_reduces_admission_and_lower_headers_never_refund(self):
        with tempfile.TemporaryDirectory() as root:
            q,clock=self.make(root)
            self.measure(q,clock)
            q.reserve('external-spike','klines',2)
            q.complete('external-spike',dict(http_status=200),{'X-MBX-USED-WEIGHT-1M':'5800'})
            with self.assertRaises(QuotaHold):q.reserve('unsafe-after-spike','klines',2)
            maximum=max(r['charged'] for r in q.report()['buckets'])
            self.assertGreaterEqual(maximum,5800)

    def test_atomic_concurrent_reservations_count_all_inflight(self):
        with tempfile.TemporaryDirectory() as root:
            q,_=self.make(root,100)
            def reserve(i):
                try:q.reserve(str(i),'synthetic',10);return True
                except QuotaHold:return False
            with ThreadPoolExecutor(max_workers=20) as pool:results=list(pool.map(reserve,range(20)))
            self.assertEqual(sum(results),9)

    def test_out_of_order_observation_race_keeps_max_and_pending(self):
        with tempfile.TemporaryDirectory() as root:
            q,_=self.make(root)
            q.reserve('a','klines',2);q.reserve('b','klines',2)
            q.complete('b',dict(http_status=200),{'X-MBX-USED-WEIGHT-1M':'100'})
            q.complete('a',dict(http_status=200),{'X-MBX-USED-WEIGHT-1M':'98'})
            self.assertGreaterEqual(max(r['charged'] for r in q.report()['buckets']),102)
            self.assertEqual(max(r['observed'] for r in q.report()['buckets']),100)

    def test_ban_retry_after_persisted_across_restart_and_no_early_probe(self):
        for status in (429,418):
            with tempfile.TemporaryDirectory() as root:
                q,clock=self.make(root)
                q.reserve('ban','klines',2)
                q.complete('ban',dict(http_status=status),{'Retry-After':'120'})
                restored=Intervals(root,wall=lambda:clock[0])
                with self.assertRaisesRegex(QuotaHold,'BACKOFF'):restored.reserve('early','klines',2)
                clock[0]+=121
                restored.reserve('fresh-intent-after-provider-expiry','klines',2)
                with self.assertRaises(QuotaHold):restored.reserve('ban','klines',2)

    def test_ban_without_retry_after_does_not_invent_an_expiry(self):
        with tempfile.TemporaryDirectory() as root:
            q,clock=self.make(root)
            q.reserve('ban','klines',2);q.complete('ban',dict(http_status=418),{})
            clock[0]+=86400
            with self.assertRaisesRegex(QuotaHold,'418_BACKOFF'):q.reserve('guess','klines',2)

    def test_unknown_receive_has_cooldown_no_replay_and_carried_cost(self):
        with tempfile.TemporaryDirectory() as root:
            q,clock=self.make(root)
            q.reserve('lost','klines',2)
            q.complete('lost',dict(http_attempted=True),{})
            self.assertEqual(q.report()['unknown'],1)
            with self.assertRaises(QuotaHold):q.reserve('next','klines',2)
            clock[0]+=71
            q.reserve('new-boundary-distinct','klines',2)
            with self.assertRaises(QuotaHold):q.reserve('lost','klines',2)

    def test_provider_decrease_immediately_blocks_and_invalid_metadata_fails(self):
        with tempfile.TemporaryDirectory() as root:
            q,_=self.make(root)
            q.reserve('one','synthetic',500)
            q.adopt(limits(100))
            with self.assertRaises(QuotaHold):q.reserve('two','klines',2)
            for bad in ([],[row('CONNECTIONS','MINUTE',1,10)],[row('REQUEST_WEIGHT','MINUTE',1,0)]):
                with self.assertRaises(QuotaHold):q.adopt(bad)

    def test_bootstrap_is_one_public_discovery_not_a_general_quota_bypass(self):
        with tempfile.TemporaryDirectory() as root:
            q=Intervals(root)
            with self.assertRaises(QuotaHold):q.reserve('wrong','klines',2)
            q.reserve('first','exchangeInfo',20)
            with self.assertRaises(QuotaHold):q.reserve('second','exchangeInfo',20)

    def test_missing_or_unadvertised_header_never_means_zero_use(self):
        with tempfile.TemporaryDirectory() as root:
            q,_=self.make(root)
            q.reserve('missing','klines',2)
            with self.assertRaises(QuotaHold):q.complete('missing',dict(http_status=200),{})
            with self.assertRaises(QuotaHold):q.complete('missing',dict(http_status=200),{'X-MBX-USED-WEIGHT-1D':'1'})

    def test_crashed_reserved_intent_becomes_unknown_not_free_capacity(self):
        with tempfile.TemporaryDirectory() as root:
            q,clock=self.make(root)
            q.reserve('crashed','klines',2)
            clock[0]+=130
            with self.assertRaisesRegex(QuotaHold,'UNKNOWN_READ_COOLDOWN'):
                q.reserve('restart','klines',2)
            self.assertEqual(q.report()['unknown'],1)
            clock[0]+=71
            q.reserve('new-window','klines',2)
            with self.assertRaises(QuotaHold):q.reserve('crashed','klines',2)

    def test_same_byte_commit_reconciliation_does_not_double_charge(self):
        with tempfile.TemporaryDirectory() as root:
            q,_=self.make(root)
            q.reserve('ack','klines',2)
            receipt=dict(http_status=200,http_attempted=True)
            q.complete('ack',receipt,{'X-MBX-USED-WEIGHT-1M':'20'})
            before=q.report()
            q.complete('ack',receipt,{'X-MBX-USED-WEIGHT-1M':'20'})
            self.assertEqual(before,q.report())
