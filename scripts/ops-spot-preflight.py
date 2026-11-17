"""Operator-invoked Windows Time and public Spot diagnostics under standing scope."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from zs_smart_gate.ops_windows_watchdog import run_tree


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
    code = run_tree([sys.executable, "-m", "zs_smart_gate.ops_windows_child",
                     str(args.output)], timeout=120)
    if code in (124, 130):
        report = {"status": "WATCHDOG_STOP" if code == 124 else "OPERATOR_ABORT", "exit": code}
        (args.output/"watchdog.json").write_text(json.dumps(report), encoding="utf-8")
        print(json.dumps(report))
    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print(json.dumps({"status":"OPERATOR_ABORT"}))
        raise SystemExit(130)
