"""Normal-token OPS24 worker. Signed activation is separate from code installation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from zs_smart_gate.ops24_budget import Budget, Hold
from zs_smart_gate.ops24_clock import check_clock, is_admin, verify_envelope
from zs_smart_gate.ops24_runtime import RuntimeJournal, supervisor
from zs_smart_gate.ops24_source import Client, atomic, scan
from zs_smart_gate.stage05_contracts import canonical, digest


def release(source):
    if subprocess.check_output(["git","-C",str(source),"status","--porcelain"],text=True).strip():
        raise Hold("RELEASE_CHECKOUT_DIRTY")
    return tuple(subprocess.check_output(["git","-C",str(source),"rev-parse",value],text=True).strip()
                 for value in ("HEAD","HEAD^{tree}"))


def activation(root, head, tree):
    config=json.loads((root/"release.json").read_bytes())
    pem=(root/"authority.public.pem").read_bytes()
    pin=config["authority_sha256"]
    if pin is None:
        raise Hold("PROTECTED_CLOCK_DEPLOYMENT_PENDING")
    if config.get("head")!=head or config.get("tree")!=tree:
        raise Hold("INSTALLED_RELEASE_PIN_MISMATCH")
    permit=verify_envelope(json.loads((root/"activation.json").read_bytes()),pem,pin)
    if (permit.get("schema")!="zs.ops24.activation.v1" or permit.get("head")!=head
            or permit.get("tree")!=tree or permit.get("purpose")!="READ_ONLY_RESEARCH_24H"
            or permit.get("seconds")!=86400 or permit.get("pm_review_url","").startswith(
                "https://github.com/scannercrypto0-gif/zs-crypto-signals/") is False):
        raise Hold("ACTIVATION_SCOPE_INVALID")
    for gate in ("engineering","full_market","normal_worker","stop_rollback","owner_merge"):
        row=permit["proofs"][gate]
        raw=(root/"proofs"/(gate+".json")).read_bytes()
        if digest(raw)!=row["sha256"]:
            raise Hold("ACTIVATION_PROOF_HASH_INVALID")
        proof=json.loads(raw)
        if gate=="full_market" and not (proof.get("coverage")=="MARKET_COVERAGE_VERIFIED"
                and proof.get("eligible",0)>0 and proof.get("eligible")==proof.get("validated")
                and proof.get("missing")==0):
            raise Hold("FULL_MARKET_PREFLIGHT_NOT_PASSED")
        if gate!="full_market" and proof.get("accepted") is not True:
            raise Hold("REVIEWED_GATE_NOT_PASSED")
    return permit,config,pem


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("Status","Stop","Disable","Validate","Serve"))
    parser.add_argument("--root",type=Path,required=True)
    args=parser.parse_args()
    root=args.root.resolve()
    owned=Path("D:/ZS-SMART-GATE").resolve()
    if os.name!="nt" or sys.version_info[:3]!=(3,12,10) or owned not in root.parents:
        parser.error("Windows 3.12.10 / owned D: root required")
    if is_admin():
        raise Hold("NORMAL_USER_TOKEN_REQUIRED")
    if args.action in ("Stop","Disable"):
        root.mkdir(parents=True,exist_ok=True)
        atomic(root/("STOP_REQUESTED" if args.action=="Stop" else "DISABLED"),b"operator-request\n")
        return 0
    if args.action=="Status":
        path=root/"status.json"
        print(path.read_text() if path.exists() else json.dumps(
            dict(status="DISABLED_OR_NOT_STARTED",stability="24H_STABILITY_NOT_PROVEN")))
        return 0
    source=Path(__file__).resolve().parents[1]
    head,tree=release(source)
    permit,config,pem=activation(root,head,tree)
    start=permit["start_epoch"]
    if type(start) is not int or start%1800 or not start-1800<=time.time()<start+86400:
        raise Hold("ACTIVATION_WINDOW_INVALID")
    if args.action=="Validate":
        print(json.dumps(dict(status="SIGNED_ACTIVATION_VERIFIED",head=head,tree=tree)))
        return 0
    activation_bytes=(root/"activation.json").read_bytes()
    release_bytes=(root/"release.json").read_bytes()
    journal=RuntimeJournal(root)
    window=journal.plan(start,head)
    def clock():
        try:
            check_clock(json.loads((root/"clock.json").read_bytes()),pem,config["authority_sha256"],
                        head=head,tree=tree)
            return True
        except (OSError,ValueError,KeyError,ImportError,Hold):
            return False
    def admitted():
        try:
            return ((root/"activation.json").read_bytes()==activation_bytes
                    and (root/"release.json").read_bytes()==release_bytes
                    and not (root/"STOP_REQUESTED").exists())
        except (OSError,ValueError,KeyError,ImportError,Hold):
            return False
    def cycle(boundary):
        activation(root,head,tree)
        from zs_smart_gate.ops_windows_watchdog import run_tree
        output=root/"cycles"/str(boundary)
        output.mkdir(parents=True,exist_ok=True)
        # The child performs one finite, guarded capture under a process-tree watchdog.
        argv=[sys.executable,str(source/"scripts"/"ops24-bounded.py"),"--cycle-child",
              "--output",str(output),"--runtime-root",str(root),"--boundary",str(boundary)]
        code=run_tree(argv,timeout=120)
        if code in (124,130):
            return dict(coverage="BLOCKED",stop="CYCLE_WATCHDOG_OR_OPERATOR",exit_code=code)
        path=output/"result.json"
        return json.loads(path.read_bytes()) if path.exists() else dict(coverage="BLOCKED",stop="MISSING_CYCLE_RESULT")
    report=supervisor(root,window,activation=admitted,run_cycle=cycle,clock=clock)
    atomic(root/"final.json",canonical(report))
    return 0 if report["stability"]=="24H_COMPLETE" else 2


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (Hold,OSError,ValueError,KeyError,ImportError) as exc:
        print(json.dumps(dict(status="HOLD",reason=str(exc) if isinstance(exc,Hold) else type(exc).__name__)))
        raise SystemExit(2)
