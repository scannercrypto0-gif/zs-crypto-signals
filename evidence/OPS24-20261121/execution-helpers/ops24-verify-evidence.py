"""Verify exact permitted evidence bytes from a clean GitHub checkout. Offline."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('root',type=Path)
args=p.parse_args()
root=args.root.resolve()
raw=(root/'SHA256SUMS.json').read_bytes()
manifest=json.loads(raw)
seen=set()
for row in manifest['files']:
 path=(root/row['path']).resolve()
 if root not in path.parents or path.is_symlink() or row['path'] in seen:
  raise SystemExit('INVALID_MANIFEST_PATH')
 seen.add(row['path'])
 data=path.read_bytes()
 if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
  raise SystemExit('HASH_MISMATCH:'+row['path'])
actual={path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file()}
if actual != seen|{'SHA256SUMS.json'}:
 raise SystemExit('UNLISTED_OR_MISSING_EVIDENCE')
print(json.dumps(dict(status='PASS',files=len(seen),manifest_sha256=hashlib.sha256(raw).hexdigest(),source_head=manifest['source_head'],source_tree=manifest['source_tree'],bytes=sum(row['bytes'] for row in manifest['files']))))
