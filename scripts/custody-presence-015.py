from pathlib import Path
import json,hashlib,collections
T=Path(__file__).resolve().parent
trees=[json.loads((T/f'start-tree-{i}.json').read_bytes())for i in range(4)]
lookup=collections.defaultdict(list)
for t in trees:
 for f in t['tree']:
  if f['type']=='blob':lookup[f['sha']].append({'ref':t['ref'],'path':f['path']})
rows=json.loads((T/'migration-inventory-local.json').read_bytes());matches={}
counts=collections.Counter()
for row in rows:
 raw=(T/'incoming'/row['path']).read_bytes()
 gitsha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
 if gitsha in lookup:
  matches[row['sha256']]=lookup[gitsha]
  counts['GITHUB_PRESENT_VERIFIED']+=1
 else:counts['LOCAL_ONLY_AT_START']+=1
result={'schema':'zs-custody-start-state-overlay-v1','matching':'Git blob SHA-1 and byte length matched against GitHub recursive trees; original SHA-256 retained in inventory',
 'refs':[x['ref']for x in trees],'path_counts':dict(counts),'existing_by_original_sha256':matches,
 'interpretation':'Override initial classification to GITHUB_PRESENT_VERIFIED for matching SHA-256 rows. main vs PR-only is determined by listed ref. New evidence copy does not imply code merged to main.'}
(T/'portable/research/custody-015/github-start-presence.json').write_text(json.dumps(result,sort_keys=True,separators=(',',':')))
print(dict(counts),len(matches))
