"""Real local SQLite lifecycle, synthetic authority/clock, no actual logoff/reboot."""
import json,sqlite3,tempfile
from pathlib import Path
import unittest
from contextlib import closing
from unittest.mock import patch
from zs_smart_gate.ops24_release_clock import RECOVERY
from zs_smart_gate.ops24_recovery import serve_recovery,verify_recovery
from zs_smart_gate.ops24_budget import Hold
from zs_smart_gate.stage05_contracts import canonical,digest

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='D:/ZS-SMART-GATE/temp');self.root=Path(self.temp.name);self.now=1000
        self.head='a'*40;self.tree='b'*40
        self.record=dict(schema='zs.ops77.recovery-authority.v1',scope=RECOVERY,head=self.head,tree=self.tree,directive_id=7076686518,directive_body='PRODUCTION_SERVE_UNPROVEN fixture not actual authority',windows_tests=dict(head=self.head,tree=self.tree,tests=1),created_epoch=1000,expires_epoch=87400)
        self.record['directive_sha256']=digest(self.record['directive_body'].encode());raw=canonical(self.record)
        (self.root/'recovery-authority.json').write_bytes(raw)
        self.config=dict(scope=RECOVERY,head=self.head,tree=self.tree,recovery_authority_sha256=digest(raw));(self.root/'release.json').write_bytes(canonical(self.config))
    def tearDown(self):self.temp.cleanup()
    def test_serve_lifecycle_journals_and_stops_without_any_market_transport(self):
        class Clock:
            def refresh(self):return dict(assessment=dict(status='OPERATIONAL_TIME_ACCEPTED'),fixture=True)
        def sleep(_):self.now+=5;(self.root/'STOP_REQUESTED').write_bytes(b'owner-fixture')
        with patch('urllib.request.urlopen',side_effect=AssertionError('NETWORK_FORBIDDEN')):
            result=serve_recovery(self.root,self.head,self.tree,Clock(),observe=lambda:dict(session=0,normal_token=True,boot_utc='fixture'),wall=lambda:self.now,sleep=sleep)
        self.assertEqual(result,0)
        with closing(sqlite3.connect(self.root/'recovery.sqlite')) as db:
            kinds=[r[0] for r in db.execute('SELECT kind FROM events ORDER BY id')]
            for raw,pin in db.execute('SELECT payload,sha FROM events'):self.assertEqual(digest(raw),pin)
        self.assertEqual(kinds,['SERVE_START','SERVE_CLOCK','SERVE_HEARTBEAT','SERVE_STOP'])
        status=json.loads((self.root/'status.json').read_bytes());self.assertEqual(status['market_calls'],0)
        self.assertEqual(status['stability'],'RECOVERY_VALIDATION_ONLY_NOT_24H_MARKET_SOAK')
    def test_live_scope_or_changed_authority_cannot_enter_recovery(self):
        self.config['scope']='PUBLIC_SPOT_READ_ONLY_NO_TELEGRAM_SQL_TRADING';(self.root/'release.json').write_bytes(canonical(self.config))
        with self.assertRaises(Hold):verify_recovery(self.root,self.head,self.tree)
