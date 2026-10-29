"""On-demand local control; no LLM, no market requests, no lease renewal."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

from .windows_operations import d_path, load_config, verify_deployment

TASK_NAME='ZS-WindowsRunner-Independent-Simulation'
TASK_PATH='\\ZS-Offline-Pilot\\'
MARKER='ZS independent simulation-only runner v2; no LIVE transport'


def run_ps(code):
    """Built-in Windows management client, child processes never allocate consoles."""
    exe=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    result=subprocess.run([str(exe),'-NoProfile','-NonInteractive','-Command',
        '[Console]::OutputEncoding=[Text.UTF8Encoding]::new();'+code],
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=25,
        creationflags=flags)
    if result.returncode:
        raise RuntimeError('WINDOWS_QUERY_FAILED')
    return result.stdout.strip()


def task_snapshot():
    code=r"""$ErrorActionPreference='Stop';
$t=Get-ScheduledTask -TaskPath '\ZS-Offline-Pilot\' -TaskName 'ZS-WindowsRunner-Independent-Simulation' -ErrorAction SilentlyContinue;
$i=if($t){Get-ScheduledTaskInfo -InputObject $t};
$clock=(& w32tm /query /status /verbose 2>&1 | Out-String);
$network=@(Get-NetConnectionProfile -ErrorAction SilentlyContinue | Where-Object {$_.IPv4Connectivity -eq 'Internet' -or $_.IPv6Connectivity -eq 'Internet'}).Count -gt 0;
@{exists=($null -ne $t);description=$t.Description;enabled=if($t){$t.Settings.Enabled}else{$false};state=if($t){$t.State.ToString()}else{'MISSING'};
xml=if($t){Export-ScheduledTask -InputObject $t};last_result=if($i){$i.LastTaskResult};
last_utc=if($i -and $i.LastRunTime.Year -gt 2000){$i.LastRunTime.ToUniversalTime().ToString('o')};
next_utc=if($i -and $i.NextRunTime.Year -gt 2000){$i.NextRunTime.ToUniversalTime().ToString('o')};
clock=$clock;time_service=(Get-Service W32Time).Status.ToString();internet_hint=$network} | ConvertTo-Json -Depth 4 -Compress
"""
    return json.loads(run_ps(code))


def parse_duration(value):
    m=re.fullmatch(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?',value or '')
    if not m or not any(m.groups()): raise ValueError('INVALID_LEASE')
    d,h,mn,s=(int(x or 0) for x in m.groups())
    seconds=d*86400+h*3600+mn*60+s
    if not 0 < seconds <= 7*86400: raise ValueError('INVALID_LEASE')
    return timedelta(seconds=seconds)


def clock_status(raw, service):
    age=re.search(r'Time since Last Good Sync Time:\s+([0-9.]+)s',raw or '')
    source=re.search(r'^Source:\s*(.+)$',raw or '',re.M)
    dispersion=re.search(r'Root Dispersion:\s*([0-9.]+)s',raw or '')
    trusted=(service=='Running' and 'Leap Indicator: 0' in raw and 'Last Sync Error: 0' in raw
             and age is not None and 0<=float(age[1])<=1800 and source is not None
             and not re.search('Local CMOS|Free.running',source[1],re.I))
    return {'operational_simulation_ok':trusted,'source':source[1].strip() if source else 'UNKNOWN',
            'sync_age_seconds':float(age[1]) if age else None,
            'root_dispersion_seconds':float(dispersion[1]) if dispersion else None,
            'exchange_uncertainty':'UNKNOWN'}


def boundary_utc(value, local_resolver=None):
    """Windows offset-less boundaries use OS timezone rules at that date.

    Reject DST gaps/folds rather than guess which instant the scheduler chose.
    Never attach today's fixed UTC offset to a different local date.
    """
    if not isinstance(value,str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?',value):
        raise ValueError('INVALID_BOUNDARY')
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:
        if local_resolver is not None:
            parsed=local_resolver(parsed)
        else:
            if os.name!='nt': raise ValueError('WINDOWS_LOCAL_ZONE_REQUIRED')
            answer=run_ps("$d=[DateTime]::SpecifyKind([DateTime]::ParseExact('"+value+
                "','yyyy-MM-ddTHH:mm:ss.FFFFFF',[Globalization.CultureInfo]::InvariantCulture),[DateTimeKind]::Unspecified);"
                "$z=[TimeZoneInfo]::Local; if($z.IsInvalidTime($d) -or $z.IsAmbiguousTime($d)){throw 'DST_BOUNDARY_UNCERTAIN'};"
                "[TimeZoneInfo]::ConvertTimeToUtc($d,$z).ToString('o')")
            parsed=datetime.fromisoformat(answer.replace('Z','+00:00'))
    if parsed.tzinfo is None: raise ValueError('LOCAL_ZONE_UNRESOLVED')
    return parsed.astimezone(timezone.utc)


def assess_task(snapshot, *, expected_executable, expected_arguments, repo, now, local_resolver=None):
    if not snapshot.get('exists'): return 'BLOCKED','TASK_MISSING',None
    if snapshot.get('description')!=MARKER: return 'BLOCKED','UNKNOWN_TASK',None
    try:
        xml=ET.fromstring(snapshot['xml'])
        ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
        def find(p): return xml.findtext(p,namespaces=ns)
        actions=xml.findall('t:Actions/t:Exec',ns)
        if (len(actions)!=1 or find('t:Actions/t:Exec/t:Command').casefold()!=str(expected_executable).casefold()
                or find('t:Actions/t:Exec/t:Arguments')!=expected_arguments
                or find('t:Actions/t:Exec/t:WorkingDirectory').casefold()!=str(repo).casefold()
                or find('t:Settings/t:MultipleInstancesPolicy')!='IgnoreNew'
                or find('t:Principals/t:Principal/t:LogonType')!='InteractiveToken'):
            return 'BLOCKED','TASK_ACTION_MISMATCH',None
        triggers=xml.findall('t:Triggers/t:TimeTrigger',ns)
        if len(triggers)!=1: raise ValueError('INVALID_LEASE')
        start=boundary_utc(find('t:Triggers/t:TimeTrigger/t:StartBoundary'),local_resolver)
        expiry=start+parse_duration(find('t:Triggers/t:TimeTrigger/t:Repetition/t:Duration'))
        if start.tzinfo is None: raise ValueError('AWARE_TIME_REQUIRED')
        if now>=expiry: return 'EXPIRED','LEASE_EXPIRED',expiry.isoformat()
    except (ValueError,TypeError,AttributeError,RuntimeError,ET.ParseError):
        return 'BLOCKED','INVALID_TASK_XML',None
    if not clock_status(snapshot.get('clock',''),snapshot.get('time_service'))['operational_simulation_ok']:
        return 'BLOCKED','CLOCK_UNTRUSTED',expiry.isoformat()
    return ('RUNNING' if snapshot['enabled'] else 'PAUSED'),'SIMULATION_ONLY',expiry.isoformat()


class Control:
    def __init__(self,config_path,config_sha,repo,state,logs,pythonw,reader=task_snapshot,executor=run_ps):
        self.config_path=Path(config_path);self.config_sha=config_sha;self.repo=Path(repo)
        self.state=Path(state);self.logs=Path(logs);self.pythonw=Path(pythonw)
        self.reader=reader;self.executor=executor

    @property
    def arguments(self):
        return (f'-B "{self.repo / "scripts/windows-tick.py"}" --config "{self.config_path}" '
                f'--config-sha {self.config_sha} --state-dir "{self.state}" --log-dir "{self.logs}" --dry-run --once')

    def status(self):
        data=self.reader()
        try:
            for p in (self.config_path,self.repo,self.state,self.logs,self.pythonw): d_path(p)
            config=load_config(self.config_path,self.config_sha)
            verify_deployment(config,self.repo)
        except (ValueError,OSError):
            return {'state':'BLOCKED','reason':'PIN_OR_D_PATH_INVALID','live':'OFF'}
        status,reason,expiry=assess_task(data,expected_executable=self.pythonw,
            expected_arguments=self.arguments,repo=self.repo,now=datetime.now(timezone.utc))
        health={}
        try:
            hp=self.logs/'health.json'
            if hp.exists() and hp.stat().st_size<=16384: health=json.loads(hp.read_text(encoding='utf-8'))
        except (ValueError,OSError): pass
        from .windows_diagnostic import status as diagnostic_status
        diagnostic = diagnostic_status(self.logs, expected_config_sha=self.config_sha)
        return {'state':status,'reason':reason,'expires':expiry,'last_utc':data.get('last_utc'),
                'next_utc':data.get('next_utc'),'exit_code':data.get('last_result'),
                'clock':clock_status(data.get('clock',''),data.get('time_service')),
                'internet':'WINDOWS_REPORTS_INTERNET' if data.get('internet_hint') else 'OFFLINE_OR_UNKNOWN',
                'health':health,'revision':config['revision'],'live':'OFF',
                'github_evidence':'PENDING_OWNER_APPROVAL','capture':'NONE / SIMULATION_ONLY',
                'codex_required':False,'diagnostic':diagnostic}

    def resume(self):
        before=self.status()
        if before['state'] not in ('RUNNING','PAUSED'): return before
        # Enable only; never Run(), register a second task, renew or backfill.
        self.executor("$t=Get-ScheduledTask -TaskPath '\\ZS-Offline-Pilot\\' -TaskName 'ZS-WindowsRunner-Independent-Simulation';"
                      "if($t.Description -ne '"+MARKER+"'){throw 'UNKNOWN_TASK'}; Enable-ScheduledTask -InputObject $t | Out-Null")
        return self.status()

    def pause(self):
        # Even a broken pin must be stoppable, but never stop an unknown task.
        data=self.reader()
        if data.get('exists') and data.get('description')!=MARKER:
            return {'state':'BLOCKED','reason':'UNKNOWN_TASK','live':'OFF'}
        self.executor("$t=Get-ScheduledTask -TaskPath '\\ZS-Offline-Pilot\\' -TaskName 'ZS-WindowsRunner-Independent-Simulation' -ErrorAction SilentlyContinue;"
                      "if($t){if($t.Description -ne '"+MARKER+"'){throw 'UNKNOWN_TASK'};Disable-ScheduledTask -InputObject $t | Out-Null}")
        return self.status()  # current bounded tick is allowed to finish


    def diagnostic_start(self):
        """Explicit GUI-only one-time diagnostic; NEVER modifies Resume/Pause."""
        from .windows_diagnostic import authorize, status as diagnostic_status
        try:
            return {'diagnostic':authorize(
                config_path=self.config_path,config_sha=self.config_sha,
                repo=self.repo,state=self.state,logs=self.logs,
                pythonw=self.pythonw,executor=self.executor)}
        except (OSError,ValueError,RuntimeError):
            # Do not fall back to simulation or direct HTTP if scheduler fails.
            return {'diagnostic':diagnostic_status(self.logs,self.config_sha),
                    'state':'BLOCKED','reason':'DIAGNOSTIC_ARMING_FAILED'}
