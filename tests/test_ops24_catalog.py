"""Windows native cryptographic membership, plus negative binding controls.

Only explicit native member checks use actual OS files. Other clock inputs below
are synthetic fixtures and never establish an actual scheduled clock acceptance.
"""
import copy
from pathlib import Path
import tempfile
import unittest

from zs_smart_gate.ops24_catalog import member_proof
from zs_smart_gate.ops24_normal_clock import (
    catalog_signature,system_directory,verify_provenance,
)
from zs_smart_gate.ops24_budget import Hold
from test_ops24_normal_clock import profile

class CatalogNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof=member_proof(system_directory()/'sc.exe')
        cls.signed=catalog_signature(cls.proof['catalog'])

    def test_actual_windows_catalog_member_and_microsoft_signature(self):
        self.assertIs(self.proof['verified'],True)
        self.assertEqual(self.proof['winverifytrust_code'],0)
        self.assertEqual(self.signed['status'],'Valid')
        self.assertIn('O=Microsoft Corporation',self.signed['signer'])
        self.assertEqual(self.signed['sha256'],self.proof['catalog_sha256'])

    def test_changed_pe_member_is_rejected_even_with_real_signed_catalog(self):
        with tempfile.TemporaryDirectory(dir='D:/ZS-SMART-GATE/temp') as folder:
            path=Path(folder)/'changed.exe'
            data=bytearray((system_directory()/'sc.exe').read_bytes())
            data[0x1000]^=1;path.write_bytes(data)
            result=member_proof(path,catalog=self.proof['catalog'])
            self.assertIs(result['verified'],False)
            self.assertNotEqual(result['winverifytrust_code'],0)

    def test_complete_native_binding_retains_original_notsigned(self):
        fixture=profile();row=fixture['signatures'][0]
        row.update(status='NotSigned',signer=None,sha256=self.proof['file_sha256'],
                   explicit_catalog={**copy.deepcopy(self.proof),'signature':copy.deepcopy(self.signed)})
        self.assertTrue(verify_provenance(fixture))
        self.assertEqual(row['status'],'NotSigned')
        for mode in ('MEMBER','DIGEST','CATALOG','SIGNER','MUTABLE','NO_ACL','HASH_MISMATCH','UNCERTAIN_CODE'):
            bad=copy.deepcopy(fixture);item=bad['signatures'][0];proof=item['explicit_catalog']
            if mode=='MEMBER':proof['winverifytrust_code']=-1
            elif mode=='DIGEST':proof['file_sha256']='0'*64
            elif mode=='CATALOG':proof['catalog_sha256']='0'*64
            elif mode=='SIGNER':proof['signature']['signer']='CN=Untrusted'
            elif mode=='MUTABLE':proof['signature']['rules'].append(dict(propagation=0,type='Allow',rights=2,sid='S-1-5-32-545'))
            elif mode=='NO_ACL':proof['signature']['rules']=[]
            elif mode=='HASH_MISMATCH':item['status']='HashMismatch'
            else:proof['winverifytrust_code']=False
            with self.subTest(mode=mode),self.assertRaises(Hold):
                verify_provenance(bad)
