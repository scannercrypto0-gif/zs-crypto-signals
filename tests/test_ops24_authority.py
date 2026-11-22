"""Standing authority is verified technical evidence, not a manually accepted flag."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from zs_smart_gate.ops24_authority import SCOPE,review_proof,windows_proof,compose,deployment_proof,verify_remote
from zs_smart_gate.ops24_budget import Hold
from zs_smart_gate.stage05_contracts import canonical,digest

HEAD='a'*40
TREE='b'*40

def reviewed(head=HEAD,tree=TREE):
 return dict(id=123,commit_id=head,state='COMMENTED',user=dict(login='scannercrypto0-gif'),
  html_url='https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/76#pullrequestreview-123',
  body='PM independent review\nOPS24_RELEASE_ACCEPT '+head+' '+tree+' '+SCOPE)


class StandingAuthorityTests(unittest.TestCase):
 def test_actual_pm_exact_head_marker_not_flags_or_old_review(self):
  good=reviewed()
  self.assertEqual(review_proof([good],HEAD,TREE)['id'],123)
  for bad in (dict(accepted=True),reviewed('c'*40),{**good,'body':'PM accepted everything'},
              {**good,'user':dict(login='different-account')}):
   with self.assertRaises(Hold):review_proof([bad],HEAD,TREE)

 def test_windows_original_stdout_tamper_and_test_totals(self):
  with tempfile.TemporaryDirectory() as root:
   root=Path(root);stdout=b'original stdout\r\n';stderr=b'original stderr\r\n'
   (root/'target.stdout.raw.txt').write_bytes(stdout);(root/'target.stderr.raw.txt').write_bytes(stderr)
   result=dict(tests=1,success=True)
   (root/'target.json').write_bytes(canonical(result))
   proof=dict(head=HEAD,tree=TREE,clean=True,python='3.12.10',powershell='5.1.0',success=True,
      tests=1,failures=0,errors=0,skipped=0,network_attempts=0,
      suites=[dict(suite='target',exit=0,result=result,stdout_sha256=digest(stdout),stderr_sha256=digest(stderr))])
   (root/'acceptance.json').write_bytes(canonical(proof))
   self.assertEqual(windows_proof(root,HEAD,TREE)['tests'],1)
   (root/'target.stdout.raw.txt').write_bytes(b'tampered')
   with self.assertRaisesRegex(Hold,'RAW_RECEIPT_HASH'):windows_proof(root,HEAD,TREE)

 def test_owner_standing_permission_does_not_forge_pm_review_or_merge(self):
  authority=dict(user=dict(login='scannercrypto0-gif'),body='Standing authorization granted now read-only')
  def fetch(path):
   if 'issues/comments' in path:return authority
   if '/reviews?' in path:return []
   self.fail('must hold before reading nonexistent merge')
  with self.assertRaisesRegex(Hold,'PM_REVISED_EXACT_RELEASE_REVIEW_PENDING'):
   compose(head=HEAD,tree=TREE,windows='unused',source='unused',fetch=fetch)
  def unmerged(path):
   if 'issues/comments' in path:return authority
   if '/reviews?' in path:return [reviewed()]
   if path.endswith('/pulls/76'):return dict(head=dict(sha=HEAD),draft=True,merged=False)
   self.fail(path)
  with self.assertRaisesRegex(Hold,'PLATFORM_MERGE_PENDING'):
   compose(head=HEAD,tree=TREE,windows='unused',source='unused',fetch=unmerged)

 def test_deployment_flags_never_substitute_real_receipts(self):
  with tempfile.TemporaryDirectory() as root:
   Path(root,'deployment-proof.json').write_bytes(canonical(dict(accepted=True,reboot=True,logoff=True)))
   with self.assertRaisesRegex(Hold,'ACTUAL_NORMAL_DEPLOYMENT_PROOF_PENDING'):
    deployment_proof(root,HEAD,TREE,'local-owner-fixture')

 def test_remote_authority_mutation_revokes_cached_decision(self):
  decision=dict(schema='zs.ops24.standing-authority.v2',scope=SCOPE,head=HEAD,tree=TREE,
   authority_id=7061389384,authority_body_sha256='c'*64,reviewed_source_head=HEAD,seconds=86400,
   platform=dict(merged_commit=HEAD,protection_bypass=False),
   windows=dict(head=HEAD,tree=TREE,tests=1),source=dict(head=HEAD,tree=TREE,eligible=1))
  with self.assertRaisesRegex(Hold,'AUTHORITY_CHANGED'):
   verify_remote(decision,fetch=lambda _:dict(body='changed authority'))

 def test_standard_worker_cannot_claim_its_own_mutable_cache_as_owner_authority(self):
  from zs_smart_gate.ops24_authority import verify_protected_cache
  with tempfile.TemporaryDirectory() as root:
   with self.assertRaisesRegex(Hold,'PROTECTED_STANDING_CACHE_REQUIRED'):
    verify_protected_cache(root,{},dict(owner_sid='same-fixture-owner',worker_sid='same-fixture-owner'))
