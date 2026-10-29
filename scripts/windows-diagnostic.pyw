"""One-time read-only Binance diagnostic via a separate no-console scheduled action.

Never imports simulation windows-tick, alters its socket audit hook, or starts
the prospective runner. The task command is generated only by GUI consent.
"""
import argparse
import os
from pathlib import Path
import sys

ROOT=Path("D:/ZS-SMART-GATE")
for key,suffix in {"TEMP":"temp","TMP":"temp","TMPDIR":"temp",
                   "PIP_CACHE_DIR":"cache/pip","PYTHONPYCACHEPREFIX":"cache/pycache",
                   "XDG_CACHE_HOME":"cache","UV_CACHE_DIR":"cache/uv"}.items():
    os.environ[key]=str(ROOT/suffix)
os.environ["PYTHONNOUSERSITE"]="1"
sys.dont_write_bytecode=True

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--config",required=True)
parser.add_argument("--config-sha",required=True)
parser.add_argument("--state-dir",required=True)
parser.add_argument("--log-dir",required=True)
parser.add_argument("--token",required=True)
parser.add_argument("--once",required=True,action="store_true")
args=parser.parse_args()

# All repo imports occur after the OS entrypoint has fixed D-only temp/cache.
# Task Scheduler action uses matching D: venv pythonw.exe with -B, not python.exe.
try:
    repo=Path.cwd().resolve(strict=True)
    sys.path.insert(0,str(repo/"src"))
    from zs_smart_gate.windows_diagnostic import execute
    result=execute(config_path=args.config,config_sha=args.config_sha,repo=repo,
                   state=args.state_dir,logs=args.log_dir,token=args.token)
    raise SystemExit(0 if result["status"]=="PASS" else 2)
except Exception as exc:
    # A second invocation or malformed/expired consent never touches Binance.
    # No exception body, token, account data or traceback in the D: status.
    import json
    from datetime import datetime,timezone
    try:
        logs=(ROOT/"logs").resolve(strict=True)
        if logs.drive.upper()=="D:":
            file=logs/"market-diagnostic-status.json"
            if not (ROOT/"runtime"/"market-diagnostic-consumed.json").exists():
                summary={"status":"BLOCKED","error_category":type(exc).__name__,
                         "http_attempts":0,"finished_at":datetime.now(timezone.utc).isoformat(),
                         "one_time_consumed":False,"study":"OFF"}
                temp=file.with_suffix(".tmp")
                temp.write_text(json.dumps(summary),encoding="utf-8")
                os.replace(temp,file)
    except Exception:
        pass
    raise SystemExit(2)
