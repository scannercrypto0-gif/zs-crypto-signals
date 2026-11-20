"""ORDER007 explicitly invoked bounded Windows read-only SHADOW process.

Never schedules itself. Uses existing tested marketwide capture, durable cursor,
source/clock fail-closed policy and 120-second process-tree watchdog.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from zs_smart_gate.ops_windows_watchdog import START, run_tree


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live-read-only", action="store_true")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--admin-clock-pilot", action="store_true",
                   help="Owner-approved one-shot elevated clock pilot, not a service")
    args=p.parse_args()
    if (os.name != "nt" or sys.version_info[:3] != (3,12,10)
            or args.root.resolve().drive.upper() != "D:"
            or args.output.resolve().drive.upper() != "D:"
            or args.root.resolve() != Path("D:/ZS-SMART-GATE").resolve()
            or args.root.resolve() not in args.output.resolve().parents):
        p.error("ORDER007_WINDOWS_31210_D_ONLY_RELEASE_REQUIRED")
    if not args.live_read_only:
        return 2
    if args.child:
        if sys.stdin.buffer.readline() != START:
            return 2
        from zs_smart_gate.marketwide_capture import PublicCapture, run
        class StopAware(PublicCapture):
            def healthy(self):
                return (super().healthy()
                        and not (args.root/"state"/"STOP_REQUESTED").exists())
        transport=StopAware(args.output)
        outcome=run(args.output, args.root/"state"/"marketwide-cursor.sqlite",
                    transport=transport, admin_clock_pilot=args.admin_clock_pilot)
        # Full private result is already durably saved as result.json on D:.
        # Never stream inventory rows or detailed evaluations to operator stdout.
        summary = {"status": outcome.get("status"), "stop": outcome.get("stop"),
                   "requests": outcome.get("requests"),
                   "receipt_manifest_sha256": outcome.get("receipt_manifest_sha256"),
                   "eligible": (outcome.get("funnel") or {}).get("eligible"),
                   "source_validated": (outcome.get("funnel") or {}).get("source_validated"),
                   "coverage": (outcome.get("funnel") or {}).get("coverage"),
                   "result_path": str(args.output / "result.json")}
        print(json.dumps(summary, sort_keys=True))
        # Partial/clock blocked is expected, but NEVER pretend a live pass.
        return 0 if (outcome.get("funnel") or {}).get("coverage") == (
            "MARKET_COVERAGE_VERIFIED") else 2
    if subprocess.check_output(["git","status","--porcelain"],text=True).strip():
        p.error("RELEASE_CHECKOUT_MUST_BE_CLEAN")
    if args.output.exists():
        p.error("FRESH_OUTPUT_PATH_REQUIRED")
    args.output.mkdir(parents=True)
    argv=[sys.executable,__file__,"--live-read-only","--child",
          "--root",str(args.root),"--output",str(args.output)]
    if args.admin_clock_pilot:
        argv.append("--admin-clock-pilot")
    code=run_tree(argv,timeout=120)
    if code in (124,130):
        (args.output/"watchdog.json").write_text(
            json.dumps({"status":"STOPPED_BY_WATCHDOG_OR_OPERATOR",
                        "exit":code, "source":"PUBLIC_READ_ONLY",
                        "external_effects":"OFF"}),encoding="utf-8")
    return code

if __name__=="__main__":
    raise SystemExit(main())
