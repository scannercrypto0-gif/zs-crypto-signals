"""Normal-token OPS24 worker. Reviewed activation is separate from code installation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

# Resolve this pinned checkout without an installed package or caller PYTHONPATH.
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))

from zs_smart_gate.ops24_budget import Hold
from zs_smart_gate.marketwide_capture import _is_admin as is_admin
from zs_smart_gate.ops24_runtime import RuntimeJournal, supervisor
from zs_smart_gate.ops24_source import atomic
from zs_smart_gate.stage05_contracts import canonical, digest


def release(source):
    if subprocess.check_output(["git","-C",str(source),"status","--porcelain"],text=True).strip():
        raise Hold("RELEASE_CHECKOUT_DIRTY")
    return tuple(subprocess.check_output(["git","-C",str(source),"rev-parse",value],text=True).strip()
                 for value in ("HEAD","HEAD^{tree}"))


def activation(root, head, tree):
    config=json.loads((root/"release.json").read_bytes())
    if config.get("head")!=head or config.get("tree")!=tree:
        raise Hold("INSTALLED_RELEASE_PIN_MISMATCH")
    from zs_smart_gate.ops24_authority import verify_cached,verify_remote
    decision=json.loads((root/'standing-authority.json').read_bytes())
    verify_cached(decision,head=head,tree=tree)
    verify_remote(decision)  # Real GitHub records, never self-declared approval.
    from zs_smart_gate.ops24_normal_clock import system_directory
    user=subprocess.check_output([str(system_directory()/"whoami.exe"),"/user","/fo","csv","/nh"],text=True)
    import re
    sid=re.search(r"S-1-[0-9-]+",user)
    if sid is None or config.get("owner_sid")!=sid[0]:
        raise Hold("AUTHENTICATED_OPERATOR_REQUIRED")
    from zs_smart_gate.ops24_authority import deployment_proof
    deployment_proof(root,head,tree,config['owner_sid'])
    start=json.loads((root/'window.json').read_bytes())['start_epoch']
    return dict(start_epoch=start,seconds=86400,scope=decision['scope']),config,None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("Status","Stop","Disable","Validate","Verify","Probe","Health","Evidence","Serve"))
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
    if args.action in ('Probe','Health'):
        from zs_smart_gate.ops24_runtime import resources
        from zs_smart_gate.ops24_normal_clock import system_directory
        command=[str(system_directory()/'WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-NonInteractive','-Command',
            "@{boot_utc=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o');session=[Diagnostics.Process]::GetCurrentProcess().SessionId}|ConvertTo-Json -Compress"]
        observed=json.loads(subprocess.check_output(command,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW))
        report=dict(schema='zs.ops24.actual-normal-task-probe.v2',head=head,tree=tree,
                    pid=os.getpid(),normal_token=not is_admin(),measured_utc=time.time(),
                    windows=observed,resources=resources(root),market_calls=0,telegram_calls=0,sql_writes=0)
        if args.action=='Health':
            from zs_smart_gate.ops24_normal_clock import NormalClock
            report['clock']=NormalClock().refresh()
        atomic(root/'probe.json',canonical(report))
        print(json.dumps(dict(status='ACTUAL_NORMAL_USER_PROBE_RECORDED',head=head,tree=tree)))
        return 0
    if args.action=='Evidence':
        rows=[dict(file=p.relative_to(root).as_posix(),sha256=digest(p.read_bytes()),bytes=p.stat().st_size)
              for p in root.rglob('*.json') if p.name not in ('release.json','standing-authority.json')]
        print(json.dumps(dict(head=head,tree=tree,files=rows,scope='LOCAL_HASH_INDEX_NO_SECRET_CONTENT')))
        return 0
    permit,config,_=activation(root,head,tree)
    start=permit["start_epoch"]
    if type(start) is not int or start%1800 or not start-1800<=time.time()<start+86400:
        raise Hold("ACTIVATION_WINDOW_INVALID")
    if args.action in ("Validate","Verify"):
        print(json.dumps(dict(status="REVIEWED_ACTIVATION_VERIFIED",head=head,tree=tree)))
        return 0
    activation_bytes=(root/"standing-authority.json").read_bytes()
    release_bytes=(root/"release.json").read_bytes()
    journal=RuntimeJournal(root)
    window=journal.plan(start,head)
    from zs_smart_gate.ops24_normal_clock import NormalClock
    normal_clock=NormalClock()
    def clock():
        return normal_clock.accepted()
    def admitted():
        try:
            return ((root/"standing-authority.json").read_bytes()==activation_bytes
                    and (root/"release.json").read_bytes()==release_bytes
                    and not (root/"STOP_REQUESTED").exists())
        except (OSError,ValueError,KeyError,ImportError,Hold):
            return False
    def cycle(boundary):
        # Startup validated live GitHub authority; immutable local revocation/STOP
        # is rechecked continuously. Revalidate remote authority at the next restart.
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
