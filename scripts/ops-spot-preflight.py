"""Operator-invoked Windows Time and public Spot diagnostics under standing scope."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-read-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.live_read_only:
        return 2
    if (os.name != "nt" or args.output is None
            or args.output.resolve().drive.upper() != "D:" or sys.version_info[:2] != (3, 12)):
        parser.error("Windows, Python 3.12 and a fresh output directory on D: are required")
    if subprocess.check_output(["git","status","--porcelain"],text=True).strip():
        parser.error("clean checkout required")
    args.output.mkdir()
    elapsed = subprocess.run([sys.executable, "-m", "zs_smart_gate.ops_windows_child",
                              str(args.output)], timeout=120)
    return elapsed.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired:
        print(json.dumps({"status":"WATCHDOG_STOP"}))
        raise SystemExit(2)
    except KeyboardInterrupt:
        print(json.dumps({"status":"OPERATOR_ABORT"}))
        raise SystemExit(130)
