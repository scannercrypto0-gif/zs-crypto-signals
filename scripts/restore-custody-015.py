"""GitHub-only offline restore check; invoked after two pinned GitHub checkouts."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import socket
import sys
import zipfile
from zs_smart_gate.custody_restore import restore, materialize
from zs_smart_gate.evidence_journal import canonical_bytes
from zs_smart_gate.stage03_bounded_inference import bounded_interval, paired_gain

def representative(restored):
    inventory = json.loads((restored/'inventory.json').read_bytes())
    selected = {}
    for x in inventory['files']:
        name = Path(x['path']).name
        if x['transfer_status']=='INCLUDED' and name.endswith('.zip'):
            selected.setdefault(x['sha256'], x)
    archive_checks = []
    for sha, item in sorted(selected.items()):
        raw = (restored/'objects'/sha).read_bytes()
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if len(z.namelist()) != 1 or z.testzip() is not None:
                raise ValueError('ARCHIVE_CRC_FAIL')
            rows = list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode('utf8'))))
        if not rows or any(len(r)!=12 for r in rows):
            raise ValueError('KLINE_SCHEMA_FAIL')
        opens = [int(r[0]) for r in rows]
        if opens != sorted(set(opens)):
            raise ValueError('KLINE_SEQUENCE_FAIL')
        archive_checks.append(dict(name=Path(item['path']).name,sha256=sha,rows=len(rows),first_open=opens[0],last_open=opens[-1]))
    if len(archive_checks)!=4:
        raise ValueError('REPRESENTATIVE_ARCHIVES_MISSING')
    # Deterministic synthetic reproduction; never promoted to market performance.
    gains = [paired_gain(.25,.75,y,1) for y in [-1,-.5,0,.5,1]]
    return dict(archive_checks=archive_checks, synthetic_gains=gains,
                conditional_interval=bounded_interval(gains),
                scientific_state='PIT_FAIL_HOLD',full_historical_replay='BLOCKED_CAPACITY',
                source='FOUR_EXISTING_JANUARY_ARCHIVES_AND_SYNTHETIC_VECTOR',fresh_market_requests=0)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--snapshot',required=True)
    p.add_argument('--destination',required=True)
    p.add_argument('--anchor',default='research/custody-015/anchor.json')
    p.add_argument('--expected',default='research/custody-015/representative-expected.json')
    a=p.parse_args()
    anchor=json.loads(Path(a.anchor).read_bytes())
    # Network disabled throughout restore and computation, after GitHub retrieval.
    def denied(*args,**kwargs):
        raise RuntimeError('NETWORK_DISABLED_DURING_REPRODUCTION')
    socket.socket=denied
    socket.create_connection=denied
    report=restore(a.snapshot,a.destination,study_id=anchor['study_id'],branch=anchor['branch'],manifest_sha256=anchor['manifest_sha256'])
    restored=Path(a.destination).resolve()
    actual=representative(restored)
    expected=json.loads(Path(a.expected).read_bytes())
    if canonical_bytes(actual)!=canonical_bytes(expected):
        raise ValueError('REPRESENTATIVE_REPRODUCTION_CHANGED')
    # Rebuild all code/tests/protocol snapshots; exact original bytes verified.
    historical=restored/'historical-code'
    count=materialize(restored,'work/stage03-012/',historical)
    report.update(representative_status='BYTE_EXACT_REPRODUCTION_PASS',
                  representative_sha256=hashlib.sha256(canonical_bytes(actual)).hexdigest(),
                  original_code_tree_files=count,network_during_reproduction='DISABLED',
                  execution_platform=sys.platform,
                  local_owner_disks=('NOT_AVAILABLE_ON_CLEAN_LINUX_RUNNER' if sys.platform=='linux' else 'NOT_CLAIMED_FOR_LOCAL_CHECK'),
                  evidence_commit=anchor['evidence_commit'],
                  custody_status='GITHUB_ONLY_CUSTODY_PARTIAL_WITH_BLOCKERS')
    print('ZS015_RESTORE_RESULT='+json.dumps(report,sort_keys=True))

if __name__=='__main__':
    main()
