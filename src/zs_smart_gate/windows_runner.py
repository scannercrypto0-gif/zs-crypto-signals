"""Offline Windows timing pilot. No network implementation or LIVE switch.

Temporary receipts suppress duplicates only while intact on this device. They are
not a journal, PIT evidence, or an exactly-once guarantee across hosts/reboots.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Protocol

UTC = timezone.utc
RIYADH = timezone(timedelta(hours=3), "Asia/Riyadh")
HORIZONS = {"5m": 300, "30m": 1800, "4h": 14400}
ELIGIBLE = "ELIGIBLE_TO_CAPTURE"
LATE = "STALE/LATE"


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware UTC timestamp required")
    return value.astimezone(UTC)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Event:
    symbol: str
    horizon: str
    close: datetime

    def payload(self):
        return {"symbol": self.symbol, "horizon": self.horizon,
                "close": utc(self.close).isoformat()}

    @property
    def id(self):
        return digest(self.payload())


@dataclass(frozen=True)
class Scope:
    events: tuple[Event, ...] = ()
    symbols: tuple[str, ...] = ("BTCUSDT",)
    horizons: tuple[str, ...] = ("5m", "30m", "4h")
    grace_seconds: float = 30
    budget_seconds: float = 5
    max_attempts: int = 8
    simulation_only: bool = True

    def __post_init__(self):
        if (not self.simulation_only or not 0 < self.grace_seconds <= 60
                or not 0 < self.budget_seconds <= 10
                or not 1 <= self.max_attempts <= 8 or len(self.events) > 8
                or len({e.id for e in self.events}) != len(self.events)):
            raise ValueError("invalid bounded simulation scope")

    @property
    def sha(self):
        return digest({**asdict(self), "events": [e.payload() for e in self.events]})


@dataclass(frozen=True)
class ClockProof:
    sampled_at: datetime
    offset_seconds: float
    rtt_seconds: float
    uncertainty_seconds: float | None
    simulated: bool = True

    def trusted(self, now):
        numbers = (self.offset_seconds, self.rtt_seconds, self.uncertainty_seconds)
        return (all(v is not None and math.isfinite(v) for v in numbers)
                and 0 <= self.rtt_seconds <= 1
                and self.rtt_seconds / 2 <= self.uncertainty_seconds <= 1
                and abs(self.offset_seconds) <= 1
                and 0 <= (utc(now) - utc(self.sampled_at)).total_seconds() <= 30)


def estimate_clock(sent, received, server_time, uncertainty=None):
    """Separate exchange sample; OS/NTP status alone never proves Binance time."""
    sent, received, server_time = map(utc, (sent, received, server_time))
    rtt = (received - sent).total_seconds()
    return ClockProof(received, (server_time - (sent + (received - sent) / 2)).total_seconds(),
                      rtt, uncertainty, simulated=False)


def admission(event: Event, scope: Scope, now: datetime, proof: ClockProof | None):
    now, close = utc(now), utc(event.close)
    if (event not in scope.events or event.symbol not in scope.symbols
            or event.horizon not in scope.horizons or event.horizon not in HORIZONS
            or close.timestamp() % HORIZONS[event.horizon] != 0):
        return "UNAPPROVED_SCOPE"
    if proof is None or not proof.trusted(now):
        return "CLOCK_UNTRUSTED"
    corrected = now + timedelta(seconds=proof.offset_seconds)
    uncertainty = timedelta(seconds=proof.uncertainty_seconds)
    if corrected - uncertainty < close:
        return "NOT_YET_CLOSED"
    if corrected + uncertainty >= close + timedelta(seconds=scope.grace_seconds):
        return LATE
    return ELIGIBLE


class DurableJournal(Protocol):
    """Integration contract only; implementation/authorization is a separate gate."""
    def claim(self, event_id: str, config_sha: str) -> bool: ...


def live_gate():
    return "BLOCKED / OWNER DECISION: approved durable GitHub journal and LIVE authorization required"


@contextmanager
def process_lock(directory: Path):
    """Kernel-held lock released on process crash; never delete the lock inode."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "runner.lock").open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            pass
        try:
            yield acquired
        finally:
            if acquired:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class ReceiptError(Exception):
    pass


def read_receipts(path):
    if not path.exists():
        return {"version": 1, "last_utc": None, "claims": {}}
    try:
        if path.stat().st_size > 131072:
            raise ValueError()
        data = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or data["version"] != 1 or not isinstance(data["claims"], dict)
                or len(data["claims"]) > 128
                or any(len(k) != 64 or any(c not in '0123456789abcdef' for c in k)
                       or v != "CLAIMED" for k, v in data["claims"].items())):
            raise ValueError()
        if data["last_utc"] is not None:
            utc(datetime.fromisoformat(data["last_utc"]))
        return data
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise ReceiptError("corrupt receipt; fail closed, do not reset automatically") from exc


def save_receipts(path, data):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class SimulatedTransport:
    """Bounded fixture transport. No URLs, sockets, adapters, credentials or retries."""
    def __init__(self, outcomes=()):
        self.outcomes = iter(outcomes)
        self.attempts = 0

    def request(self, event, timeout):
        self.attempts += 1
        outcome = next(self.outcomes, "OK")
        if outcome in ("429", "TIMEOUT", "OFFLINE"):
            raise OSError(outcome)
        return {"fixture": True, "event_id": event.id}


