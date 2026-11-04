"""Owner-Windows entry prerequisites; no source I/O on import or inspection."""
import ctypes
from datetime import datetime,timezone
import hashlib
import json
import ntpath
import os
from pathlib import Path
import platform
import re
import subprocess
import threading
import time
import urllib.request
from .pilot020 import canonical,sha,permit
from .github_evidence_backend import GitHubContentsTransport

REPO='scannercrypto0-gif/zs-crypto-signals'


def on_d(path):
    return ntpath.splitdrive(str(path))[0].upper()=='D:'


def fingerprint():
    # Publish only a study-purpose machine hash, never hostname/MAC/MachineGuid.
    if os.name!='nt':raise ValueError('WINDOWS_OWNER_FINGERPRINT_REQUIRED')
    boot=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
        "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')"],
        capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW,check=True).stdout.strip()
    if not boot:raise ValueError('WINDOWS_BOOT_ID_UNAVAILABLE')
    return hashlib.sha256(('020-owner-windows:'+platform.node()+':'+platform.system()+':'+boot).encode()).hexdigest()


def credentials():
    # Never read Git credential managers, browsers, cached tokens or files.
    # The owner must explicitly provision an ephemeral, scoped secret to this
    # one-shot process through an independently approved mechanism.
    token=os.environ.get('ZS020_GITHUB_TOKEN')
    if not token:raise ValueError('NATIVE_GITHUB_AUTH_UNAVAILABLE_NO_EXPLICIT_TOKEN')
    return token


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k):raise ValueError('GITHUB_REDIRECT_FORBIDDEN')


def github_json(suffix,token):
    if (suffix and not suffix.startswith('/')) or '..' in suffix:raise ValueError('GITHUB_PATH_SCOPE')
    url='https://api.github.com/repos/'+REPO+suffix
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
        'X-GitHub-Api-Version':'2022-11-28','User-Agent':'zs-pilot020'})
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=5) as response:
        raw=response.read(3145729)
        if len(raw)>3145728:raise ValueError('GITHUB_RESPONSE_CAP')
        return json.loads(raw)


class Store:
    def __init__(self,transport,manifest):
        self.transport=transport;self.m=manifest;self.calls=0
    def create(self,name,body):
        if name.startswith('/') or '..' in name:raise ValueError('STUDY_PATH_SCOPE')
        self.calls+=3
        if self.calls>300:raise ValueError('GITHUB_STUDY_REQUEST_BUDGET')
        path='studies/'+self.m['study_id']+'/'+name;branch=self.m['evidence_branch']
        if self.transport.get_file(path,branch) is not None:raise ValueError('CONSUMED_OR_DUPLICATE_NO_RETRY')
        if not self.transport.put_file(path,body,branch,None,'pilot020 '+name):raise ValueError('CREATE_CONFLICT_STOP')
        read=self.transport.get_file(path,branch)
        if read is None or read[0]!=body:raise ValueError('WRITE_READBACK_UNKNOWN_NO_RETRY')
    def read(self,name):
        self.calls+=1
        if self.calls>300:raise ValueError('GITHUB_STUDY_REQUEST_BUDGET')
        return self.transport.get_file('studies/'+self.m['study_id']+'/'+name,self.m['evidence_branch'])


class WindowsContinuity:
    def __init__(self):
        if os.name!='nt':raise ValueError('WINDOWS_REQUIRED')
        ctypes.windll.kernel32.GetTickCount64.restype=ctypes.c_ulonglong
        self.baseline=self.sample();self.last=time.monotonic()
    def sample(self):
        value=ctypes.c_ulonglong()
        if not ctypes.windll.kernel32.QueryUnbiasedInterruptTime(ctypes.byref(value)):
            raise ValueError('UNBIASED_INTERRUPT_TIME_UNAVAILABLE')
        return ctypes.windll.kernel32.GetTickCount64()/1000-value.value/1e7
    def check(self):
        now=time.monotonic()
        if now-self.last>60 or abs(self.sample()-self.baseline)>.25:
            raise ValueError('SLEEP_OR_WATCHDOG_GAP_STOP_REANCHOR')
        self.last=now


def load_review(value):
    if value.get('user',{}).get('login')!='scannercrypto0-gif':raise ValueError('REVIEW_ACTOR_NOT_GOVERNANCE_ACCOUNT')
    body=value.get('body','')
    if '020_FIELD_PREFLIGHT_PASS' not in body:raise ValueError('NO_INDEPENDENT_PREFLIGHT_PASS')
    match=re.search(r'```json\s*(\{.*?\})\s*```',body,re.S)
    if not match:raise ValueError('REVIEW_MACHINE_READABLE_PINS_REQUIRED')
    review=json.loads(match.group(1));review['comment_id']=value['id']
    if review.get('independence_statement')!='PM_REVIEW_NOT_EXECUTOR':raise ValueError('INDEPENDENT_ROLE_STATEMENT_REQUIRED')
    return review


