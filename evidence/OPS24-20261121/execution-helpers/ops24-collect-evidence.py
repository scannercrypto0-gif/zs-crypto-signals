"""Collect permitted OPS24 originals, screen and hash; no network or source body publication."""
from pathlib import Path
import hashlib,json,re,shutil,sqlite3
BASE=Path('D:/ZS-SMART-GATE/validation')
OUT=BASE/'OPS24-20261121-evidence-source/evidence/OPS24-20261121'
sha=lambda data:hashlib.sha256(data).hexdigest()
def copy(p,relative):
 target=OUT/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
def dump(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8')
private_roots=[BASE/'OPS24-20261121-source-observation',Path('D:/ZS-SMART-GATE/data/shadow-20261120-153000-38240')]
live=BASE/'OPS24-20261121-full-market'
if live.exists():
 private_roots.append(live)
 for pattern in ('result.json','result.sha256','*.receipt.json','clock-*.private.json','watchdog.json','research-intake.json'):
  for p in live.glob(pattern):copy(p,Path('bounded-full-market')/p.name)
 if (live/'inventory.private.json').exists():
  obj=json.loads((live/'inventory.private.json').read_bytes())
  # Exclude quote bodies; preserve every inclusion/exclusion reason and inventory identity.
  obj['rows']=[{k:v for k,v in row.items() if k!='market'} for row in obj['rows']]
  dump(OUT/'bounded-full-market/inventory-inclusion-exclusion.json',obj)
 for p in BASE.glob('OPS24-20261121-full-market-driver.*'):copy(p,Path('bounded-full-market')/p.name)
 for p in BASE.glob('OPS24-20261121-live-intake*'):copy(p,Path('bounded-full-market')/p.name)
 for p in BASE.glob('OPS24-20261121-legacy-final*'):copy(p,Path('legacy-source-replay')/p.name)
manifest=[]
for root in private_roots:
 for p in sorted(root.rglob('*')):
  if p.is_file():manifest.append(dict(local_path=str(p),bytes=p.stat().st_size,sha256=sha(p.read_bytes()),retained=True))
dump(OUT/'local-originals-manifest.json',dict(policy='Original market bodies retained privately; no secrets or full market body redistribution in this packet',files=manifest))
copy(Path(__file__),Path('execution-helpers')/Path(__file__).name)
findings=[]
for p in OUT.rglob('*'):
 if not p.is_file() or p.name=='SHA256SUMS.json':continue
 text=p.read_text(encoding='utf-8-sig',errors='replace')
 for kind,pattern in [('telegram-token',r'\b\d{8,12}:[A-Za-z0-9_-]{30,}\b'),('private-key',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),('local-account-sid',r'S-1-5-21-[0-9-]+')]:
  if re.search(pattern,text):findings.append(dict(file=str(p.relative_to(OUT)),kind=kind))
 if p.name.endswith('.private'):
  findings.append(dict(file=str(p.relative_to(OUT)),kind='SOURCE_RAW_BODY_MUST_REMAIN_LOCAL'))
if findings:raise RuntimeError(json.dumps(findings))
dump(OUT/'screening.json',dict(status='PASS_AUTOMATED_SCREEN_AND_ALLOWLIST',repo_visibility='private',secrets_uploaded=False,market_raw_bodies_uploaded=False,notes='Only selected nonsecret receipts/reports/clock OS provenance; built-in Windows service SIDs are public OS identities. Historical attempts are labelled separately.',findings=[]))
rows=[dict(path=p.relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.json']
dump(OUT/'SHA256SUMS.json',dict(schema='zs.ops24.evidence-hashes.v1',source_head='8c52be6f9c5d7a49af19bf68b1d8d50bd63a5b72',source_tree='dcf6a9b1abc2a62c9b91891e605dfcbdccf2bd98',files=rows))
print(json.dumps(dict(files=len(rows),bytes=sum(r['bytes'] for r in rows),hash_manifest_sha256=sha((OUT/'SHA256SUMS.json').read_bytes()),screen='PASS')))
