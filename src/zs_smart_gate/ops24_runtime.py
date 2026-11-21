"""Disabled-first normal-token supervisor and immutable planned-slot journal."""
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import time

from .ops24_budget import Hold
from .ops24_source import atomic
from .stage05_contracts import canonical, digest
from .windows_runner import process_lock


class RuntimeJournal:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.path = self.root/"runtime.sqlite"
        with closing(self.open()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS windows(id TEXT PRIMARY KEY,start INTEGER,end INTEGER,release TEXT);
                CREATE TABLE IF NOT EXISTS slots(window TEXT,kind TEXT,at INTEGER,state TEXT,payload BLOB,sha TEXT,
                    PRIMARY KEY(window,kind,at));
                CREATE TABLE IF NOT EXISTS control(id INTEGER PRIMARY KEY, failures INTEGER, retry_at REAL, halt TEXT);
                INSERT OR IGNORE INTO control VALUES(1,0,0,NULL);
            """)

    def open(self):
        db = sqlite3.connect(self.path,timeout=5,isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def plan(self, start, release):
        if type(start) is not int or start%1800:
            raise Hold("ALIGNED_FROZEN_WINDOW_REQUIRED")
        window = digest(canonical([start,release]))
        with closing(self.open()) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO windows VALUES(?,?,?,?)",(window,start,start+86400,release))
            for kind,step in (("health",300),("boundary",1800)):
                for at in range(start,start+86400,step):
                    db.execute("INSERT OR IGNORE INTO slots VALUES(?,?,?,'PLANNED',NULL,NULL)",(window,kind,at))
            db.commit()
        return window

    def reserve(self, window,kind,at):
        with closing(self.open()) as db:
            return db.execute("""UPDATE slots SET state='CLAIMED'
                WHERE window=? AND kind=? AND at=? AND state='PLANNED'""",(window,kind,at)).rowcount==1

    def finish(self, window,kind,at,state,payload):
        raw = canonical(payload)
        with closing(self.open()) as db:
            changed = db.execute("""UPDATE slots SET state=?,payload=?,sha=?
                WHERE window=? AND kind=? AND at=? AND state='CLAIMED'""",
                (state,raw,digest(raw),window,kind,at)).rowcount
            if changed!=1:
                raise Hold("SLOT_REPLAY_OR_CONFLICT")

    def missed(self, window, now):
        # Never change a started/unknown operation into an unattempted slot.
        with closing(self.open()) as db:
            db.execute("""UPDATE slots SET state='MISSED'
                WHERE window=? AND state='PLANNED' AND
                ((kind='health' AND at+300<=?) OR (kind='boundary' AND at+90<?))""",
                (window,now,now))

    def breaker(self, *, now, success, hard_reason=None):
        with closing(self.open()) as db:
            failures,_,halt = db.execute("SELECT failures,retry_at,halt FROM control").fetchone()
            failures = 0 if success else failures+1
            halt = halt or hard_reason or ("CIRCUIT_BREAKER" if failures>=3 else None)
            retry = now+(0 if success else min(300,5*(3**min(failures-1,4))))
            db.execute("UPDATE control SET failures=?,retry_at=?,halt=? WHERE id=1",(failures,retry,halt))
            return dict(failures=failures,retry_at=retry,halt=halt)

    def report(self, window, now):
        with closing(self.open()) as db:
            start,end,release = db.execute("SELECT start,end,release FROM windows WHERE id=?",(window,)).fetchone()
            rows = list(db.execute("SELECT kind,at,state,payload,sha FROM slots WHERE window=? ORDER BY at,kind",(window,)))
            control = db.execute("SELECT failures,retry_at,halt FROM control").fetchone()
        slots=[]
        for kind,at,state,raw,pin in rows:
            if raw is not None and digest(raw)!=pin:
                raise Hold("RUNTIME_JOURNAL_CORRUPTION")
            slots.append(dict(kind=kind,at=at,state=state,payload=json.loads(raw) if raw else None))
        complete = now>=end and all(s["state"]=="PASS" for s in slots)
        return dict(window=window,start=start,end=end,release=release,
                    elapsed_seconds=max(0,min(now,end)-start),planned_health=288,planned_boundaries=48,
                    slots=slots,complete_elapsed=now>=end,
                    stability="24H_COMPLETE" if complete else "24H_STABILITY_NOT_PROVEN",
                    breaker=dict(failures=control[0],retry_at=control[1],halt=control[2]))


def resources(root):
    """Fail on caps, retain evidence rather than deleting original receipts."""
    import ctypes
    from ctypes import wintypes
    class Memory(ctypes.Structure):
        _fields_=[("cb",wintypes.DWORD),("faults",wintypes.DWORD),
                  *[(name,ctypes.c_size_t) for name in (
                      "peak","working","paged_peak","paged","nonpaged_peak","nonpaged","page","page_peak")]]
    memory=Memory()
    memory.cb=ctypes.sizeof(memory)
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    psapi=ctypes.WinDLL("psapi",use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(memory),memory.cb):
        raise Hold("RESOURCE_PROBE_UNAVAILABLE")
    root=Path(root)
    used=sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    free=shutil.disk_usage(root).free
    result=dict(working_set_bytes=memory.working,disk_bytes=used,disk_free_bytes=free,cpu_seconds=time.process_time())
    if memory.working>512*1024*1024 or used>=1024*1024*1024 or free<512*1024*1024:
        raise Hold("RESOURCE_CAP")
    return result


def supervisor(root, window, *, activation, run_cycle, clock, wall=time.time, sleep=time.sleep):
    """Activation is a cryptographically verified release/window, never a bare flag."""
    from .ops24_clock import is_admin
    root=Path(root)
    if is_admin():
        raise Hold("NORMAL_USER_TOKEN_REQUIRED")
    if (root/"DISABLED").exists() or not activation():
        raise Hold("REVIEWED_ACTIVATION_REQUIRED")
    journal=RuntimeJournal(root)
    with process_lock(root/"lock") as owned:
        if not owned:
            raise Hold("SINGLETON_ALREADY_RUNNING")
        while True:
            current=wall()
            report=journal.report(window,current)
            if current>=report["end"]:
                return report
            if (root/"STOP_REQUESTED").exists() or (root/"DISABLED").exists() or not activation():
                atomic(root/"stopped.json",canonical(dict(at=current,reason="OPERATOR_STOP_OR_ACTIVATION_REVOKED")))
                return report
            journal.missed(window,current)
            report=journal.report(window,current)
            for slot in report["slots"]:
                if slot["state"]!="PLANNED" or not slot["at"]<=current<slot["at"]+(300 if slot["kind"]=="health" else 90):
                    continue
                if not journal.reserve(window,slot["kind"],slot["at"]):
                    continue
                try:
                    health=resources(root)
                    if not clock():
                        raise Hold("CLOCK_WITNESS_HOLD")
                    if slot["kind"]=="health":
                        payload,state=health,"PASS"
                    else:
                        control=report["breaker"]
                        if control["halt"] or current<control["retry_at"]:
                            raise Hold(control["halt"] or "RESTART_BACKOFF")
                        payload=run_cycle(slot["at"])
                        state="PASS" if payload.get("coverage")=="MARKET_COVERAGE_VERIFIED" else "PARTIAL"
                        reason=payload.get("stop")
                        hard=reason if reason and ("HTTP_429" in reason or "HTTP_418" in reason or "UNKNOWN" in reason) else None
                        journal.breaker(now=wall(),success=state=="PASS",hard_reason=hard)
                    journal.finish(window,slot["kind"],slot["at"],state,payload)
                except Hold as exc:
                    journal.finish(window,slot["kind"],slot["at"],"HOLD",dict(reason=str(exc)))
                    journal.breaker(now=wall(),success=False)
            atomic(root/"status.json",canonical(journal.report(window,wall())))
            sleep(1)
