"""Validate the owner-pinned no-market recovery record; no live-release admission."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zs_smart_gate.ops24_recovery import verify_recovery
from zs_smart_gate.ops24_release_clock import validate_map
parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--head',required=True);parser.add_argument('--tree',required=True)
args=parser.parse_args()
verify_recovery(args.root,args.head,args.tree);validate_map(args.root,args.head,args.tree)
print('RECOVERY_NO_MARKET_SCOPE_VERIFIED_NOT_LIVE_OR_SOAK_ACCEPTANCE')
