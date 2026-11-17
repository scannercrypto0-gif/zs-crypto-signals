"""Operator-only Spot preflight entry point for a separately approved UTC window."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import time

from zs_smart_gate.ops_spot_preflight import public_get, run_preflight
from zs_smart_gate.stage05_contracts import parse_utc


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-id", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--start-utc", required=True)
    parser.add_argument("--end-utc", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    start, end = map(parse_utc, (args.start_utc, args.end_utc))
    now = lambda: datetime.now(timezone.utc)
    if not start <= now() or now()+timedelta(seconds=120) > end or end-start > timedelta(minutes=15):
        parser.error("approved UTC window must be open with 120 seconds remaining")
    if (os.name != "nt" or args.output.resolve().drive.upper() != "D:"
            or git("rev-parse", "HEAD") != args.head or git("rev-parse", "HEAD^{tree}") != args.tree
            or git("status", "--porcelain")):
        parser.error("Windows D:, clean pinned HEAD and TREE required")
    args.output.mkdir(exist_ok=False)
    with (args.output / "receipts.jsonl").open("x", encoding="utf-8") as stream:
        def record(value):
            stream.write(json.dumps(value, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

        def get(path, params, timeout):
            remaining = (end-now()).total_seconds()
            if remaining <= 0:
                from zs_smart_gate.stage05_contracts import ContractError
                raise ContractError("OPS_UTC_WINDOW_CLOSED")
            return public_get(path, params, min(timeout, remaining))

        record(dict(state="STARTED", approval_id=args.approval_id, head=args.head, tree=args.tree,
                    start_utc=args.start_utc, end_utc=args.end_utc))
        report = run_preflight(get=get, monotonic=time.monotonic,
                               utc_now=lambda: now().isoformat(), record=record)
        record(report)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "SOURCE_READBACK_PASS_CLOCK_PENDING" else 2


if __name__ == "__main__":
    raise SystemExit(main())
