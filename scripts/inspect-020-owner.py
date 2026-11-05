"""Finite native preflight inspection. No Binance/time-source access or writes."""
import json
import platform
from pathlib import Path
from zs_smart_gate.pilot020_native import fingerprint,WindowsContinuity,credentials,conflict_check


result=dict(system=platform.system(),release=platform.release(),python=platform.python_version(),
            native_github_auth_available=False,market_requests=0,system_settings_changed=False)
for name,operation in [('host_fingerprint_sha256',fingerprint),('conflict_check',conflict_check),
                       ('windows_unbiased_sleep_guard',lambda:WindowsContinuity().check())]:
    try:
        value=operation();result[name]=value if value is not None else 'PASS'
    except Exception as exc:result[name]='BLOCKED:'+type(exc).__name__+':'+str(exc)[:120]
try:
    credentials();result['native_github_auth_available']=True
except Exception as exc:result['native_github_auth_reason']=str(exc)[:120]
Path('research/stage03-020/owner-host-preflight.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,sort_keys=True))
