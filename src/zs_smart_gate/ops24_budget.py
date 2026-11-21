"""Versioned B1 research request ledger. No legacy capture limits are modified."""
from contextlib import closing
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sqlite3
import time

from .stage05_contracts import canonical, digest

VERSION = "ZS_OPS24_B1_REST_V1"
WEIGHTS = {"exchangeInfo": 20, "ticker/24hr": 80, "ticker/bookTicker": 4, "klines": 2}


class Hold(RuntimeError):
    pass


@dataclass(frozen=True)
class Policy:
    workers: int = 2
    max_seconds: int = 110
    freshness_seconds: int = 90
    request_timeout: int = 8
    max_body: int = 16 * 1024 * 1024
    candle_body: int = 256 * 1024
    max_bytes: int = 32 * 1024 * 1024
    max_observed_weight: int = 5500
    version: str = VERSION

    def validate(self):
        if (self.version != VERSION or self.workers not in (1, 2, 3, 4)
                or self.max_seconds != 110 or self.freshness_seconds != 90
                or self.request_timeout != 8 or self.max_body != 16*1024*1024
                or self.candle_body != 256*1024 or self.max_bytes != 32*1024*1024
                or self.max_observed_weight != 5500):
            raise Hold("UNREVIEWED_RESOURCE_POLICY")

    @property
    def sha256(self):
        self.validate()
        return digest(canonical(asdict(self)))


