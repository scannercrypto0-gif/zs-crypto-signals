"""Post-holdout, preregistered label-free lineage audit; no new inference/fit."""
import argparse,hashlib,json
from pathlib import Path
import zs_smart_gate.stage03_science_expanded as science

p=argparse.ArgumentParser();p.add_argument('--root',required=True);args=p.parse_args()
root=Path(args.root).resolve(strict=True)
if root.drive.upper()!='D:':raise SystemExit('PRIVATE_D_REQUIRED')
manifest=json.loads((root/'manifest.json').read_text())
freeze=json.loads((root/'dev-freeze.json').read_text());raw=(root/'dev-models.json').read_bytes()
if hashlib.sha256(raw).hexdigest()!=freeze['models_sha256']:raise SystemExit('MODEL_CHANGED')
models=json.loads(raw);data=science.load_archives(root/'batch-B',manifest)
result={'kind':'LABEL_FREE_PREDECLARED_OVERLAP_AUDIT_NO_NEW_HOLDOUT_SELECTION',
 'frozen_experiment_code':manifest['code_sha'],'models_sha256':freeze['models_sha256'],
 'audit_runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'audit_module_sha256':hashlib.sha256(Path(science.__file__).read_bytes()).hexdigest()}
for phase in ('DEV','OOS'):
    records,_=science.build_records(data,phase)
    result[phase]=science.overlap_audit(records,models)
output=root/'lineage-audit.json'
with output.open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({'status':'COMPLETED_LABEL_FREE_AUDIT','sha256':hashlib.sha256(output.read_bytes()).hexdigest()}))
