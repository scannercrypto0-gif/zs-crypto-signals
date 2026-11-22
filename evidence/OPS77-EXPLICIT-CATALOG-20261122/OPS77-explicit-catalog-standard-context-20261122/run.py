import sys,json,hashlib,ctypes
from pathlib import Path
sys.path.insert(0,r'D:\ZS-SMART-GATE\validation\OPS24-20261121-source\src')
from zs_smart_gate.ops24_normal_clock import bind_catalogs,verify_provenance
r=Path(__file__).parent
p=json.loads((r/'input-profile.json').read_bytes())
report={'origin':'DIRECT_CREDENTIAL_STANDARD_USER_DIAGNOSTIC_NOT_SCHEDULED_CLOCK','admin':bool(ctypes.windll.shell32.IsUserAnAdmin()),'market_calls':0,'telegram_calls':0,'sql_writes':0}
try:
 bind_catalogs(p,r/'clock-catalog-map.json')
 report['provenance_verifier_pass']=verify_provenance(p)
 report['members']=[{'file':x['file'],'original_status':x['status'],'native_code':x.get('explicit_catalog',{}).get('winverifytrust_code'),'catalog_signature':x.get('explicit_catalog',{}).get('signature',{}).get('status')} for x in p['signatures']]
except Exception as e:report['failure']=str(e)
(r/'bound-profile.json').write_text(json.dumps(p))
(r/'report.json').write_text(json.dumps(report,indent=2))
