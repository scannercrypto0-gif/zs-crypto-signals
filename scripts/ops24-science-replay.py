"""Offline research replay of pinned owner-local CLOCK73 originals, without HTTP."""
import argparse
from pathlib import Path
# Resolve this pinned checkout without an installed package or caller PYTHONPATH.
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from zs_smart_gate.ops24_science import legacy_research_replay
from zs_smart_gate.ops24_source import atomic
from zs_smart_gate.stage05_contracts import canonical

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--legacy-root",type=Path,required=True)
parser.add_argument("--result-sha256",required=True)
parser.add_argument("--output",type=Path,required=True)
args=parser.parse_args()
owned=Path("D:/ZS-SMART-GATE").resolve()
if any(owned not in path.resolve().parents for path in (args.legacy_root,args.output)):
    parser.error("owned D: paths required")
if args.output.exists():
    parser.error("fresh output required")
report=legacy_research_replay(args.legacy_root,args.result_sha256)
atomic(args.output,canonical(report))
print(canonical(dict(scope=report["scope"],counts=report["counts"],science=report["science"],
                     original_live_outcome_unchanged=report["original_live_outcome_unchanged"])).decode())
