"""Actual local custody and replay, fake Telegram/clock; never a live acceptance."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from test_e2e51 import config, fixture
from test_stage05_operational import Fake, update
from zs_smart_gate.e2e51 import analyze, persist
from zs_smart_gate.pre05_offline_chain import LocalChainJournal
from zs_smart_gate.stage05_contracts import ContractError, canonical, digest
from zs_smart_gate.stage05_custody import VerifiedUpstream
from zs_smart_gate.stage05_runtime_bridge import TelegramBridge
from zs_smart_gate.stage05_telegram_http import ApiResult


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='D:/ZS-SMART-GATE/temp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        rows, decision = fixture()
        self.now = datetime.fromtimestamp(decision / 1000 + 1, timezone.utc)
        event = analyze(rows, decision, synthetic=False)
        stored, _ = persist(self.root, rows, event)
        self.journal = LocalChainJournal(self.root/'journal.sqlite')
        self.ref = self.journal.append_readback(stored)[0], digest(canonical(stored))
        self.upstream = VerifiedUpstream(self.journal, dict([self.ref]))
        self.fake = Fake()
        self.allowed = True

    def bridge(self):
        return TelegramBridge(root=self.root/'runtime', config=config(), upstream=self.upstream,
            references={'BTCUSDT': self.ref}, clock_guard=lambda: self.allowed,
            clock=lambda: self.now, simulation=True,
            transports={'ANALYTICS':self.fake, 'INTERACTIVE':self.fake, 'SIGNALS':self.fake})

    def inbound(self, account, number):
        row = update(account, number, int(self.now.timestamp()))
        row['update_id'] = number
        return row

    def test_verified_rejection_archived_once_and_never_sent_as_signal(self):
        bridge = self.bridge()
        first = bridge.dispatch('BTCUSDT')
        self.assertEqual(set(first['destinations']), {'C'})
        self.assertIsNone(first['signal_id'])
        self.assertEqual(first['qualification'], 'REJECTED')
        self.bridge().dispatch('BTCUSDT')
        self.assertEqual(len(self.fake.sends),1)

    def test_both_real_account_routes_are_served_offline_fixture(self):
        self.fake.updates = (self.inbound(101,1),self.inbound(202,2))
        result = self.bridge().poll_once()
        self.assertEqual([r['status'] for r in result['replies']], ['ACCEPTED','ACCEPTED'])
        self.assertEqual({row[0] for row in self.fake.sends}, {101,202})
        self.assertEqual({r['destination_label'] for r in result['replies']},{'A','B'})

    def test_cross_account_or_third_account_never_receives_reply(self):
        cross = self.inbound(101,1);cross['message']['chat']['id']=202
        self.fake.updates = (cross,self.inbound(303,2))
        self.assertEqual(self.bridge().poll_once()['replies'],[])
        self.assertEqual(self.fake.sends,[])

    def test_restart_never_resends_acknowledged_update(self):
        self.fake.updates = (self.inbound(101,1),)
        self.bridge().poll_once()
        self.bridge().poll_once()
        self.assertEqual(len(self.fake.sends),1)

    def test_uncertain_send_is_durable_and_not_retried_after_restart(self):
        self.fake.updates = (self.inbound(202,2),)
        self.fake.outcomes = iter((ApiResult('UNKNOWN_DELIVERY'),))
        self.assertEqual(self.bridge().poll_once()['replies'][0]['status'],'UNKNOWN_DELIVERY')
        self.bridge().poll_once()
        self.assertEqual(len(self.fake.sends),1)

    def test_clock_or_stop_prevents_poll_and_delivery(self):
        bridge = self.bridge();self.allowed=False
        for operation in (lambda:bridge.dispatch('BTCUSDT'),bridge.poll_once):
            with self.assertRaisesRegex(ContractError,'CLOCK_HOLD'):operation()
        self.allowed=True;(bridge.root/'STOP_REQUESTED').write_text('stop')
        with self.assertRaisesRegex(ContractError,'CLOCK_HOLD'):bridge.poll_once()
        self.assertEqual(self.fake.sends,[])

    def test_stale_snapshot_never_dispatches_archive_or_signal(self):
        self.now += timedelta(seconds=121)
        with self.assertRaisesRegex(ContractError,'STALE_OR_FUTURE'):
            self.bridge().dispatch('BTCUSDT')

    def test_changed_update_identity_is_rejected(self):
        self.fake.updates=(self.inbound(101,1),)
        bridge=self.bridge();bridge.poll_once()
        self.fake.updates[0]['message']['text']='ETHUSDT'
        with self.assertRaisesRegex(ContractError,'UPDATE_CONFLICT'):bridge.poll_once()

    def test_old_or_future_human_messages_are_not_replied_to(self):
        old=self.inbound(101,1);old['message']['date']-=121
        future=self.inbound(202,2);future['message']['date']+=5
        self.fake.updates=(old,future)
        self.assertEqual(self.bridge().poll_once()['replies'],[])
        self.assertEqual(self.fake.sends,[])

    def test_reply_limit_keeps_later_updates_unacknowledged(self):
        self.fake.updates=(self.inbound(101,1),self.inbound(202,2))
        first=self.bridge().poll_once(max_replies=1)
        self.assertEqual([r['destination_label'] for r in first['replies']],['A'])
        second=self.bridge().poll_once(max_replies=1)
        self.assertEqual([r['destination_label'] for r in second['replies']],['B'])
        self.assertEqual(len(self.fake.sends),2)
