from pathlib import Path
import sys,json,hashlib
from datetime import datetime,timezone
T=Path(__file__).resolve().parent;W=T/'work'
sys.path[:0]=[str(W/'src'),str(W/'tests')]
from zs_smart_gate.evidence_journal import canonical_bytes,SingleStudyJournal
from zs_smart_gate.github_evidence_backend import GitHubEvidenceBackend,verify_snapshot
from zs_smart_gate.stage04_evidence_packet import make_record,prepare_manifest,persist_packet
from zs_smart_gate.integrated_research016 import evaluate
from test_github_evidence_backend import MockContentsTransport
study='zs03-016-integrated';branch='evidence-stage03-016';now=datetime.now(timezone.utc).isoformat()
records={}
def add(event,kind,payload):
 records[event]=make_record(study_id=study,event_id=event,record_type=kind,source_id='016-frozen-archive-research',received_at=now,available_at=now,payload=payload)
decisions={}
for symbol in ['BTCUSDT','ETHUSDT']:
 raw=(T/'fixtures'/(symbol+'.json')).read_bytes();data=json.loads(raw)
 sha=hashlib.sha256(raw).hexdigest()
 add('source-'+symbol,'source_snapshot',dict(raw_json=raw.decode(),sha256=sha,source_archive_sha256=data['provenance']['source_archive_sha256']))
 decision=evaluate(raw,expected_sha256=sha,decision_ms=data['received_ms']+500)
 decisions[symbol]=decision;add('decision-'+symbol,'decision_context',decision)
(T/'research-results/decisions.json').write_bytes(canonical_bytes(decisions))
for name,kind in [('calibration','experiment_manifest'),('cost-scenarios','experiment_manifest'),('forward-readiness','decision_context')]:
 add(name,kind,json.loads((T/'research-results'/(name+'.json')).read_bytes())if name!='cost-scenarios'else dict(scenarios=json.loads((T/'research-results'/(name+'.json')).read_bytes())))
add('protocol','experiment_manifest',dict(protocol=json.loads((W/'research/stage03-016/protocol-016.json').read_bytes()),
 protocol_sha256=hashlib.sha256((W/'research/stage03-016/protocol-016.json').read_bytes()).hexdigest(),
 protocol_freeze_commit='77ea1940765d2f6874330f075b3f34dcb1d74caf',science_implementation_freeze='be884b093cbef17387127ecba9c3c2182e084a37'))
add('probe-plan','experiment_manifest',json.loads((W/'research/stage03-016/public-probe-plan.json').read_bytes()))
add('forward-request','experiment_manifest',json.loads((W/'research/stage03-016/forward-scope-request.json').read_bytes()))
m=prepare_manifest(study,records,created_at=now)
transport=MockContentsTransport();backend=GitHubEvidenceBackend(study,branch=branch,transport=transport,enabled=True)
r=persist_packet(SingleStudyJournal(study,backend,lambda:datetime.now(timezone.utc)),m,records)
assert r.ok,r
assert verify_snapshot(study,transport.files).ok
for path,raw in transport.files.items():
 p=T/'offline-packet'/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
budget=sum(len(v)for v in transport.files.values());assert budget<2*1024*1024
a=dict(study_id=study,branch=branch,manifest_sha256=r.manifest_sha256,packet_bytes=budget,record_count=len(records),
 expected_calibration_sha256=hashlib.sha256(canonical_bytes(json.loads((T/'research-results/calibration.json').read_bytes()))).hexdigest())
(T/'offline-anchor.json').write_bytes(canonical_bytes(a));print(json.dumps(a))
