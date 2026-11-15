"""Replay the pinned public Spot capture through independent 30m research."""
import argparse
import json
from pathlib import Path

from zs_smart_gate.stage03_30m_universe import replay_spot_capture

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("capture", type=Path)
parser.add_argument("pin")
args = parser.parse_args()
print(json.dumps(replay_spot_capture(args.capture.read_bytes(), args.pin), sort_keys=True))
