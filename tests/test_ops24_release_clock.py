"""New Serve clock contract tests; fixtures are not live clock acceptance."""
import json,tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from zs_smart_gate.ops24_release_clock import ReleaseClock,validate_map,CONTRACT,TASK_PROFILE
from zs_smart_gate.ops24_budget import Hold
from zs_smart_gate.stage05_contracts import canonical,digest

class ReleaseClockTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='D:/ZS-SMART-GATE/temp');self.root=Path(self.temp.name)
        self.head='a'*40;self.tree='b'*40
        self.mapping=dict(schema='zs.ops24.catalog-map.v2',scope='DISCOVERY_ONLY_NOT_ACCEPTANCE',release_head=self.head,release_tree=self.tree,files={})
        self.raw=canonical(self.mapping);(self.root/'clock-catalog-map.json').write_bytes(self.raw)
        self.config=dict(schema='zs.ops24.disabled-release.v2',head=self.head,tree=self.tree,task_profile=TASK_PROFILE,task_logon_type='Password',clock_contract=CONTRACT,owner_sid='owner-fixture',worker_sid='worker-fixture',clock_catalog_map_sha256=digest(self.raw))
        self.save()
    def tearDown(self):self.temp.cleanup()
    def save(self):(self.root/'release.json').write_bytes(canonical(self.config))
    def test_live_collection_uses_same_root_and_checks_current_acl(self):
        calls=[];value={'fixture':'NOT_A_CLOCK_WITNESS'}
        clock=ReleaseClock(self.root,self.head,self.tree,acl=lambda r,c:calls.append(('acl',r)),collect=lambda **kw:(calls.append(('collect',kw['diagnostic_root'])) or value))
        self.assertIs(clock.provenance(),value)
        self.assertEqual(calls,[('acl',self.root),('collect',self.root)])
        clock.provenance();self.assertEqual(len(calls),4)
    def test_missing_changed_wrong_release_or_s4u_map_never_replays_health(self):
        for mode in ('MISSING','CHANGED','RELEASE','S4U'):
            with self.subTest(mode=mode):
                (self.root/'clock-catalog-map.json').write_bytes(self.raw);self.config['task_logon_type']='Password';self.save()
                if mode=='MISSING':(self.root/'clock-catalog-map.json').unlink()
                elif mode=='CHANGED':(self.root/'clock-catalog-map.json').write_bytes(b'{}')
                elif mode=='RELEASE':
                    m={**self.mapping,'release_head':'c'*40};raw=canonical(m);(self.root/'clock-catalog-map.json').write_bytes(raw);self.config['clock_catalog_map_sha256']=digest(raw);self.save()
                else:self.config['task_logon_type']='S4U';self.save()
                with self.assertRaises((Hold,OSError)):validate_map(self.root,self.head,self.tree)
                self.config['clock_catalog_map_sha256']=digest(self.raw)
    def test_cached_clock_is_not_used_after_release_or_map_drift(self):
        clock=ReleaseClock(self.root,self.head,self.tree,acl=lambda *_:None,collect=lambda **_: {})
        clock.clock.refresh=lambda: {'assessment':{'status':'OPERATIONAL_TIME_ACCEPTED'}}
        self.assertTrue(clock.accepted())
        (self.root/'clock-catalog-map.json').write_bytes(b'changed')
        self.assertFalse(clock.accepted())
    def test_acl_failure_or_drift_during_collection_remains_hold(self):
        def fail(*_):raise Hold('FIXTURE_UNSAFE_ACL')
        clock=ReleaseClock(self.root,self.head,self.tree,acl=fail,collect=lambda **_: {})
        with self.assertRaisesRegex(Hold,'UNSAFE_ACL'):clock.provenance()
        def drift(**_):self.config['extra']='changed';self.save();return {}
        clock=ReleaseClock(self.root,self.head,self.tree,acl=lambda *_:None,collect=drift)
        with self.assertRaisesRegex(Hold,'RELEASE_CHANGED'):clock.provenance()
