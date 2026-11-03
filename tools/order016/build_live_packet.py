from pathlib import Path
import sys,json,hashlib
from datetime import datetime,timezone
T=Path(__file__).resolve().parent;W=T/'work';sys.path[:0]=[str(W/'src'),str(W/'tests')]
from zs_smart_gate.evidence_journal import canonical_bytes,SingleStudyJournal
from zs_smart_gate.github_evidence_backend import GitHubEvidenceBackend,verify_snapshot
from zs_smart_gate.stage04_evidence_packet import make_record,prepare_manifest,persist_packet
from test_github_evidence_backend import MockContentsTransport
study='zs03-016-public-compat';branch='evidence-stage03-016';at=datetime.now(timezone.utc).isoformat();records={}
def add(name,kind,payload):
 records[name]=make_record(study_id=study,event_id=name,record_type=kind,source_id='Issue25-preflight-6603902336-one-batch',received_at=at,available_at=at,payload=payload)
report=json.loads((T/'live-compatibility/report.json').read_bytes());assert report['http_attempts']==6 and report['weight_attempted']==31
for i in range(6):
 raw=(T/'live-compatibility'/f'response-{i:02d}.json').read_bytes()
 assert hashlib.sha256(raw).hexdigest()==report['responses'][i]['sha256']
 add(f'wire-{i:02d}','source_snapshot',dict(raw_json=raw.decode(),sha256=hashlib.sha256(raw).hexdigest(),capture_metadata={k:v for k,v in report['responses'][i].items()if k!='body_base64'}))
sources=json.loads((T/'live-compatibility/replay-sources.json').read_bytes())
for symbol,payload in sources.items():add('replay-source-'+symbol,'source_snapshot',payload)
add('replay-result','decision_context',json.loads((T/'live-compatibility/replay-decisions.json').read_bytes()))
add('batch-counter','scan_cycle',{k:v for k,v in report.items()if k!='responses'})
m=prepare_manifest(study,records,created_at=at);t=MockContentsTransport();b=GitHubEvidenceBackend(study,branch=branch,transport=t,enabled=True)
r=persist_packet(SingleStudyJournal(study,b,lambda:datetime.now(timezone.utc)),m,records);assert r.ok,r
assert verify_snapshot(study,t.files).ok
for path,raw in t.files.items():
 p=T/'live-packet'/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
size=sum(len(x)for x in t.files.values());old=json.loads((T/'offline-anchor.json').read_bytes())['packet_bytes'];assert size+old<10485760
a=dict(study_id=study,branch=branch,manifest_sha256=r.manifest_sha256,packet_bytes=size,combined016_bytes=size+old,source_requests=6,source_weight=31,wire_response_bytes=45853)
(T/'live-anchor.json').write_bytes(canonical_bytes(a));print(json.dumps(a))
