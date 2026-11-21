"""Explicit bounded B1 observation; no unattended mode or external delivery."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import threading

# Resolve this pinned checkout without an installed package or caller PYTHONPATH.
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from zs_smart_gate.ops24_budget import Budget, Hold
from zs_smart_gate.marketwide_capture import _is_admin as is_admin
from zs_smart_gate.ops24_runtime import resources
from zs_smart_gate.ops24_source import Client, atomic, discover, scan
from zs_smart_gate.ops_windows_watchdog import START, run_tree
from zs_smart_gate.stage05_contracts import canonical, digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--observe-source",action="store_true")
    parser.add_argument("--full-market-preflight",action="store_true")
    parser.add_argument("--cycle-child",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--child",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--runtime-root",type=Path)
    parser.add_argument("--boundary",type=int)
    args=parser.parse_args()
    output=args.output.resolve()
    owned=Path("D:/ZS-SMART-GATE").resolve()
    if (os.name!="nt" or sys.version_info[:3]!=(3,12,10)
            or owned not in output.parents or is_admin()):
        parser.error("normal-token Windows 3.12.10 / owned D: path required")
    if not (args.child or args.cycle_child):
        if not (args.observe_source or args.full_market_preflight) or output.exists():
            parser.error("explicit bounded mode and fresh output required")
        if args.full_market_preflight and (args.boundary is None or not 0<=time.time()-args.boundary<90):
            parser.error("full-market entry requires the current declared 30m boundary")
        if args.full_market_preflight and args.boundary%1800:
            parser.error("30m boundary required")
        if subprocess.check_output(["git","status","--porcelain"],text=True).strip():
            parser.error("clean checkout required")
        output.mkdir(parents=True)
        argv=[sys.executable,__file__,"--child","--output",str(output)]
        if args.observe_source:
            argv.append("--observe-source")
        else:
            argv.extend(["--full-market-preflight","--boundary",str(args.boundary)])
        code=run_tree(argv,timeout=120)
        if code in (124,130):
            atomic(output/"watchdog.json",canonical(dict(status="WATCHDOG_OR_OPERATOR_STOP",exit=code)))
        return code
    if sys.stdin.buffer.readline()!=START:
        return 2
    source=Path(__file__).resolve().parents[1]
    code_head=subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True).strip()
    code_tree=subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD^{tree}"],text=True).strip()
    cycle=digest(canonical([code_head,code_tree,args.boundary])) if (args.cycle_child or args.full_market_preflight) else "discovery-"+str(time.time_ns())
    budget=Budget(output,cycle)
    from zs_smart_gate.ops24_normal_clock import NormalClock
    normal_clock=NormalClock()
    started_cpu=time.process_time()
    clock_proof=[None]
    health_lock=threading.Lock()
    def healthy_unlocked():
        try:
            resource=resources(args.runtime_root or output)
            if resource["disk_bytes"]+2*16*1024*1024+65536>1024*1024*1024:
                return False
            if time.process_time()-started_cpu>60:
                return False
            if args.runtime_root:
                root=args.runtime_root
                if (root/"DISABLED").exists() or (root/"STOP_REQUESTED").exists():
                    budget.stop("OPERATOR_STOP")
                    return False
            if args.full_market_preflight or args.cycle_child:
                witness=normal_clock.refresh()
                raw=canonical(witness)
                pin=digest(raw)
                atomic(output/("clock-"+pin+".private.json"),raw)
                clock_proof[0]=dict(witness_sha256=pin,profile=witness["profile"],
                                   assessment=witness["assessment"])
                if witness["assessment"]["status"]!="OPERATIONAL_TIME_ACCEPTED":
                    budget.stop("NORMAL_CLOCK_BLOCKED")
                    return False
                if not 0<=time.time()-args.boundary<90:
                    budget.stop("BOUNDARY_CUTOFF")
                    return False
            return True
        except (Hold,OSError,ValueError,KeyError,subprocess.TimeoutExpired):
            budget.stop("CLOCK_OR_RESOURCE_PROBE_FAILED")
            return False
    def healthy():
        with health_lock:
            return healthy_unlocked()
    client=Client(budget,guard=healthy,clock_receipt=lambda:clock_proof[0])
    if args.observe_source:
        result=dict(head=code_head,tree=code_tree,time_trust="HOST_TIME_CONDITIONAL_UNVERIFIED",status="SOURCE_OBSERVATION_PENDING",full_market="BLOCKED_CLOCK_WITNESS_NOT_DEPLOYED",
                    live_e2e="NOT_PROVEN",qualified_signals=0,telegram_calls=0,sql_writes=0)
        try:
            receipts,snapshot=discover(client)
            atomic(output/"inventory.private.json",canonical(snapshot))
            result.update(status="SOURCE_DISCOVERY_VERIFIED",inventory_id=snapshot["snapshot_sha256"],
                          discovered=len(snapshot["rows"]),eligible=sum(r["eligible"] for r in snapshot["rows"]),
                          actual_evaluations=0,rate_limits=receipts[0]["payload"].get("rateLimits"))
            result["inventory"]=[{k:v for k,v in row.items() if k!="market"} for row in snapshot["rows"]]
        except (Hold,ValueError,KeyError,TypeError) as exc:
            result.update(status="SOURCE_STOP",stop=str(exc) if isinstance(exc,Hold) else "INVALID_SOURCE")
        result["budget"]=budget.state()
        atomic(output/"observation.json",canonical(result))
    else:
        if args.boundary is None or (args.cycle_child and args.runtime_root is None):
            raise Hold("RUNTIME_CLOCK_AND_BOUNDARY_REQUIRED")
        result=scan(client,boundary_ms=args.boundary*1000,release=dict(head=code_head,tree=code_tree))
    print(json.dumps({k:v for k,v in result.items() if k not in ("inventory","rows")},sort_keys=True))
    return 0 if result.get("status")=="SOURCE_DISCOVERY_VERIFIED" else (
        0 if result.get("coverage")=="MARKET_COVERAGE_VERIFIED" else 2)


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (Hold,OSError,ValueError,KeyError) as exc:
        print(json.dumps(dict(status="HOLD",reason=str(exc) if isinstance(exc,Hold) else type(exc).__name__)))
        raise SystemExit(2)
