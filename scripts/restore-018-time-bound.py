"""Re-evaluate pinned GitHub017 evidence under V2, never rewrite its outputs.

Offline computation deliberately disables sockets. Fresh CI supplies the exact
GitHub017 checkout; a working-tree fixture or owner disk is never an authority.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
from zs_smart_gate.evidence_journal import canonical_bytes
from zs_smart_gate.prospective_causality_v2 import VERSION, utc_gate

SOURCE_COMMIT = '445d7b04fd834c2dc84ad3d296e406ea357c055e'
SAMPLES_SHA256 = 'da45a4a47990a2d6977472826869c2b22b10f86a492177d04734269de89bfe1d'


def reevaluate(source):
    root=Path(source)/'research/stage03-017'
    manifest=json.loads((root/'manifest.json').read_bytes())
    if hashlib.sha256((root/'samples.json').read_bytes()).hexdigest()!=SAMPLES_SHA256:
        raise ValueError('PINNED017_SOURCE_CHANGED')
    for name,sha in manifest.items():
        if Path(name).name!=name or hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:
            raise ValueError('017_MANIFEST_CHANGED')
    spec=importlib.util.spec_from_file_location('original017',Path(source)/'scripts/verify-017-clock.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    previous=helper.check(root/'samples.json')
    saved=json.loads((root/'verification.json').read_bytes())
    if canonical_bytes(previous)!=canonical_bytes(saved):
        raise ValueError('017_ORIGINAL_RESULT_NOT_REPRODUCED')
    rows=[]
    for row in previous['results']:
        bound=row['interval']['local_error_bound_seconds']
        rows.append(dict(index=row['index'],original_conditional_bound_seconds=bound,
                         original_lt_1s=row['interval']['below_one_second'],
                         v2_numerically_lt_1p5s=bound<1.5,
                         qualified_clock=False,qualification='HOLD',
                         missing=['INDEPENDENT_LOCAL_COUNTER_CALIBRATION','MAXIMUM_FUTURE_DRIFT_PROOF',
                                  'INDEPENDENT_TOTAL_ERROR_BUDGET_ADMISSION']))
    return dict(version=VERSION,clock_uncertainty_limit_seconds=1.5,source_commit=SOURCE_COMMIT,
                source_samples_sha256=SAMPLES_SHA256,original017_status=previous['status'],
                rows=rows,status='PROSPECTIVE_UTC_HOLD',forward='NOT_ARMED',
                new_provider_requests=0,new_oos_events=0,previous_outputs_modified=False,
                actual_utc_gate=utc_gate(None,wall=0,mono=0,epoch='not-admitted'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--github017',required=True);p.add_argument('--output',required=True)
    p.add_argument('--verify-history',action='store_true')
    args=p.parse_args()
    def denied(*a,**k):raise RuntimeError('NETWORK_DISABLED_DURING_018_REPRODUCTION')
    socket.socket=denied;socket.create_connection=denied;socket.getaddrinfo=denied
    if args.verify_history:
        original_head=subprocess.check_output(['git','-C',args.github017,'rev-parse','HEAD'],text=True).strip()
        if original_head!=SOURCE_COMMIT:raise ValueError('GITHUB017_CHECKOUT_NOT_PINNED')
        frozen=json.loads(Path('research/stage03-018/preserved-git-blobs.json').read_bytes())
        for path,sha in frozen.items():
            actual=subprocess.check_output(['git','rev-parse','HEAD:'+path],text=True).strip()
            if actual!=sha:raise ValueError('FROZEN_PRE018_FILE_CHANGED:'+path)
    report=reevaluate(args.github017)
    data=canonical_bytes(report)
    expected=Path('research/stage03-018/reevaluation-017.json').read_bytes()
    if data!=expected:raise ValueError('V2_REEVALUATION_NOT_EXACT')
    Path(args.output).write_bytes(data)
    print('ZS018_REPRODUCED='+json.dumps(report,sort_keys=True))


if __name__=='__main__':main()
