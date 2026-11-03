import base64
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from zs_smart_gate.custody_restore import restore, safe_target, materialize
from zs_smart_gate.evidence_journal import SingleStudyJournal,canonical_bytes
from zs_smart_gate.github_evidence_backend import GitHubEvidenceBackend
from zs_smart_gate.stage04_evidence_packet import make_record,prepare_manifest,persist_packet
from test_github_evidence_backend import MockContentsTransport

class CustodyRestoreTests(unittest.TestCase):
    def packet(self,root,extra=None):
        study='fixture-015';branch='evidence-fixture-015'
        raw=b'original exact historical bytes\r\n'
        sha=hashlib.sha256(raw).hexdigest()
        inventory={'files':[{'path':'work/tool.py','bytes':len(raw),'sha256':sha,'transfer_status':'INCLUDED'},
                            {'path':'missing.zip','transfer_status':'BLOCKED_CAPACITY'}]}
        content={'inventory.json':canonical_bytes(inventory),'objects/'+sha:raw}
        if extra:content.update(extra)
        b=io.BytesIO()
        with tarfile.open(fileobj=b,mode='w')as t:
            for name,body in content.items():
                i=tarfile.TarInfo(name);i.size=len(body);t.addfile(i,io.BytesIO(body))
        z=gzip.compress(b.getvalue(),mtime=0)
        at=datetime.now(timezone.utc).isoformat()
        def rec(event,payload):
            return make_record(study_id=study,event_id=event,record_type='source_snapshot',source_id='synthetic',received_at=at,available_at=at,payload=payload)
        records={'control':rec('control',dict(kind='custody-control-v1',archive_bytes=len(z),archive_sha256=hashlib.sha256(z).hexdigest(),chunk_count=1)),
                 'chunk-000':rec('chunk-000',dict(kind='custody-chunk-v1',ordinal=0,sha256=hashlib.sha256(z).hexdigest(),data_base64=base64.b64encode(z).decode()))}
        m=prepare_manifest(study,records,created_at=at)
        transport=MockContentsTransport()
        j=SingleStudyJournal(study,GitHubEvidenceBackend(study,branch=branch,transport=transport,enabled=True),lambda:datetime.now(timezone.utc))
        r=persist_packet(j,m,records);self.assertTrue(r.ok)
        for path,body in transport.files.items():
            p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
        return dict(study_id=study,branch=branch,manifest_sha256=r.manifest_sha256)

    def test_exact_restore_and_explicit_partial_status(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);kw=self.packet(root/'github')
            result=restore(root/'github',root/'restored',**kw)
            self.assertEqual(result['blocked_files'],1)
            self.assertFalse(result['full_reproducible'])
            self.assertEqual(materialize(root/'restored','work/',root/'code'),1)
            self.assertEqual((root/'code/tool.py').read_bytes(),b'original exact historical bytes\r\n')

    def test_tampered_remote_receipt_fails_before_output(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);kw=self.packet(root/'github')
            p=root/'github/studies/fixture-015/receipts/chunk-000.json'
            p.write_bytes(p.read_bytes()+b'tampered')
            with self.assertRaises(ValueError):restore(root/'github',root/'restored',**kw)
            self.assertFalse((root/'restored').exists())

    def test_valid_journal_cannot_authorize_path_traversal(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);kw=self.packet(root/'github',{'../escape':b'bad'})
            with self.assertRaises(ValueError):restore(root/'github',root/'restored',**kw)
            self.assertFalse((root/'restored').exists())

    def test_missing_source_cannot_materialize_as_complete(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);kw=self.packet(root/'github')
            restore(root/'github',root/'restored',**kw)
            with self.assertRaisesRegex(ValueError,'SOURCE_MISSING_OR_WITHHELD'):
                materialize(root/'restored','missing',root/'bad')
            self.assertFalse((root/'bad').exists())

    def test_absolute_windows_and_traversal_paths_rejected(self):
        for name in ['D:/owner/file','C:\\owner\\file','../secret','/absolute']:
            with self.assertRaises(ValueError):safe_target(Path.cwd(),name)

    def test_wrong_manifest_pin_rejected(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);kw=self.packet(root/'github');kw['manifest_sha256']='0'*64
            with self.assertRaises(ValueError):restore(root/'github',root/'restored',**kw)
