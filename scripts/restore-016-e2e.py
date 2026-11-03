"""Independent clean-runner016 replay. Only pinned GitHub checkouts are inputs."""
import argparse,hashlib,importlib.util,json,socket
from pathlib import Path
from zs_smart_gate.evidence_journal import canonical_bytes
from zs_smart_gate.github_evidence_backend import verify_snapshot
from zs_smart_gate.stage04_evidence_packet import restore_from_remote
from zs_smart_gate.custody_restore import Snapshot,restore
from zs_smart_gate.integrated_research016 import evaluate
from zs_smart_gate.science016 import calibrate

def payload(root,study,event):
    return json.loads((Path(root)/'studies'/study/'receipts'/(event+'.json')).read_bytes())['payload']['payload']

def main():
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--custody',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();anchor=json.loads(Path('research/stage03-016/evidence-anchor.json').read_bytes())
    output=Path(a.output);output.mkdir(parents=True,exist_ok=False)
    def denied(*args,**kwargs):raise RuntimeError('NETWORK_DISABLED_DURING_016_REPRODUCTION')
    socket.socket=denied;socket.create_connection=denied
    checked=[]
    total=0
    for packet in anchor['packets']:
        study=packet['study_id']
        r=restore_from_remote(study_id=study,branch='evidence-stage03-016',transport=Snapshot(a.snapshot),expected_manifest_sha256=packet['manifest_sha256'])
        if not r.ok:raise ValueError(r.status)
        checked.append(dict(study=study,claim_receipt_records=r.records_checked,manifest_sha256=r.manifest_sha256))
        total+=sum(x.stat().st_size for x in (Path(a.snapshot)/'studies'/study).rglob('*')if x.is_file())
    if total!=anchor['combined_bytes']or total>10485760:raise ValueError('016_AGGREGATE_CAP_OR_BYTES')
    # Recreate source fixture from authoritative015 raw, not a local disk fixture.
    migration=restore(a.custody,output/'015-raw-input',study_id='custody-010-014-015-raw',branch='evidence-migration-015',
        manifest_sha256='aee2f65b39179906e77fa8512fe1df0da508414c434331a1fb2ff603e79df769')
    spec=importlib.util.spec_from_file_location('fixture_builder',Path(__file__).with_name('build-016-fixtures.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.extract(output/'015-raw-input',output/'fixture-lineage')
    offline='zs03-016-integrated';live='zs03-016-public-compat';revision='zs03-016-engineering-revision';decision_hashes={}
    erratum=payload(a.snapshot,revision,'erratum')
    for symbol in ['BTCUSDT','ETHUSDT']:
        src=payload(a.snapshot,offline,'source-'+symbol);raw=src['raw_json'].encode()
        if raw!=(output/'fixture-lineage'/(symbol+'.json')).read_bytes():raise ValueError('SOURCE_LINEAGE_NOT_EXACT')
        data=json.loads(raw)
        result=evaluate(raw,expected_sha256=src['sha256'],decision_ms=data['received_ms']+500)
        original=payload(a.snapshot,offline,'decision-'+symbol)
        if hashlib.sha256(canonical_bytes(original)).hexdigest()!=erratum['superseded_decision_payload_sha256']['archive-'+symbol]:
            raise ValueError('SUPERSEDED_OUTPUT_HISTORY_CHANGED')
        expected=payload(a.snapshot,revision,'archive-'+symbol)
        if canonical_bytes(result)!=canonical_bytes(expected):raise ValueError('ARCHIVE_DECISION_NOT_REPRODUCED')
        decision_hashes['archive-'+symbol]=hashlib.sha256(canonical_bytes(result)).hexdigest()
        captured=payload(a.snapshot,live,'replay-source-'+symbol)
        original_live=payload(a.snapshot,live,'replay-result')['decisions'][symbol]
        if hashlib.sha256(canonical_bytes(original_live)).hexdigest()!=erratum['superseded_decision_payload_sha256']['compat-'+symbol]:
            raise ValueError('SUPERSEDED_LIVE_REPLAY_HISTORY_CHANGED')
        expected_live=payload(a.snapshot,revision,'compat-'+symbol)
        result_live=evaluate(captured['raw_json'].encode(),expected_sha256=captured['sha256'],
            decision_ms=captured['decision_ms'],source_mode='BOUNDED_COMPATIBILITY_REPLAY',market=captured['market'])
        if canonical_bytes(result_live)!=canonical_bytes(expected_live):raise ValueError('COMPATIBILITY_REPLAY_NOT_REPRODUCED')
        if result_live['score']is not None or result_live['publishable']:raise ValueError('FORBIDDEN_PRODUCTION_PROMOTION')
        decision_hashes['compatibility-'+symbol]=hashlib.sha256(canonical_bytes(result_live)).hexdigest()
        if symbol=='ETHUSDT'and (expected['features']['INTRADAY:1']['I3']['value']is not None or
             float(original['features']['INTRADAY:1']['I3']['value'])<=1):
            raise ValueError('I3_ERRATUM_NOT_ENFORCED')
    frozen=payload(a.snapshot,offline,'protocol')
    local=Path('research/stage03-016/protocol-016.json').read_bytes()
    if hashlib.sha256(local).hexdigest()!=frozen['protocol_sha256']:raise ValueError('FROZEN_PROTOCOL_CHANGED')
    calibration=calibrate(frozen['protocol'])
    expected_calibration=payload(a.snapshot,offline,'calibration')
    if canonical_bytes(calibration)!=canonical_bytes(expected_calibration):raise ValueError('CALIBRATION_NOT_REPRODUCED')
    counter=payload(a.snapshot,live,'batch-counter')
    if (counter['http_attempts'],counter['weight_attempted'],counter['response_bytes'])!=(6,31,45853):raise ValueError('LIVE_COUNTER_CONFLICT')
    report=dict(status='ENGINEERING_E2E_PASS_CANDIDATE',source='PINNED_GITHUB_ONLY',stage04=checked,
        source_lineage='EXACT_ORIGINAL_BINANCE_ARCHIVE_SUBSET_VERIFIED',decision_hashes=decision_hashes,
        calibration_sha256=hashlib.sha256(canonical_bytes(calibration)).hexdigest(),
        live_probe_attempts=6,live_probe_weight=31,live_probe_response_bytes=45853,
        network_during_reproduction='DISABLED',new_provider_requests_in_CI=0,
        new_eligible_OOS_events=0,forward_live_capture_events=0,
        prospective_causality='HOLD_INDEPENDENT_UTC_PROOF_MISSING',historical_publisher_pit='HOLD',
        scientific_winner=None,full_V2='UNAVAILABLE',evidence_bytes=total,spool='TEMPORARY_RUNNER_ONLY',
        erratum='I3_OUT_OF_UNIT_SUPERSEDED_NO_SILENT_CLIPPING',decision_version=erratum['new_decision_version'],
        migration_read_only='ACCEPTED015_RAW_READ_FOR_NEW_SOURCE_LINEAGE_NOT_RE_MIGRATION')
    (output/'reproduction-result.json').write_bytes(canonical_bytes(report))
    print('ZS016_REPRODUCTION_RESULT='+json.dumps(report,sort_keys=True))

if __name__=='__main__':main()
