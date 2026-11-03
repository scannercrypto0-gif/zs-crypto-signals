from pathlib import Path
import sys, json, gzip, io, tarfile, hashlib, base64, re, collections
from datetime import datetime, timezone
T=Path(__file__).resolve().parent; W=T/'portable'
sys.path[:0]=[str(W/'src'),str(W/'tests')]
from zs_smart_gate.evidence_journal import SingleStudyJournal,canonical_bytes
from zs_smart_gate.github_evidence_backend import GitHubEvidenceBackend, verify_snapshot
from zs_smart_gate.stage04_evidence_packet import make_record,prepare_manifest,persist_packet
from test_github_evidence_backend import MockContentsTransport
STUDY='custody-010-014-015'; BRANCH='evidence-migration-015'
rows=json.loads((T/'migration-inventory-local.json').read_bytes())
unique={r['sha256']:r for r in rows}
included={}; matrix=[]
for r in rows:
 p=T/'incoming'/r['path']; raw=p.read_bytes()
 assert len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256']
 q=dict(r, classification='REQUIRES_UPLOAD', transfer_status='INCLUDED',
        review_status='EXECUTOR_HASH_VERIFIED_PENDING_PM',
        license_decision='PROJECT_RESEARCH_EVIDENCE_PRIVATE_INTERNAL',
        reason='Lossless exact-byte custody copy; historical local locators are provenance only')
 if p.suffix=='.private':
  q.update(classification='SECRET_NEVER_UPLOAD',transfer_status='WITHHELD_SECURITY',reason='NTS session-bearing request/response; never export session material')
 elif p.suffix=='.pem':
  q.update(classification='REQUIRES_SANITIZED_DERIVATIVE',transfer_status='SANITIZED_REPORT_ONLY',reason='Unnecessary server certificate bytes withheld; verified fingerprint and hostname are retained in nts-auth/report.json')
 elif p.suffix=='.gz':
  q.update(classification='REQUIRES_UPLOAD',transfer_status='BLOCKED_CAPACITY',license_decision='TARDIS_INTERNAL_ONLY_CUSTOMER_USERS_CLOUD_CLAUSE_9_6_NO_EXTERNAL_REDISTRIBUTION',reason='Raw sample exceeds remaining 10MiB budget; private internal custody only; external reviewer access requires Customer User qualification')
 elif p.suffix=='.zip' and not ('2025-01' in p.name and ('30m' in p.name or '4h' in p.name) and '/negative-root/' not in r['path']):
  q.update(classification='REQUIRES_UPLOAD',transfer_status='BLOCKED_CAPACITY',license_decision='BINANCE_VISION_CC_BY_NC_SA_4_0_NONCOMMERCIAL_ATTRIBUTION_SHAREALIKE',reason='Raw historical archive exceeds remaining consolidated 10MiB budget; not silently re-downloaded')
 elif p.suffix=='.zip':
  q.update(license_decision='BINANCE_VISION_CC_BY_NC_SA_4_0_NONCOMMERCIAL_ATTRIBUTION_SHAREALIKE',reason='Bounded representative January archives; Binance Vision attribution and identical research license retained')
 elif p.suffix=='.whl':
  q.update(license_decision='THIRD_PARTY_LICENSES_PRESERVED_IN_WHEEL_DIST_INFO',reason='Pinned official PyPI wheel; bundled license/notices remain intact; CI uses hash-locked platform wheels')
 elif '/dependencies/' in r['path']:
  q.update(license_decision='PYPI_PUBLIC_METADATA_RESEARCH_PROVENANCE')
 elif 'dev-models' in r['path'] or 'results' in p.name or 'freeze' in p.name:
  q.update(license_decision='RESEARCH_OUTPUT_BINANCE_DERIVATIVES_CC_BY_NC_SA_4_0_WHERE_APPLICABLE')
 if q['transfer_status']=='INCLUDED':
  included[r['sha256']]=raw
 q['github_url']='https://github.com/scannercrypto0-gif/zs-crypto-signals/tree/'+BRANCH+'/studies/'+STUDY if q['transfer_status']=='INCLUDED' else None
 matrix.append(q)
