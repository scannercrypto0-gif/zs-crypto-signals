"""Adaptive provider interval ledger; conservative atomic worst-case admission.

RAW envelopes apply only to REST requests with the pinned documented minimum
weight of one. Unsupported/unbounded counters fail closed, not presumed empty.
"""
from contextlib import closing
from email.utils import parsedate_to_datetime
import json
import math
from pathlib import Path
import re
import sqlite3
import time

from .stage05_contracts import canonical,digest

VERSION='ZS_REST_ADAPTIVE_INTERVALS_V2'
SECONDS={'SECOND':1,'MINUTE':60,'HOUR':3600,'DAY':86400}
LETTERS={'s':1,'m':60,'h':3600,'d':86400}
# Official Spot REST reference inspected 2026-11-21; no zero-cost REST route.
REST_WEIGHT_REFERENCE='e7b6eade603cd0db0fc88e717ba67a58e19e0089'


class QuotaHold(RuntimeError):
    pass


class Intervals:
    def __init__(self,root,*,wall=time.time,timeout=8):
        self.path=Path(root)/'provider-intervals.sqlite'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.wall,self.timeout=wall,timeout
        with closing(self.open()) as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS limits(kind TEXT,seconds INTEGER,cap INTEGER,PRIMARY KEY(kind,seconds));
            CREATE TABLE IF NOT EXISTS buckets(kind TEXT,seconds INTEGER,epoch INTEGER,charged INTEGER,
              observed INTEGER,samples INTEGER,first REAL,last REAL,jump REAL,PRIMARY KEY(kind,seconds,epoch));
            CREATE TABLE IF NOT EXISTS intents(token TEXT PRIMARY KEY,route TEXT,weight INTEGER,state TEXT,windows BLOB,issued REAL,receipt TEXT);
            CREATE TABLE IF NOT EXISTS control(id INTEGER PRIMARY KEY,until REAL,reason TEXT,metadata TEXT);
            INSERT OR IGNORE INTO control VALUES(1,0,NULL,NULL);
            ''')

    def open(self):
        db=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        return db

    def adopt(self,rows):
        parsed={}
        for row in rows:
            kind=row['rateLimitType']
            if kind=='ORDERS':
                continue  # This client never places an order; zero order count.
            if kind not in ('REQUEST_WEIGHT','RAW_REQUESTS'):
                raise QuotaHold('UNSUPPORTED_PROVIDER_LIMIT')
            n,cap=row['intervalNum'],row['limit']
            if (type(n) is not int or n<1 or type(cap) is not int or cap<1
                    or row['interval'] not in SECONDS):
                raise QuotaHold('INVALID_PROVIDER_LIMIT')
            key=(kind,n*SECONDS[row['interval']])
            if key in parsed:
                raise QuotaHold('DUPLICATE_PROVIDER_LIMIT')
            parsed[key]=cap
        if not any(k[0]=='REQUEST_WEIGHT' for k in parsed):
            raise QuotaHold('NO_CONFIRMED_WEIGHT_LIMIT')
        with closing(self.open()) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM limits')
            db.executemany('INSERT INTO limits VALUES(?,?,?)',[(k,s,c) for (k,s),c in parsed.items()])
            db.execute('UPDATE control SET metadata=? WHERE id=1',(digest(canonical(rows)),))
            db.commit()

    @staticmethod
    def target(cap):
        return cap*59//60

    def _usage(self,db,kind,seconds,epoch):
        row=db.execute('SELECT * FROM buckets WHERE kind=? AND seconds=? AND epoch=?',
                       (kind,seconds,epoch)).fetchone()
        return dict(row) if row else dict(charged=0,observed=0,samples=0,first=self.wall(),last=self.wall(),jump=0)

    def _ceiling(self,row,cap):
        # The preferred 59/60 target is reached only after a stable measured quorum.
        confident=row['samples']>=4 and row['last']-row['first']>=1
        margin=max(cap-self.target(cap),math.ceil(row['jump']*(self.timeout+2)),
                   0 if confident else math.ceil(cap*.10))
        return max(0,cap-margin)

    def _raw_envelope(self,limits,seconds):
        # Bound every RAW request by >=1 provider-weight point, including shared IP.
        candidates=[cap*(seconds//period) for kind,period,cap in limits
                    if kind=='REQUEST_WEIGHT' and seconds%period==0]
        return min(candidates) if candidates else None

    def reserve(self,token,route,weight):
        if type(weight) is not int or weight<=0:
            raise QuotaHold("INVALID_WORST_CASE_WEIGHT")
        now=self.wall()
        with closing(self.open()) as db:
            db.execute('BEGIN IMMEDIATE')
            # Interrupted reservations become durable unknowns, never free retries.
            stale=list(db.execute("SELECT token FROM intents WHERE state='RESERVED' AND issued+?<?",(120,now)))
            if stale:
                db.executemany("UPDATE intents SET state='UNKNOWN' WHERE token=?",[(r[0],) for r in stale])
                longest=db.execute('SELECT COALESCE(MAX(seconds),60) FROM limits').fetchone()[0]
                db.execute('UPDATE control SET until=?,reason=? WHERE id=1',(now+longest+self.timeout+2,'UNKNOWN_READ_COOLDOWN'))
                db.commit()
                raise QuotaHold('UNKNOWN_READ_COOLDOWN')
            ctl=db.execute('SELECT * FROM control').fetchone()
            if ctl['reason'] and (ctl['until'] is None or now<ctl['until']):
                raise QuotaHold(ctl['reason'])
            if db.execute('SELECT 1 FROM intents WHERE token=?',(token,)).fetchone():
                raise QuotaHold('GLOBAL_UNKNOWN_OR_DUPLICATE_INTENT')
            limits=[tuple(r) for r in db.execute('SELECT * FROM limits')]
            if not limits:
                if route!='exchangeInfo' or db.execute('SELECT 1 FROM intents LIMIT 1').fetchone():
                    raise QuotaHold('ONLY_SINGLE_DISCOVERY_BOOTSTRAP_ALLOWED')
                windows=[]
            else:
                windows=[]
                orphan_weight=db.execute("SELECT COALESCE(SUM(weight),0) FROM intents WHERE state='UNKNOWN'").fetchone()[0]
                orphans=db.execute("SELECT COUNT(*) FROM intents WHERE state='UNKNOWN'").fetchone()[0]
                for kind,seconds,cap in limits:
                    # Reserve all possible provider windows until timeout + clock jitter.
                    for epoch in range(math.floor((now-1)/seconds),math.floor((now+self.timeout+1)/seconds)+1):
                        row=self._usage(db,kind,seconds,epoch)
                        cost=weight if kind=='REQUEST_WEIGHT' else 1
                        ceiling=self._ceiling(row,cap)
                        use=row['charged']+(orphan_weight if kind=='REQUEST_WEIGHT' else orphans)
                        if kind=='RAW_REQUESTS' and row['samples']==0:
                            envelope=self._raw_envelope(limits,seconds)
                            if envelope is None:
                                raise QuotaHold('RAW_SHARED_IP_UNBOUNDED')
                            # This envelope covers all local+external REST requests.
                            use=max(use,envelope)
                        if use+cost>ceiling:
                            raise QuotaHold('INTERVAL_HEADROOM_'+kind+'_'+str(seconds))
                        windows.append((kind,seconds,epoch,cost))
                for kind,seconds,epoch,cost in windows:
                    db.execute('''INSERT INTO buckets VALUES(?,?,?,?,0,0,?,?,0)
                      ON CONFLICT(kind,seconds,epoch) DO UPDATE SET charged=charged+excluded.charged''',
                      (kind,seconds,epoch,cost,now,now))
            db.execute("INSERT INTO intents VALUES(?,?,?,'RESERVED',?,?,NULL)",
                       (token,route,weight,canonical(windows),now))
            db.commit()

    def complete(self,token,receipt,headers):
        now=self.wall()
        parsed=[]
        for name,value in headers.items():
            m=re.fullmatch(r'x-mbx-used-(weight|raw-requests)-(\d+)([smhd])',name.lower())
            if not m:
                continue
            if not str(value).isascii() or not str(value).isdecimal() or len(str(value))>12:
                raise QuotaHold('INVALID_INTERVAL_HEADER')
            parsed.append(('REQUEST_WEIGHT' if m[1]=='weight' else 'RAW_REQUESTS',int(m[2])*LETTERS[m[3]],int(value)))
        with closing(self.open()) as db:
            db.execute('BEGIN IMMEDIATE')
            intent=db.execute('SELECT * FROM intents WHERE token=?',(token,)).fetchone()
            if intent is not None and intent['state']=='COMPLETE' and intent['receipt']==digest(canonical(receipt)):
                db.commit()
                return  # Explicit same-byte reconciliation after a cycle commit crash.
            if intent is None or intent['state'] not in ('RESERVED','UNKNOWN'):
                raise QuotaHold('INTERVAL_INTENT_CONFLICT')
            status=receipt.get('http_status')
            if status in (429,418):
                retry=next((v for k,v in headers.items() if k.lower()=='retry-after'),None)
                try:
                    until=now+float(retry) if str(retry).isdecimal() else parsedate_to_datetime(str(retry)).timestamp()
                    if not math.isfinite(until) or until<now:raise ValueError()
                except (ValueError,TypeError,OverflowError):
                    until=None  # No legal automatic ban expiry can be inferred.
                db.execute('UPDATE control SET until=?,reason=? WHERE id=1',(until,'PROVIDER_'+str(status)+'_BACKOFF'))
            confirmed=[tuple(r) for r in db.execute('SELECT * FROM limits')]
            known={(k,s) for k,s,_ in confirmed}
            for kind,seconds,used in parsed:
                if (kind,seconds) not in known:
                    raise QuotaHold('UNADVERTISED_INTERVAL_HEADER')
                for epoch in range(math.floor((now-1)/seconds),math.floor((now+1)/seconds)+1):
                    row=self._usage(db,kind,seconds,epoch)
                    pending=0
                    for other in db.execute("SELECT windows FROM intents WHERE state='RESERVED' AND token!=?",(token,)):
                        pending+=sum(cost for k,s,e,cost in json.loads(other[0]) if (k,s,e)==(kind,seconds,epoch))
                    delta=max(0,used-row['observed']-max(0,row['charged']-row['observed']))
                    velocity=delta/max(.001,now-row['last']) if row['samples'] else 0
                    charged=max(row['charged'],used+pending)
                    db.execute('''INSERT INTO buckets VALUES(?,?,?,?,?,?,?,?,?)
                      ON CONFLICT(kind,seconds,epoch) DO UPDATE SET charged=excluded.charged,
                      observed=MAX(observed,excluded.observed),samples=samples+1,last=excluded.last,
                      jump=MAX(jump*.9,excluded.jump)''',
                      (kind,seconds,epoch,charged,used,1,row['first'],now,velocity))
            missing=[(k,s) for k,s,_ in confirmed if k=='REQUEST_WEIGHT' and (k,s) not in {(k,s) for k,s,_ in parsed}]
            if status==200 and missing:
                raise QuotaHold('MISSING_PROVIDER_WEIGHT_INTERVAL_HEADER')
            state='UNKNOWN' if status is None and receipt.get('http_attempted',True) else 'COMPLETE'
            db.execute('UPDATE intents SET state=?,receipt=? WHERE token=?',
                       (state,digest(canonical(receipt)),token))
            if state=='UNKNOWN':
                longest=max((s for _,s,_ in confirmed),default=60)
                db.execute('UPDATE control SET until=?,reason=? WHERE id=1',(now+longest+self.timeout+2,'UNKNOWN_READ_COOLDOWN'))
            db.commit()

    def abandon(self,token,reason):
        with closing(self.open()) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE intents SET state='UNKNOWN' WHERE token=?",(token,))
            longest=db.execute('SELECT COALESCE(MAX(seconds),60) FROM limits').fetchone()[0]
            db.execute('UPDATE control SET until=?,reason=? WHERE id=1',
                       (self.wall()+longest+self.timeout+2,reason))
            db.commit()

    def report(self):
        with closing(self.open()) as db:
            return dict(version=VERSION,reference=REST_WEIGHT_REFERENCE,
                limits=[dict(r)|{'preferred':self.target(r['cap'])} for r in db.execute('SELECT * FROM limits')],
                control=dict(db.execute('SELECT * FROM control').fetchone()),
                buckets=[dict(r) for r in db.execute('SELECT * FROM buckets')],
                unknown=db.execute("SELECT COUNT(*) FROM intents WHERE state='UNKNOWN'").fetchone()[0])