def tick(scope, directory, clock=lambda: datetime.now(UTC), monotonic=time.monotonic,
         proof=None, transport=None):
    """One bounded simulated batch. Claim before attempt; failures are not replayed."""
    if transport is not None and type(transport) is not SimulatedTransport:
        raise ValueError("only built-in offline fixture transport is permitted")
    start, mono_start = utc(clock()), monotonic()
    result = {"mode": "DRY_RUN", "trigger_utc": start.isoformat(),
              "riyadh": start.astimezone(RIYADH).isoformat(), "config_sha": scope.sha,
              "input_sha": digest([e.payload() for e in scope.events]), "events": [],
              "attempts": 0, "http_attempts": 0, "exit_code": 0,
              "budget_seconds": scope.budget_seconds, "journal_gate": live_gate(),
              "clock": asdict(proof) if proof else "UNKNOWN"}
    if proof:
        result["clock"]["sampled_at"] = utc(proof.sampled_at).isoformat()
    with process_lock(Path(directory)) as acquired:
        if not acquired:
            return {**result, "status": "LOCK_BUSY", "exit_code": 2}
        path = Path(directory) / "receipts.json"
        try:
            receipts = read_receipts(path)
        except ReceiptError:
            return {**result, "status": "CLOCK_UNTRUSTED", "reason": "CORRUPT_RECEIPT", "exit_code": 2}
        if receipts["last_utc"] and start < datetime.fromisoformat(receipts["last_utc"]):
            return {**result, "status": "CLOCK_UNTRUSTED", "reason": "BACKWARD_CLOCK", "exit_code": 2}
        receipts["last_utc"] = start.isoformat()
        save_receipts(path, receipts)
        for event in scope.events:
            now, elapsed = utc(clock()), monotonic() - mono_start
            status = admission(event, scope, now, proof)
            if abs((now - start).total_seconds() - elapsed) > 1 or elapsed < 0:
                status = "CLOCK_UNTRUSTED"
            elif elapsed >= scope.budget_seconds:
                status = LATE
            row = {"event_id": event.id, "close_utc": utc(event.close).isoformat(),
                   "trigger_minus_close_seconds": (start - utc(event.close)).total_seconds(),
                   "status": status, "receipt_utc": None, "decision_utc": now.isoformat()}
            result["events"].append(row)
            if event.id in receipts["claims"]:
                row.update(status=LATE, reason="DUPLICATE_OR_INTERRUPTED")
                continue
            if status != ELIGIBLE:
                continue
            if len(receipts["claims"]) >= 128:
                row.update(status="UNAPPROVED_SCOPE", reason="TEMP_BUFFER_FULL")
                continue
            receipts["claims"][event.id] = "CLAIMED"
            save_receipts(path, receipts)
            if transport is None:
                row["reason"] = "SIMULATED_ADMISSION_ONLY"
                continue
            if result["attempts"] >= scope.max_attempts:
                row.update(status=LATE, reason="ATTEMPT_BUDGET")
                continue
            # Disk claim may be slow. Recheck immediately before dispatch.
            dispatch, elapsed = utc(clock()), monotonic() - mono_start
            if (admission(event, scope, dispatch, proof) != ELIGIBLE
                    or elapsed >= scope.budget_seconds or elapsed < 0
                    or abs((dispatch - start).total_seconds() - elapsed) > 1):
                row.update(status=LATE, reason="DISPATCH_DEADLINE")
                continue
            result["attempts"] += 1
            try:
                transport.request(event, min(scope.budget_seconds - elapsed,
                    (utc(event.close) + timedelta(seconds=scope.grace_seconds) - dispatch).total_seconds()))
                receipt = utc(clock())
                row["receipt_utc"] = receipt.isoformat()
                if admission(event, scope, receipt, proof) != ELIGIBLE:
                    row.update(status=LATE, reason="RECEIPT_DEADLINE")
            except OSError as exc:
                row.update(status=LATE, reason=str(exc))
            decision, elapsed = utc(clock()), monotonic() - mono_start
            row["decision_utc"] = decision.isoformat()
            if abs((decision - start).total_seconds() - elapsed) > 1 or elapsed < 0:
                row["status"] = "CLOCK_UNTRUSTED"
            elif admission(event, scope, decision, proof) != ELIGIBLE or elapsed >= scope.budget_seconds:
                row["status"] = LATE
        result["status"] = "SIMULATION_COMPLETE"
        result["exit_code"] = int(any(e["status"] != ELIGIBLE for e in result["events"]))
        # One overwritten, bounded, metadata-only diagnostic; never response bodies/secrets.
        (Path(directory) / "last-diagnostic.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--once", action="store_true", default=True)
    parser.add_argument("--state-dir", type=Path, default=Path(tempfile.gettempdir()) / "zs-win-runner-pilot")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)
    if args.status:
        path = args.state_dir / "last-diagnostic.json"
        print(path.read_text(encoding="utf-8") if path.exists() and path.stat().st_size <= 131072 else "NO_BOUNDED_DIAGNOSTIC")
        return 0
    result = tick(Scope(), args.state_dir)
    print(json.dumps(result, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
