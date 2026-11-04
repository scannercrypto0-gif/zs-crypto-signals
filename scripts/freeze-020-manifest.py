"""Freeze exactly one future target; publish returned bytes to GitHub before use."""
import argparse
import json
from pathlib import Path
import time
from zs_smart_gate.pilot020 import sha,canonical,validate_manifest
from zs_smart_gate.pilot020_native import fingerprint,on_d

p=argparse.ArgumentParser();p.add_argument('--code-sha',required=True);p.add_argument('--output',required=True);a=p.parse_args()
if not on_d(Path(a.output).resolve()):raise SystemExit('D_OUTPUT_ONLY')
plan=json.loads(Path('research/stage03-020/field-plan.json').read_bytes())
m=dict(plan['manifest_limits']);m.update(code_sha=a.code_sha,host_fingerprint_sha256=fingerprint(),
    plan_sha256=sha(plan),frozen_at=int(time.time()),target_close=plan['target_close'])
m.update(start_at=m['target_close']-240,end_at=m['target_close']+120,expires_at=m['frozen_at']+86400,
         study_id='zs03-020-'+str(m['target_close']),evidence_branch='evidence-stage03-020')
validate_manifest(m)
with Path(a.output).open('xb') as f:f.write(canonical(m))
print(json.dumps(dict(manifest_sha256=sha(m),target_close=m['target_close'],expires_at=m['expires_at']),sort_keys=True))
