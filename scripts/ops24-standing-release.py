"""Compose standing read-only release authority from GitHub PM review and real Windows proofs."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zs_smart_gate.ops24_authority import compose
from zs_smart_gate.ops24_budget import Hold
from zs_smart_gate.ops24_source import atomic
from zs_smart_gate.stage05_contracts import canonical
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--head',required=True);p.add_argument('--tree',required=True)
p.add_argument('--windows',type=Path,required=True);p.add_argument('--source-proof',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
try:
 owned=Path('D:/ZS-SMART-GATE').resolve()
 if any(owned not in v.resolve().parents for v in (a.windows,a.source_proof,a.output)) or a.output.exists():
  raise Hold('FRESH_OWNED_D_PATH_REQUIRED')
 result=compose(head=a.head,tree=a.tree,windows=a.windows,source=a.source_proof)
 atomic(a.output,canonical(result));print(json.dumps(dict(decision=result['decision'],head=result['head'],tree=result['tree'])))
except (Hold,OSError,ValueError,KeyError) as e:
 print(json.dumps(dict(status='HOLD',reason=str(e) if isinstance(e,Hold) else type(e).__name__)));raise SystemExit(2)
