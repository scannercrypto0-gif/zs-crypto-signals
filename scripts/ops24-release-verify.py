"""Verify an existing standing release against actual GitHub authority/review/merge state."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zs_smart_gate.ops24_authority import verify_remote
from zs_smart_gate.ops24_budget import Hold
p=argparse.ArgumentParser(description=__doc__);p.add_argument('decision',type=Path);a=p.parse_args()
try:
 if Path('D:/ZS-SMART-GATE').resolve() not in a.decision.resolve().parents:raise Hold('D_OWNED_PATH_REQUIRED')
 result=verify_remote(json.loads(a.decision.read_bytes()))
 print(json.dumps(dict(status='STANDING_REVIEWED_RELEASE_VERIFIED',head=result['head'],tree=result['tree'])))
except (Hold,OSError,ValueError,KeyError) as e:
 print(json.dumps(dict(status='HOLD',reason=str(e) if isinstance(e,Hold) else type(e).__name__)));raise SystemExit(2)
