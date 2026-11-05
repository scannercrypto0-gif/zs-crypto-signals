"""020-A native GitHub permission probe only. ZERO market/time-source calls."""
import argparse
import json
import os
from pathlib import Path
import time
from zs_smart_gate.pilot020 import canonical,sha,validate_manifest
from zs_smart_gate.pilot020_native import credentials,github_json,Store,fingerprint,on_d
from zs_smart_gate.github_evidence_backend import GitHubContentsTransport

p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);a=p.parse_args()
try:
    if os.name!='nt' or not on_d(Path(a.manifest).resolve()):raise ValueError('OWNER_WINDOWS_D_ONLY')
    m=json.loads(Path(a.manifest).read_bytes());validate_manifest(m)
    if fingerprint()!=m['host_fingerprint_sha256']:raise ValueError('HOST_OR_BOOT_CHANGED')
    token=credentials();meta=github_json('',token)
    if meta.get('private') is not True or not meta.get('permissions',{}).get('push'):raise ValueError('PRIVATE_PUSH_REQUIRED')
    store=Store(GitHubContentsTransport('scannercrypto0-gif/zs-crypto-signals',token,timeout=5),m)
    name='native-preflight-probe-'+str(time.time_ns())+'.json'
    result=dict(status='NATIVE_GITHUB_STORAGE_WRITE_READBACK_PASS',manifest_sha256=sha(m),code_sha=m['code_sha'],
        host_fingerprint_sha256=fingerprint(),market_requests=0,credential_persisted=False)
    store.create(name,canonical(result));print(json.dumps(result,sort_keys=True))
except Exception as exc:
    print(json.dumps(dict(status='NATIVE_GITHUB_STORAGE_BLOCKED',reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__,market_requests=0)))
    raise SystemExit(2)
