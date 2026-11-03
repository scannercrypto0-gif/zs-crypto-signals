"""Owner-approved raw supplement; cumulative original+proof+raw <=48MiB."""
from pathlib import Path
import sys,json,io,tarfile,gzip,hashlib,base64
from datetime import datetime,timezone
T=Path(__file__).resolve().parent;W=T/'portable'
sys.path[:0]=[str(W/'src'),str(W/'tests')]
from zs_smart_gate.evidence_journal import SingleStudyJournal,canonical_bytes,study_capacity
from zs_smart_gate.github_evidence_backend import GitHubEvidenceBackend,verify_snapshot
from zs_smart_gate.stage04_evidence_packet import make_record,prepare_manifest,persist_packet
from test_github_evidence_backend import MockContentsTransport
STUDY='custody-010-014-015-raw';BRANCH='evidence-migration-015'
old=json.loads((T/'inventory-final.json').read_bytes())
files=[dict(x,transfer_status='INCLUDED',review_status='HASH_VERIFIED_PENDING_REMOTE_RESTORE_PM',
             reason='Owner approved consolidated 48MiB migration capacity; exact existing raw bytes, no new provider acquisition')
       for x in old['files']if x['transfer_status']=='BLOCKED_CAPACITY']
objects={}
for item in files:
 raw=(T/'incoming'/item['path']).read_bytes()
 assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
 objects[item['sha256']]=raw
inventory=dict(schema='zs-custody-015-raw-supplement-v1',files=files,
 logical_study='custody-010-014-015',approval='Issue25 comment6600760450: explicit owner 48MiB capacity decision',
 rights='PRIVATE INTERNAL NONCOMMERCIAL RESEARCH ONLY; Binance Vision CC BY-NC-SA 4.0, Tardis clauses9.1/9.5/9.6 Customer Users and confidential cloud custody. No public redistribution, commercial licensing or foundation-model training.',
 source_notice='Binance Vision attribution applies to original ZIPs and derived altered-negative ZIP fixture. Tardis BTC/ETH sample originals retain provider rights.',
 prior_manifest_sha256=json.loads((T/'anchor.json').read_bytes())['manifest_sha256'],
 publication_proved=False,full_scientific_reproducible=False)
content={'inventory.json':canonical_bytes(inventory),**{'objects/'+k:v for k,v in sorted(objects.items())}}
b=io.BytesIO()
with tarfile.open(fileobj=b,mode='w',format=tarfile.USTAR_FORMAT)as tar:
 for name,raw in content.items():
  i=tarfile.TarInfo(name);i.size=len(raw);i.mode=0o600;i.mtime=0;tar.addfile(i,io.BytesIO(raw))
archive=gzip.compress(b.getvalue(),compresslevel=9,mtime=0)
parts=[archive[i:i+660000]for i in range(0,len(archive),660000)]
now=datetime.now(timezone.utc).isoformat()
def record(event,payload):
 return make_record(study_id=STUDY,event_id=event,record_type='source_snapshot',source_id='owner-approved-015-existing-raw-migration',received_at=now,available_at=now,payload=payload)
records={'control':record('control',dict(kind='custody-control-v1',archive_bytes=len(archive),archive_sha256=hashlib.sha256(archive).hexdigest(),chunk_count=len(parts),codec='deterministic-tar-gzip-base64',inventory_sha256=hashlib.sha256(content['inventory.json']).hexdigest(),full_reproducible=False))}
for n,part in enumerate(parts):
 event=f'chunk-{n:03d}'
 records[event]=record(event,dict(kind='custody-chunk-v1',ordinal=n,sha256=hashlib.sha256(part).hexdigest(),data_base64=base64.b64encode(part).decode()))
m=prepare_manifest(STUDY,records,created_at=now)
transport=MockContentsTransport();backend=GitHubEvidenceBackend(STUDY,branch=BRANCH,transport=transport,enabled=True,max_study_bytes=study_capacity(STUDY))
r=persist_packet(SingleStudyJournal(STUDY,backend,lambda:datetime.now(timezone.utc)),m,records)
assert r.ok,r
assert verify_snapshot(STUDY,transport.files).ok
size=sum(len(x)for x in transport.files.values())
prior=json.loads((T/'proof-anchor.json').read_bytes())['combined_migration_and_verification_bytes']
assert prior+size < 48*1024*1024-500000
for path,raw in transport.files.items():
 p=T/'raw-packet'/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
a=dict(study_id=STUDY,branch=BRANCH,manifest_sha256=r.manifest_sha256,archive_sha256=hashlib.sha256(archive).hexdigest(),packet_bytes=size,
 prior_total_bytes=prior,combined_bytes=prior+size,cap_bytes=study_capacity(STUDY),chunks=len(parts),paths=len(files),unique_files=len(objects),original_unique_bytes=sum(len(x)for x in objects.values()))
(T/'raw-anchor.json').write_bytes(canonical_bytes(a));print(json.dumps(a,indent=2))
