"""Actual Serve lifecycle validation; hard no-market scope, never a 24h soak PASS."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time
import uuid

from .ops24_budget import Hold
from .ops24_runtime import resources
from .ops24_source import atomic
from .ops24_release_clock import RECOVERY
from .stage05_contracts import canonical,digest
from .windows_runner import process_lock

def verify_recovery(root,head,tree):
    root=Path(root);config=json.loads((root/'release.json').read_bytes())
    raw=(root/'recovery-authority.json').read_bytes();record=json.loads(raw)
    if (config.get('scope')!=RECOVERY or config.get('head')!=head or config.get('tree')!=tree
            or digest(raw)!=config.get('recovery_authority_sha256')
            or record.get('schema')!='zs.ops77.recovery-authority.v1'
            or record.get('scope')!=RECOVERY or record.get('head')!=head or record.get('tree')!=tree
            or record.get('directive_id')!=7076686518
            or record.get('directive_sha256')!=digest(record.get('directive_body','').encode())
            or 'PRODUCTION_SERVE_UNPROVEN' not in record.get('directive_body','')
            or record.get('windows_tests',{}).get('head')!=head
            or record.get('windows_tests',{}).get('tree')!=tree
            or record.get('windows_tests',{}).get('tests',0)<=0):
        raise Hold('RECOVERY_SCOPE_OR_PIN_UNVERIFIED')
    return config,record

def serve_recovery(root,head,tree,clock,*,observe,wall=time.time,sleep=time.sleep):
    root=Path(root);config,record=verify_recovery(root,head,tree)
    end=record['expires_epoch']
    if not isinstance(end,int) or not record['created_epoch']<=wall()<=end or end-record['created_epoch']!=86400:
        raise Hold('RECOVERY_VALIDATION_WINDOW_INVALID')
    release=(root/'release.json').read_bytes();authority=(root/'recovery-authority.json').read_bytes()
    db=sqlite3.connect(root/'recovery.sqlite',timeout=5,isolation_level=None)
    db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,session TEXT,utc REAL,kind TEXT,payload BLOB,sha TEXT)')
    db.execute("CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append only');END")
    db.execute("CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append only');END")
    if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':
        db.close();raise Hold('RECOVERY_JOURNAL_CORRUPT')
    for raw,pin in db.execute('SELECT payload,sha FROM events'):
        if digest(raw)!=pin:db.close();raise Hold('RECOVERY_EVENT_HASH_MISMATCH')
    prior=db.execute('SELECT session,kind FROM events ORDER BY id DESC LIMIT 1').fetchone()
    session=uuid.uuid4().hex
    def event(kind,data):
        raw=canonical(data);db.execute('INSERT INTO events(session,utc,kind,payload,sha) VALUES(?,?,?,?,?)',(session,wall(),kind,raw,digest(raw)))
    try:
        with process_lock(root/'lock') as acquired:
            if not acquired:raise Hold('SINGLETON_ALREADY_RUNNING')
            identity=observe()
            if prior and prior[1] not in ('SERVE_STOP','RECOVERY_WINDOW_EXPIRED'):
                event('UNGRACEFUL_PREVIOUS_SESSION',dict(previous_session=prior[0],cause='NOT_INFERRED'))
            event('SERVE_START',dict(head=head,tree=tree,windows=identity,scope=RECOVERY))
            next_clock=0;clock_result=None
            while True:
                now=wall()
                if (root/'STOP_REQUESTED').exists() or (root/'DISABLED').exists():
                    event('SERVE_STOP',dict(reason='OWNER_STOP_OR_DISABLED'))
                    atomic(root/'stopped.json',canonical(dict(scope=RECOVERY,session=session,at=now,graceful=True)))
                    return 0
                if now>=end:
                    event('RECOVERY_WINDOW_EXPIRED',dict(not_a_market_soak=True));return 0
                if release!=(root/'release.json').read_bytes() or authority!=(root/'recovery-authority.json').read_bytes():
                    raise Hold('RECOVERY_RELEASE_OR_AUTHORITY_CHANGED')
                if now>=next_clock:
                    try:
                        if (root/'FAULT_NETWORK').exists():raise Hold('APP_NETWORK_FAILURE_INJECTED_NOT_PHYSICAL_OUTAGE')
                        witness=clock.refresh();raw=canonical(witness);pin=digest(raw)
                        atomic(root/('recovery-clock-'+pin+'.private.json'),raw)
                        clock_result=dict(status=witness['assessment']['status'],witness_sha256=pin)
                    except (Hold,OSError,ValueError,KeyError) as exc:
                        clock_result=dict(status='HOLD',reason=str(exc) if isinstance(exc,Hold) else type(exc).__name__)
                    event('SERVE_CLOCK',clock_result);next_clock=now+300
                payload=dict(schema='zs.ops77.serve-recovery-status.v1',head=head,tree=tree,session=session,
                    scope=RECOVERY,clock=clock_result,windows=identity,resources=resources(root),
                    at=now,expires_epoch=end,market_calls=0,telegram_calls=0,sql_writes=0,
                    stability='RECOVERY_VALIDATION_ONLY_NOT_24H_MARKET_SOAK')
                event('SERVE_HEARTBEAT',payload);atomic(root/'status.json',canonical(payload))
                sleep(5)
    finally:db.close()
