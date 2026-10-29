"""One-off owner Windows GUI→TaskScheduler→approved Stage03B1 diagnostic.

No simulation changes, future-study activation, Telegram or trading. D-only
transient diagnostic files are NOT the approved immutable GitHub journal.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
import hashlib,json,os,re,secrets
from pathlib import Path

from .stage03a_contracts import Horizon
from .stage03b1_live import probe_once
from .windows_operations import d_path,load_config,verify_deployment

TASK_NAME="ZS-WindowsRunner-OneShot-Diagnostic"
TASK_PATH="\\ZS-Offline-Pilot\\"
MARKER="ZS one-time read-only BTCUSDT 03B1 diagnostic; independent of simulation/PIT"
INTENT="market-diagnostic-intent.json"
CLAIM="market-diagnostic-consumed.json"
STATUS="market-diagnostic-status.json"
EVIDENCE="market-diagnostic-evidence.json"
MAX_AGE=timedelta(minutes=5)
BUDGET=8

def now_utc(): return datetime.now(timezone.utc)

def write_json(path,value,exclusive=False):
    raw=json.dumps(value,sort_keys=True,allow_nan=False,ensure_ascii=True)
    if len(raw.encode())>(4096 if exclusive else 65536):
        raise ValueError("DIAGNOSTIC_RECORD_TOO_LARGE")
    if exclusive:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as f:f.write(raw+"\n")
    else:
        tmp=path.with_name(path.name+".tmp")
        with tmp.open("w",encoding="utf-8") as f:f.write(raw+"\n")
        os.replace(tmp,path)

def status(logs,expected_config_sha=None):
    path=Path(logs)/STATUS
    try:
        if not path.exists():return {"status":"NOT_AUTHORIZED","http_attempts":0}
        if path.stat().st_size>65536:return {"status":"STATUS_UNREADABLE","http_attempts":None}
        value=json.loads(path.read_text(encoding="utf-8"))
        if expected_config_sha and value.get("deployment_config_sha")!=expected_config_sha:
            return {"status":"PIN_MISMATCH","http_attempts":0}
        return value
    except (ValueError,OSError):
        return {"status":"STATUS_UNREADABLE","http_attempts":None}

def pinned(config_path,config_sha,repo,state,logs,pythonw=None):
    for p in (config_path,repo,state,logs):d_path(p)
    if pythonw is not None:
        if d_path(pythonw).name.lower()!="pythonw.exe":
            raise ValueError("NO_CONSOLE_PYTHONW_REQUIRED")
    config=load_config(Path(config_path),config_sha)
    if verify_deployment(config,Path(repo))!=config_sha:
        raise ValueError("FROZEN_CONFIG_CHANGED")
    return config

def authorize(*,config_path,config_sha,repo,state,logs,pythonw,executor,
              clock=now_utc,token_factory=lambda:secrets.token_hex(16)):
    """One explicit GUI authorization, even registration failure consumes it."""
    config=pinned(config_path,config_sha,repo,state,logs,pythonw)
    runtime,logdir=Path(state),Path(logs)
    if (runtime/INTENT).exists() or (runtime/CLAIM).exists():
        return {"status":"ALREADY_AUTHORIZED_OR_CONSUMED","http_attempts":0}
    entry=d_path(Path(repo)/"scripts/windows-diagnostic.pyw")
    now=clock()
    if now.tzinfo is None:raise ValueError("AWARE_CLOCK_REQUIRED")
    token=token_factory()
    if not re.fullmatch("[0-9a-f]{32}",token):
        raise ValueError("INVALID_INTENT_TOKEN")
    if not re.fullmatch("[0-9a-f]{64}",config_sha):
        raise ValueError("INVALID_CONFIG_SHA")
    paths=tuple(map(str,(pythonw,entry,repo,config_path,state,logs)))
    if any(any(c in p for c in ("'","\"",chr(96),"\r","\n")) for p in paths):
        raise ValueError("UNSAFE_TASK_PATH")
    intent={"authorized_at":now.isoformat(),
            "expires_at":(now+MAX_AGE).isoformat(),
            "deployment_config_sha":config_sha,"revision":config["revision"],
            "symbol":"BTCUSDT","horizon":"INTRADAY",
            "mode":"GUI_ONE_SHOT_DIAGNOSTIC_ONLY",
            "token_sha256":hashlib.sha256(token.encode()).hexdigest()}
    write_json(runtime/INTENT,intent,exclusive=True)
    visible={"status":"ARMED","authorized_at":now.isoformat(),
             "expires_at":intent["expires_at"],"revision":config["revision"],
             "deployment_config_sha":config_sha,"http_attempts":0,
             "symbol":"BTCUSDT","parent_frame":"30m",
             "host":"https://data-api.binance.vision","study":"OFF"}
    write_json(logdir/STATUS,visible)
    args=(f'-B "{entry}" --config "{config_path}" --config-sha {config_sha} '
          f'--state-dir "{state}" --log-dir "{logs}" --token {token} --once')
    ps=(
        "$ErrorActionPreference='Stop';"
        f"$existing=Get-ScheduledTask -TaskPath '{TASK_PATH}' -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue;"
        "if($existing){throw 'DIAGNOSTIC_TASK_ALREADY_EXISTS'};"
        f"$action=New-ScheduledTaskAction -Execute '{pythonw}' -Argument '{args}' -WorkingDirectory '{repo}';"
        "$trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(12);"
        "$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew "
        "-ExecutionTimeLimit (New-TimeSpan -Minutes 3) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries;"
        "$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) "
        "-LogonType Interactive -RunLevel Limited;"
        f"Register-ScheduledTask -TaskPath '{TASK_PATH}' -TaskName '{TASK_NAME}' "
        f"-Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description '{MARKER}' | Out-Null")
    try:executor(ps)
    except Exception:
        write_json(logdir/STATUS,{**visible,"status":"REGISTRATION_FAILED",
                   "error_category":"WINDOWS_TASK_REGISTRATION_FAILED",
                   "finished_at":clock().isoformat()})
    return status(logdir,config_sha)

def execute(*,config_path,config_sha,repo,state,logs,token,
            probe=probe_once,clock=now_utc):
    """Scheduled action; atomic single-use claim BEFORE any outbound GET."""
    config=pinned(config_path,config_sha,repo,state,logs)
    runtime,logdir=Path(state),Path(logs)
    if not re.fullmatch("[0-9a-f]{32}",token or ""):
        raise ValueError("EXPLICIT_GUI_INTENT_REQUIRED")
    intent_file=runtime/INTENT
    if not intent_file.exists() or intent_file.stat().st_size>4096:
        raise ValueError("EXPLICIT_GUI_INTENT_REQUIRED")
    intent=json.loads(intent_file.read_text(encoding="utf-8"))
    now=clock()
    issued=datetime.fromisoformat(intent["authorized_at"])
    expires=datetime.fromisoformat(intent["expires_at"])
    if (now.tzinfo is None or issued.tzinfo is None or expires.tzinfo is None
        or intent.get("deployment_config_sha")!=config_sha
        or intent.get("revision")!=config["revision"]
        or intent.get("mode")!="GUI_ONE_SHOT_DIAGNOSTIC_ONLY"
        or intent.get("symbol")!="BTCUSDT" or intent.get("horizon")!="INTRADAY"
        or intent.get("token_sha256")!=hashlib.sha256(token.encode()).hexdigest()
        or issued>now or expires-issued!=MAX_AGE or now>expires):
        raise ValueError("EXPIRED_OR_MISMATCHED_GUI_INTENT")
    write_json(runtime/CLAIM,{
        "consumed_at":now.isoformat(),"revision":config["revision"],
        "deployment_config_sha":config_sha,"physical_attempt_budget":BUDGET},
        exclusive=True)
    common={"revision":config["revision"],"deployment_config_sha":config_sha,
            "started_at":now.isoformat(),"symbol":"BTCUSDT","parent_frame":"30m",
            "host":"https://data-api.binance.vision",
            "scope":"ONE_SHOT_PUBLIC_DIAGNOSTIC_NOT_PIT",
            "http_attempts":0,"study":"OFF","simulation":"UNCHANGED",
            "one_time_consumed":True}
    write_json(logdir/STATUS,{**common,"status":"RUNNING"})
    try:
        result=probe(horizon=Horizon.INTRADAY,symbol="BTCUSDT")
        metrics=result.get("measurements",{})
        n=metrics.get("physical_http_attempts")
        if type(n)!=int or n<0 or n>BUDGET:
            raise ValueError("PHYSICAL_ATTEMPT_LIMIT_NOT_PROVEN")
        if result.get("signal_id") is not None or result.get("score") is not None:
            raise ValueError("DIAGNOSTIC_NOT_SIGNAL_OR_SCORE")
        if result.get("status") not in ("PASS","INVALID","FAIL","BLOCKED"):
            raise ValueError("INVALID_PROBE_STATUS")
        evidence={**common,"status":result["status"],"http_attempts":n,
                  "finished_at":clock().isoformat(),"stage03b1":result}
        write_json(logdir/EVIDENCE,evidence)
        summary={k:v for k,v in evidence.items() if k!="stage03b1"}
        summary.update(source_status=result["status"],
                       parent_close_at=result.get("parent_close_exclusive_at"),
                       reconciliation_status=result.get("reconciliation",{}).get("status"),
                       http=metrics.get("http",[]),elapsed_ms=metrics.get("elapsed_ms"),
                       clock_offset_estimate_ms=metrics.get("estimated_server_clock_offset_ms"),
                       true_clock_uncertainty_ms=None,
                       reason=result.get("reason") or result.get("reasons"))
        write_json(logdir/STATUS,summary)
        return summary
    except Exception as error:
        failed={**common,"status":"FAIL","finished_at":clock().isoformat(),
                "error_category":type(error).__name__}
        write_json(logdir/STATUS,failed)
        return failed
