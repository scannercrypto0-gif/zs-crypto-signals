"""Order007 operator-invoked original Spot source capture. No signal delivery."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from zs_smart_gate.ops_windows_watchdog import START, run_tree


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live-read-only", action="store_true")
    p.add_argument("--symbols", required=True, help="1-2 distinct Spot USDT symbols")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args()
    if (os.name != "nt" or sys.version_info[:3] != (3,12,10)
            or args.output.resolve().drive.upper() != "D:"):
        p.error("OWNER_WINDOWS_PYTHON_3_12_10_AND_D_ONLY_REQUIRED")
    symbols = tuple(args.symbols.split(","))
    if len(set(symbols)) != len(symbols) or not 1 <= len(symbols) <= 2:
        p.error("ONE_OR_TWO_UNIQUE_SYMBOLS_REQUIRED")
    if not args.live_read_only:
        return 2
    if args.child:
        if sys.stdin.buffer.readline() != START:
            return 2
        from zs_smart_gate.order007_original_source import bounded_source
        result = bounded_source(args.output, symbols)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "RESEARCH_CAPTURED_NO_SCIENCE_AUTHORITY" else 2
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], text=True).strip()
    if status:
        p.error("CLEAN_REPO_REQUIRED")
    if args.output.exists():
        p.error("FRESH_OUTPUT_DIRECTORY_REQUIRED")
    args.output.mkdir(parents=True)
    argv = [sys.executable, __file__, "--live-read-only", "--child",
            "--symbols", args.symbols, "--output", str(args.output)]
    exitcode = run_tree(argv, timeout=120)
    if exitcode in (124, 130):
        (args.output/"watchdog.json").write_text(
            json.dumps({"status": "PROCESS_TREE_STOP", "exit": exitcode,
                        "real_source_acceptance": "NOT_PROVEN"}),
            encoding="utf-8")
    return exitcode


if __name__ == "__main__":
    raise SystemExit(main())
