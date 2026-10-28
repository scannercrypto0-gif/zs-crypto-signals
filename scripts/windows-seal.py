"""Seal a clean pinned checkout after review/tests; never updates code or enables tasks.

Update/rollback: disable task, checkout the explicitly reviewed revision, rerun
offline checks, seal, uninstall/install disabled with new ConfigSha, then Enable
only with fresh OS clock proof. No automatic main update or credential storage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from zs_smart_gate.windows_operations import d_path, canonical_sha

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--reviewed-revision',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args()
repo=d_path(Path.cwd())
output=Path(args.output)
d_path(output.parent)
if output.exists():
    raise SystemExit('Refusing to overwrite a frozen deployment; choose a versioned output path')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=repo,text=True).strip()
if head != args.reviewed_revision or dirty:
    raise SystemExit('Pinned clean reviewed revision required')
paths=list((repo/'src').rglob('*.py'))+[p for p in (repo/'scripts').glob('*') if p.is_file()]
data={'version':1,'revision':head,'mode':'SIMULATION_ONLY','scope':[],
      'files':{p.relative_to(repo).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
output.write_text(json.dumps(data,sort_keys=True,indent=2),encoding='utf-8')
print(canonical_sha(data))
