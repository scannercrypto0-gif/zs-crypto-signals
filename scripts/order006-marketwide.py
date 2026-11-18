"""Operator-invoked Order006 bounded Windows foreground capture."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from zs_smart_gate.ops_windows_watchdog import START, run_tree


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-read-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cursor", type=Path, required=True)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if (os.name != "nt" or sys.version_info[:2] != (3, 12)
            or any(p.resolve().drive.upper() != "D:" for p in (args.output, args.cursor))):
        parser.error("Windows Python 3.12 and D: output/cursor required")
    if not args.live_read_only:
        return 2
    if args.child:
        if sys.stdin.buffer.readline() != START:
            return 2
        from zs_smart_gate.marketwide_capture import run
        result = run(args.output, args.cursor)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["funnel"] and result["funnel"]["coverage"] == "MARKET_COVERAGE_VERIFIED" else 2
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        parser.error("clean checkout required")
    args.output.mkdir()
    argv = [sys.executable, __file__, "--live-read-only", "--child",
            "--output", str(args.output), "--cursor", str(args.cursor)]
    code = run_tree(argv, timeout=120)
    if code in (124, 130):
        receipt = dict(status="WATCHDOG_STOP" if code == 124 else "OPERATOR_ABORT",
                       exit_code=code, coverage="MARKET_COVERAGE_PARTIAL")
        (args.output/"watchdog.json").write_text(json.dumps(receipt), encoding="utf-8")
        print(json.dumps(receipt))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
