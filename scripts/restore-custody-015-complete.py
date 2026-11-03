"""Offline GitHub-only aggregate restoration and original raw audit reproduction."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
from zs_smart_gate.custody_aggregate import restore_aggregate
from zs_smart_gate.custody_restore import materialize
from zs_smart_gate.evidence_journal import canonical_bytes

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--snapshot',required=True)
    p.add_argument('--destination',required=True)
    p.add_argument('--anchor',default='research/custody-015/aggregate-anchor.json')
    a=p.parse_args()
    anchor=json.loads(Path(a.anchor).read_bytes())
    def denied(*args,**kwargs):raise RuntimeError('NETWORK_DISABLED_DURING_REPRODUCTION')
    socket.socket=denied;socket.create_connection=denied
    report=restore_aggregate(a.snapshot,a.destination,anchor)
    root=Path(a.destination).resolve();combined=root/'combined'
    for study in ['science-010B','science-012','science-010D','science-010E']:
        materialize(combined,'evidence/'+study+'/',root/'audit-input'/study)
    spec=importlib.util.spec_from_file_location('original_raw_audit',Path(__file__).with_name('stage03-raw-audit.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    audit=module.audit(root/'audit-input')
    if hashlib.sha256(canonical_bytes(audit)).hexdigest()!=anchor['original_raw_audit_canonical_sha256']:
        raise ValueError('ORIGINAL_AUDIT_OUTPUT_NOT_REPRODUCED')
    if audit['archive_count']!=48 or not all(audit['replay_byte_matches'].values())or not all(audit['original_artifacts_unchanged'].values()):
        raise ValueError('ORIGINAL_FULL_RAW_AUDIT_CHANGED')
    report.update(raw_audit_status='PASS_48_ARCHIVES_AND_EXISTING_QUOTE_SAMPLES',
                  raw_audit_sha256=hashlib.sha256(canonical_bytes(audit)).hexdigest(),
                  archive_count=audit['archive_count'],rows=audit['rows'],
                  replay_byte_matches=audit['replay_byte_matches'],
                  quotes=audit['quotes'],network_during_reproduction='DISABLED',
                  execution_platform=sys.platform,fresh_provider_requests=0,
                  scientific_acceptance='PENDING_PM_PIT_FAIL_HOLD',
                  limitation='Custody and audit replay only; not newly independent DEV/OOS, publication proof, full historical liquidity coverage or Forward accrual')
    (root/'raw-audit-reproduced.json').write_bytes(canonical_bytes(audit))
    print('ZS015_COMPLETE_RESTORE_RESULT='+json.dumps(report,sort_keys=True))

if __name__=='__main__':main()