inventory=dict(schema='zs-custody-file-inventory-015-v1',study_id=STUDY,
 source_scope='010-014 evidence roots, frozen work snapshots and standalone research tools; one-pass legacy disk read',
 source_counts=dict(files=len(rows),logical_bytes=sum(r['bytes']for r in rows),unique_files=len(unique),unique_bytes=sum(r['bytes']for r in unique.values())),
 files=matrix, disposition_counts=dict(collections.Counter(x['transfer_status']for x in matrix)),
 custody='PARTIAL_WITH_BLOCKERS',full_reproducible=False,
 source_notice='Binance Vision attribution CC BY-NC-SA 4.0 for applicable raw and derived works. Tardis reports are non-reconstructable aggregate research only. Third-party wheel license notices are preserved. No commercial or production authorization.',
 rights_sources=['https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md','https://creativecommons.org/licenses/by-nc-sa/4.0/','https://docs.tardis.dev/legal/terms-of-service'],
 withheld_policy='No session packets or unnecessary certificates; no raw market archive exported under this budget. No local fallback is an accepted custody source.')
# Preserve all exact original bytes once; aliases reconstruct via full inventory.
content={'inventory.json':canonical_bytes(inventory),**{'objects/'+k:v for k,v in sorted(included.items())}}
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w',format=tarfile.USTAR_FORMAT)as tar:
 for name,raw in content.items():
  info=tarfile.TarInfo(name);info.size=len(raw);info.mtime=0;info.mode=0o600
  tar.addfile(info,io.BytesIO(raw))
archive=gzip.compress(buf.getvalue(),compresslevel=9,mtime=0)
parts=[archive[i:i+600000]for i in range(0,len(archive),600000)]
at=datetime.now(timezone.utc).isoformat()
def record(event,payload):
 return make_record(study_id=STUDY,event_id=event,record_type='source_snapshot',source_id='owner-order-015-custody-migration',received_at=at,available_at=at,payload=payload)
records={'control':record('control',dict(kind='custody-control-v1',archive_bytes=len(archive),archive_sha256=hashlib.sha256(archive).hexdigest(),chunk_count=len(parts),codec='deterministic-tar-gzip-base64',full_reproducible=False,inventory_sha256=hashlib.sha256(content['inventory.json']).hexdigest()))}
for i,part in enumerate(parts):
 event=f'chunk-{i:03d}'
 records[event]=record(event,dict(kind='custody-chunk-v1',ordinal=i,sha256=hashlib.sha256(part).hexdigest(),data_base64=base64.b64encode(part).decode('ascii')))
manifest=prepare_manifest(STUDY,records,created_at=at)
transport=MockContentsTransport();backend=GitHubEvidenceBackend(STUDY,branch=BRANCH,transport=transport,enabled=True)
journal=SingleStudyJournal(STUDY,backend,lambda:datetime.now(timezone.utc))
result=persist_packet(journal,manifest,records)
assert result.ok,result
assert verify_snapshot(STUDY,transport.files).ok
out=T/'packet';out.mkdir(exist_ok=True)
for path,raw in transport.files.items():
 p=out/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
budget=sum(len(x)for x in transport.files.values())
assert budget<10*1024*1024-20000,budget
anchor=dict(study_id=STUDY,branch=BRANCH,manifest_sha256=result.manifest_sha256,archive_bytes=len(archive),packet_bytes=budget,inventory_sha256=hashlib.sha256(content['inventory.json']).hexdigest(),files=len(matrix),included_paths=sum(x['transfer_status']=='INCLUDED'for x in matrix),unique_objects=len(included),disposition_counts=inventory['disposition_counts'])
(T/'anchor.json').write_bytes(canonical_bytes(anchor))
(T/'inventory-final.json').write_bytes(content['inventory.json'])
print(json.dumps(anchor,indent=2))
