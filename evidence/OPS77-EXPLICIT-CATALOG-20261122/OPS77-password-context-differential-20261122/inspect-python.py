import sys,json,os,ctypes
from pathlib import Path
sys.path.insert(0,r'D:\ZS-SMART-GATE\validation\OPS24-20261121-source\src')
from zs_smart_gate.ops24_normal_clock import inspect
root=Path(__file__).parent
p=inspect(diagnostic_root=root)
(root/'profile.json').write_text(json.dumps(p))
(root/'context.json').write_text(json.dumps({'admin':bool(ctypes.windll.shell32.IsUserAnAdmin()),'environment':{k:os.environ.get(k) for k in ['USERPROFILE','SystemRoot','windir','LOCALAPPDATA','PSModulePath']},'version':sys.version,'executable':sys.executable}))
