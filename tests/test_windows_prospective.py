from datetime import date,datetime,timedelta,timezone
import copy
import unittest
from unittest.mock import Mock
from zs_smart_gate.windows_prospective import proposal,freeze,validate,ClockEvidence,admission,AttemptBudget,prepare_event,OLD_ID
from zs_smart_gate.windows_operations import canonical_sha

UTC=timezone.utc
SHA='a'*40
NOW=datetime(2026,10,28,12,tzinfo=UTC)

class ProspectiveTests(unittest.TestCase):
    def setUp(self):
        self.plan=proposal(date(2026,10,30),SHA)
        self.m=freeze(self.plan,now=NOW,accepted_runner_sha=SHA,storage_decision_id='TEST_ONLY_NOT_AUTHORIZED')
        self.g=self.plan['groups'][0]
        self.close=datetime.fromisoformat(self.g['close'])
    def clock(self,t,uncertainty=.1,dispersion=.1):return ClockEvidence(t,0,.1,uncertainty,dispersion,True)
    def test_new_identity_twelve_slots_and_freeze(self):
        self.assertNotEqual(self.m['study_id'],OLD_ID)
        self.assertEqual(len(self.plan['groups'])*len(self.plan['symbols']),12)
        validate(self.m)
        changed=copy.deepcopy(self.m);changed['plan']['day']='2027-10-30'
        with self.assertRaises(ValueError):validate(changed)
        with self.assertRaises(ValueError):freeze(self.plan,now=self.close,accepted_runner_sha=SHA,storage_decision_id='x')
        with self.assertRaises(ValueError):freeze(self.plan,now=NOW,accepted_runner_sha=SHA,storage_decision_id='')
    def test_strict_clock_current_dispersion_rejected(self):
        t=self.close+timedelta(seconds=60)
        for c in [None,self.clock(t,None),self.clock(t,.1,7.965),self.clock(t-timedelta(seconds=31))]:
            self.assertEqual(admission(self.m,self.g,t,c),'CLOCK_UNTRUSTED')
    def test_boundary_before_after_and_wrong_date(self):
        for seconds,status in [(-1,'NOT_YET_CLOSED'),(0,'NOT_YET_CLOSED'),(60,'ELIGIBLE'),(599.9,'LATE'),(600,'LATE')]:
            t=self.close+timedelta(seconds=seconds)
            self.assertEqual(admission(self.m,self.g,t,self.clock(t)),status)
        wrong={**self.g,'close':'2027-10-30T00:30:00+00:00'}
        self.assertEqual(admission(self.m,wrong,NOW,None),'UNAPPROVED_SCOPE')
    def test_eight_twentyfour_ninetysix(self):
        b=AttemptBudget()
        for group in self.plan['groups']:
            t=datetime.fromisoformat(group['close'])+timedelta(seconds=60)
            for symbol in self.plan['symbols']:
                for _ in range(8):b.before_attempt(self.m,group,symbol,t,self.clock(t))
                with self.assertRaises(ValueError):b.before_attempt(self.m,group,symbol,t,self.clock(t))
        self.assertEqual(sum(b.counts.values()),96)
    def test_blocked_zero_attempts_and_outage(self):
        t=self.close+timedelta(seconds=60);journal=Mock()
        journal.claim_before_attempts.side_effect=OSError('offline')
        r=prepare_event(self.m,self.g,t,self.clock(t),journal=journal,pm_sha=SHA,frozen_readback_sha=canonical_sha(self.m))
        self.assertEqual(r['reason'],'GITHUB_AUTHORITY_UNAVAILABLE');self.assertEqual(r['http_attempts'],0)
        journal.reset_mock();journal.claim_before_attempts.side_effect=None;journal.claim_before_attempts.return_value=False
        r=prepare_event(self.m,self.g,t,self.clock(t),journal=journal,pm_sha=SHA,frozen_readback_sha=canonical_sha(self.m))
        self.assertEqual(r['reason'],'DUPLICATE_OR_INTERRUPTED')
        journal.reset_mock()
        r=prepare_event(self.m,self.g,t,self.clock(t),journal=journal,pm_sha='b'*40,frozen_readback_sha='bad')
        journal.claim_before_attempts.assert_not_called();self.assertEqual(r['http_attempts'],0)