class Budget:
    def __init__(self, root, cycle, *, policy=Policy(), mono=time.monotonic, wall=time.time):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root/"budget.sqlite"
        self.policy, self.mono, self.wall = policy, mono, wall
        policy.validate()
        with closing(self.open()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS control(
                  id INTEGER PRIMARY KEY, cycle TEXT, policy TEXT, started REAL, wall REAL,
                  request_cap INTEGER, weight_cap INTEGER, requests INTEGER, weight INTEGER,
                  bytes INTEGER, reserved INTEGER, active INTEGER, used INTEGER, halt TEXT);
                CREATE TABLE IF NOT EXISTS quota(id INTEGER PRIMARY KEY, effective INTEGER);
                INSERT OR IGNORE INTO quota VALUES(1,5500);
                CREATE TABLE IF NOT EXISTS requests(
                  key TEXT PRIMARY KEY, path TEXT, params BLOB, state TEXT, body_sha TEXT, receipt BLOB);
            """)
            db.execute("INSERT OR IGNORE INTO control VALUES(1,?,?,?,?,3,104,0,0,0,0,0,0,NULL)",
                       (cycle, policy.sha256, mono(), wall()))
            current = tuple(db.execute("SELECT cycle,policy FROM control").fetchone())
            if current != (cycle, policy.sha256):
                raise Hold("CYCLE_OR_POLICY_IDENTITY_MISMATCH")

    def open(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def state(self):
        with closing(self.open()) as db:
            state=dict(db.execute("SELECT * FROM control").fetchone())
            state["effective_weight_limit"]=db.execute("SELECT effective FROM quota").fetchone()[0]
            return state

    def adopt_server_limit(self, limit):
        if type(limit) is not int or limit<=500:
            raise Hold("UNVERIFIED_SERVER_RATE_LIMIT")
        effective=min(self.policy.max_observed_weight,limit-500)
        with closing(self.open()) as db:
            db.execute("UPDATE quota SET effective=MIN(effective,?) WHERE id=1",(effective,))

    def freeze_universe(self, count):
        if type(count) is not int or not 1 <= count <= 20000:
            raise Hold("INVALID_DYNAMIC_UNIVERSE")
        with closing(self.open()) as db:
            db.execute("BEGIN IMMEDIATE")
            state = dict(db.execute("SELECT * FROM control").fetchone())
            cap, weight = 3 + 4*count, 104 + 8*count
            if (state["requests"] < 3 or state["active"] or state["halt"]
                    or state["request_cap"] not in (3, cap)
                    or state["used"] + max(0,weight-state["weight"]) >
                    db.execute("SELECT effective FROM quota").fetchone()[0]):
                db.rollback()
                raise Hold("UNIVERSE_FREEZE_OR_HEADROOM_BLOCKED")
            db.execute("UPDATE control SET request_cap=?,weight_cap=? WHERE id=1", (cap, weight))
            db.commit()

    def stop(self, reason):
        with closing(self.open()) as db:
            db.execute("UPDATE control SET halt=COALESCE(halt,?) WHERE id=1", (reason,))

    def remaining(self):
        state = self.state()
        return self.policy.max_seconds - (self.mono()-state["started"])

    def reserve(self, path, params):
        if path not in WEIGHTS:
            raise Hold("ENDPOINT_NOT_ALLOWED")
        key = digest(canonical([path, params]))
        body_cap = self.policy.candle_body if path == "klines" else self.policy.max_body
        with closing(self.open()) as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM requests WHERE key=?", (key,)).fetchone()
            if old is not None:
                db.rollback()
                if old["state"] != "COMMITTED":
                    raise Hold("UNCERTAIN_REQUEST_NO_REISSUE")
                receipt = json.loads(old["receipt"])
                raw = (self.root/(key+".private")).read_bytes()
                if digest(raw) != old["body_sha"]:
                    raise Hold("RECEIPT_BODY_CORRUPTION")
                return key, body_cap, receipt
            row = dict(db.execute("SELECT * FROM control").fetchone())
            effective=db.execute("SELECT effective FROM quota").fetchone()[0]
            elapsed = self.mono()-row["started"]
            disagreement = abs((self.wall()-row["wall"])-elapsed)
            reason = row["halt"]
            if reason is None:
                if elapsed < 0 or disagreement > .05:
                    reason = "CLOCK_STEP_OR_BOOT_CHANGE"
                elif elapsed >= self.policy.max_seconds:
                    reason = "DEADLINE"
                elif row["requests"] >= row["request_cap"]:
                    reason = "REQUEST_CAP"
                elif row["weight"] + WEIGHTS[path] > row["weight_cap"]:
                    reason = "ESTIMATED_WEIGHT_CAP"
                elif row["used"] + sum(
                        WEIGHTS[r[0]] for r in db.execute(
                            "SELECT path FROM requests WHERE state='RESERVED'")) + WEIGHTS[path] > effective:
                    reason = "OBSERVED_WEIGHT_HEADROOM"
                elif row["active"] >= self.policy.workers:
                    reason = "INFLIGHT_CAP"
                elif row["bytes"] + row["reserved"] + body_cap + 1 > self.policy.max_bytes:
                    reason = "BYTE_RESERVATION_CAP"
            if reason:
                db.rollback()
                raise Hold(reason)
            db.execute("INSERT INTO requests VALUES(?,?,?,'RESERVED',NULL,NULL)", (key,path,canonical(params)))
            db.execute("""UPDATE control SET requests=requests+1,weight=weight+?,
                          reserved=reserved+?,active=active+1 WHERE id=1""",
                       (WEIGHTS[path], body_cap+1))
            db.commit()
        return key, body_cap, None

    def reconcile(self, key):
        with closing(self.open()) as db:
            row=db.execute("SELECT path,params,state FROM requests WHERE key=?",(key,)).fetchone()
        if row is None or row["state"]!="RESERVED":
            raise Hold("RECONCILE_STATE_INVALID")
        path=self.root/(key+".receipt.json")
        if not path.exists() or not (self.root/(key+".private")).exists():
            raise Hold("RECONCILE_ORIGINAL_INCOMPLETE")
        receipt=json.loads(path.read_bytes())
        raw=(self.root/(key+".private")).read_bytes()
        if (receipt.get("path")!=row["path"] or receipt.get("params")!=json.loads(row["params"])
                or receipt.get("http_status")!=200 or receipt.get("body_sha256")!=digest(raw)
                or receipt.get("body_bytes")!=len(raw)
                or type(receipt.get("used_weight_1m")) is not int):
            raise Hold("RECONCILE_ORIGINAL_INVALID")
        cap=self.policy.candle_body if row["path"]=="klines" else self.policy.max_body
        self.finish(key,cap,receipt)

    def finish(self, key, body_cap, receipt, *, reason=None):
        with closing(self.open()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM requests WHERE key=?", (key,)).fetchone()
            if row is None or row[0] != "RESERVED":
                db.rollback()
                raise Hold("REQUEST_STATE_CONFLICT")
            size = receipt.get("body_bytes", body_cap+1)
            used = receipt.get("used_weight_1m", 0)
            state = dict(db.execute("SELECT * FROM control").fetchone())
            elapsed=self.mono()-state["started"]
            disagreement=abs((self.wall()-state["wall"])-elapsed)
            reason = reason or (
                "CLOCK_STEP_OR_BOOT_CHANGE" if elapsed<0 or disagreement>.05 else
                "OBSERVED_WEIGHT_HEADROOM" if used >= db.execute("SELECT effective FROM quota").fetchone()[0] else
                "BODY_CAP" if size > body_cap or state["bytes"]+size > self.policy.max_bytes else
                "DEADLINE" if self.mono()-state["started"] >= self.policy.max_seconds else None)
            db.execute("UPDATE requests SET state=?,body_sha=?,receipt=? WHERE key=?",
                       ("FAILED" if reason else "COMMITTED",receipt.get("body_sha256"),canonical(receipt),key))
            db.execute("""UPDATE control SET active=active-1,reserved=reserved-?,
                bytes=bytes+?,used=MAX(used,?),halt=COALESCE(halt,?) WHERE id=1""",
                       (body_cap+1,size,used,reason))
            db.commit()
        if reason:
            raise Hold(reason)
