from pathlib import Path
import sys,json,hashlib
from datetime import datetime,timezone
T=Path(__file__).resolve().parent;W=T/'work';sys.path[:0]=[str(W/'src'),str(W/'tests')]
from zs_smart_gate.evidence_journal import canonical_bytes,SingleStudyJournal
from zs_smart_gate.github_evidence_backend import GitHubEvidenceBackend,verify_snapshot
from zs_smart_gate.stage04_evidence_packet import make_record,prepare_manifest,persist_packet
from zs_smart_gate.integrated_research016 import evaluate,DECISION_VERSION
from test_github_evidence_backend import MockContentsTransport
study='zs03-016-engineering-revision';branch='evidence-stage03-016';at=datetime.now(timezone.utc).isoformat();records={}
def add(name,payload):
 records[name]=make_record(study_id=study,event_id=name,record_type='decision_context',source_id='016-I3-unit-domain-erratum',received_at=at,available_at=at,payload=payload)
old_archive=json.loads((T/'research-results/decisions.json').read_bytes())
old_live=json.loads((T/'live-compatibility/replay-decisions.json').read_bytes())['decisions']
sources=json.loads((T/'live-compatibility/replay-sources.json').read_bytes());superseded={};new={}
for symbol in ['BTCUSDT','ETHUSDT']:
 raw=(T/'fixtures'/(symbol+'.json')).read_bytes();data=json.loads(raw)
 d=evaluate(raw,expected_sha256=hashlib.sha256(raw).hexdigest(),decision_ms=data['received_ms']+500)
 add('archive-'+symbol,d);new['archive-'+symbol]=d
 superseded['archive-'+symbol]=hashlib.sha256(canonical_bytes(old_archive[symbol])).hexdigest()
 src=sources[symbol]
 d=evaluate(src['raw_json'].encode(),expected_sha256=src['sha256'],decision_ms=src['decision_ms'],
       source_mode='BOUNDED_COMPATIBILITY_REPLAY',market=src['market'])
 add('compat-'+symbol,d);new['compat-'+symbol]=d
 superseded['compat-'+symbol]=hashlib.sha256(canonical_bytes(old_live[symbol])).hexdigest()
add('erratum',dict(schema='ZS016_ENGINEERING_ERRATUM_I3_V1',new_decision_version=DECISION_VERSION,
 cause='Body-only child path omits inter-candle price gaps; signed_net/path is not guaranteed in[-1,1].',
 observed_old_ETH_UP='1.000601684717208182912154032',observed_old_ETH_DOWN='-0.0006016847172081829121540315',
 disposition='OLD_OUT_OF_UNIT_I3_INVALIDATED; domain-invalid ratio becomes missing/UNKNOWN; no clipping or relaxed threshold',
 scope='Engineering acceptance of the prefrozen bounded R domain; no protocol/family/alpha/DGP/cost changes or market winner',
 superseded_decision_payload_sha256=superseded,source_bytes_changed=False,calibration_changed=False,
 historical_source_commit='31a5acea2fcbbea435f24bb9e185008da6ca4050',compat_source_commit='83abbc0e03a4b97ec92135df98bb1f37762a5f36'))
m=prepare_manifest(study,records,created_at=at);t=MockContentsTransport();b=GitHubEvidenceBackend(study,branch=branch,transport=t,enabled=True)
r=persist_packet(SingleStudyJournal(study,b,lambda:datetime.now(timezone.utc)),m,records);assert r.ok,r
assert verify_snapshot(study,t.files).ok
for path,raw in t.files.items():
 p=T/'revision-packet'/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
size=sum(len(x)for x in t.files.values());old=json.loads((T/'live-anchor.json').read_bytes())['combined016_bytes'];assert size+old<10485760
a=dict(study_id=study,branch=branch,manifest_sha256=r.manifest_sha256,packet_bytes=size,combined016_bytes=old+size)
(T/'revision-anchor.json').write_bytes(canonical_bytes(a));(T/'corrected-decisions.json').write_bytes(canonical_bytes(new));print(json.dumps(a))