def conflict_check():
    # Filter locally; never export command lines (they can contain secrets).
    command=("$p=Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne "+str(os.getpid())+
        " -and $_.ProcessId -ne "+str(os.getppid())+
        " -and $_.Name -match '^pythonw?\\.exe$' -and $_.CommandLine -match '(ZS-SMART-GATE|SuperKumo)' }; "
        "$t=Get-ScheduledTask | Where-Object { $_.State -eq 'Running' -and $_.TaskName -match '(ZS|SuperKumo)' }; "
        "if($p -or $t){'CONFLICT'}else{'CLEAR'}")
    p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
        capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW,check=True)
    if p.stdout.strip()!='CLEAR':raise ValueError('OTHER_PROJECT_COLLECTOR_OR_TASK_CONFLICT_OR_UNKNOWN')


def execute(manifest_path,review_id,workspace):
    """No source connection until EVERY prerequisite and remote claim passes."""
    from .pilot020_io import WebSocketOnce,public_gets
    from .pilot020_runner import Journal,run_capture
    workspace=Path(workspace).resolve();manifest_path=Path(manifest_path).resolve()
    if (os.name!='nt' or os.environ.get('GITHUB_ACTIONS')=='true' or os.environ.get('CI')=='true' or
        not all(on_d(p) for p in (workspace,manifest_path,sys_prefix(),os.environ.get('TEMP',''),os.environ.get('TMP','')))):
        raise ValueError('OWNER_WINDOWS_D_WORKSPACE_VENV_TEMP_ONLY')
    m=json.loads(manifest_path.read_bytes());token=credentials()
    repo=github_json('',token)
    if repo.get('private') is not True or not repo.get('permissions',{}).get('push'):
        raise ValueError('PRIVATE_REPOSITORY_NATIVE_WRITE_PERMISSION_REQUIRED')
    review=load_review(github_json('/issues/comments/'+str(int(review_id)),token))
    current=subprocess.check_output(['git','rev-parse','HEAD'],text=True,creationflags=subprocess.CREATE_NO_WINDOW).strip()
    # A locally edited/untracked source cannot run under another code's review.
    if subprocess.check_output(['git','status','--porcelain'],text=True,creationflags=subprocess.CREATE_NO_WINDOW).strip():raise ValueError('CLEAN_PINNED_CODE_CHECKOUT_REQUIRED')
    permit(m,review,now=time.time(),code_sha=current,host_fingerprint=fingerprint(),windows=True)
    conflict_check()
    created=datetime.fromisoformat(github_json('/issues/comments/'+str(int(review_id)),token)['created_at'].replace('Z','+00:00')).timestamp()
    if created<m['frozen_at']:raise ValueError('REVIEW_PREDATES_FROZEN_MANIFEST')
    transport=GitHubContentsTransport(REPO,token,timeout=5);store=Store(transport,m)
    remote=store.read('manifest.json')
    if remote is None or json.loads(remote[0])!=m:raise ValueError('MANIFEST_NOT_FROZEN_AND_READ_BACK')
    # Reject any surprise files/capacity already consumed in this study.
    listing=github_json('/git/trees/'+m['evidence_branch']+'?recursive=1',token)
    prefix='studies/'+m['study_id']+'/'
    initial=sum(x.get('size',0) for x in listing['tree'] if x['path'].startswith(prefix) and x['type']=='blob')
    preparation=sum(x.get('size',0) for x in listing['tree'] if x['path'].startswith('research/stage03-020/') and x['type']=='blob')
    if preparation+3145728>10485760:raise ValueError('020_PREPARATION_PLUS_FIELD_AGGREGATE_CAP')
    if initial+2097152>3145728:raise ValueError('INSUFFICIENT_SERIALIZED_STUDY_RESERVATION')
    workspace.mkdir(parents=True,exist_ok=True)
    lock=workspace/'single-attempt.lock'
    with lock.open('x',encoding='utf-8') as f:f.write(sha(m))
    store.create('claims/session-once.json',canonical(dict(manifest_sha256=sha(m),code_sha=current,
        review_comment_id=int(review_id),host_fingerprint_sha256=fingerprint(),repeat_allowed=False)))
    health=WindowsContinuity();stream=WebSocketOnce(__import__('zs_smart_gate.pilot020',fromlist=['Budget']).Budget())
    journal=Journal(workspace,store,m['study_id'],initial_bytes=initial+2048)
    finished=threading.Event()
    def hard_stop():
        if not finished.wait(max(0,min(720,m['end_at']-time.time()))):
            # DNS/library stalls must not turn this into a background service.
            (workspace/'watchdog-terminal.json').write_bytes(canonical(dict(status='GAP_HOLD_HARD_DEADLINE',repeat_allowed=False)))
            os._exit(70)
    guard=threading.Thread(target=hard_stop,daemon=True);guard.start()
    try:
        result=run_capture(m,journal=journal,stream=stream,rest=public_gets,
            health=health.check,cancel=lambda:(workspace/'CANCEL').exists(),execution_origin='OWNER_WINDOWS_VERIFIED')
        store.create('terminal-report.json',canonical(result))
        # Read every committed chunk again, then verify the hash chain before
        # returning any stored observation. Capture never resumes on a gap.
        from .pilot020_runner import verify_chunks
        chunks=[]
        for i in range(journal.chunk):
            raw=store.read(f'receipts/chunk-{i:04}.json')
            if raw is None:raise ValueError('CHUNK_RESTORE_MISSING')
            chunks.append(json.loads(raw[0]))
        result['restoration']=verify_chunks(chunks)
        store.create('restoration-report.json',canonical(result['restoration']))
        return result
    finally:finished.set();stream.close()


def sys_prefix():
    import sys
    return sys.prefix
