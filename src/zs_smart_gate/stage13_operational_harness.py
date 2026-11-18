"""Stage13 bounded synthetic cycle controller with injected offline ports."""
import json
from dataclasses import dataclass
from math import ceil

from .stage05_contracts import ContractError, canonical, digest, parse_utc

VERSION = "zs.stage13.synthetic-operations.v1"
SCOPE = "SYNTHETIC_TEST_ONLY"
STAGES = ("github", "telegram_a", "telegram_b", "telegram_c", "sql", "outcome")
HYPOTHETICAL_SCAN_WEIGHT = 3


class MockUnavailable(RuntimeError):
    """Injected failure at a synthetic integration boundary."""


@dataclass(frozen=True)
class Ports:
    scanner: object
    github: object
    telegram: object
    sql: object
    outcome: object
    utc_now: object
    monotonic_ns: object


class CycleController:
    """Single-process bounded controller; the local journal can be reopened."""

    def __init__(self, *, journal, ports, quota, max_drift_seconds=1, max_age_seconds=90):
        for value in (quota, max_drift_seconds, max_age_seconds):
            if type(value) is not int or value < 1:
                raise ContractError("S13_LIMIT_INVALID")
        self.journal, self.ports, self.quota = journal, ports, quota
        self.max_drift_seconds, self.max_age_seconds = max_drift_seconds, max_age_seconds
        self.weight = 0

    def _put(self, key, value):
        self.journal.create_if_absent(key, value)
        if self.journal.read(key) != value:
            raise ContractError("S13_LOCAL_READBACK_CONFLICT")

    def _signal(self, row):
        if not isinstance(row, dict) or row.get("scope") != SCOPE:
            raise ContractError("S13_SYNTHETIC_SOURCE_REQUIRED")
        if row.get("source_id") != "SYNTHETIC:STAGE13" or row.get("coverage") != "COMPLETE_FIXTURE":
            raise ContractError("S13_SOURCE_OR_COVERAGE_INVALID")
        if row.get("closed") is not True:
            raise ContractError("S13_INCOMPLETE_CANDLE")
        now = parse_utc(self.ports.utc_now())
        close, received, available, reference = (parse_utc(row[k]) for k in
            ("closed_at", "received_at", "available_at", "reference_at"))
        if not close <= received <= available <= now:
            raise ContractError("S13_MARKET_TIME_INVALID")
        if abs((now-reference).total_seconds()) > self.max_drift_seconds:
            raise ContractError("S13_CLOCK_DRIFT")
        if (now-close).total_seconds() > self.max_age_seconds:
            raise ContractError("S13_STALE_CANDLE")
        if row.get("qualified_fixture") is not True:
            return None
        fields = (row["symbol"], row["direction"], row["rule"])
        if (any(not isinstance(v, str) or not v.strip() for v in fields)
                or row["direction"] not in ("UP", "DOWN")):
            raise ContractError("S13_SIGNAL_IDENTITY_INVALID")
        identity = [VERSION, SCOPE, row["source_id"], close.isoformat(), *fields]
        return {"schema": VERSION, "scope": SCOPE, "signal_id": "fixture-" + digest(canonical(identity)),
                "symbol": row["symbol"], "direction": row["direction"], "rule": row["rule"],
                "closed_at": close.isoformat(), "trading_authorized": False}

    def _report(self, status, **details):
        return {"status":status, "scope":SCOPE, "readiness":"NOT_READY",
                "trading_authorized":False, "hypothetical_weight_used":self.weight, **details}

    def scan_once(self):
        if self.weight + HYPOTHETICAL_SCAN_WEIGHT > self.quota:
            return self._report("QUOTA_EXHAUSTED")
        self.weight += HYPOTHETICAL_SCAN_WEIGHT
        try:
            signal = self._signal(self.ports.scanner())
        except MockUnavailable:
            return self._report("SCAN_UNAVAILABLE")
        except (ContractError, KeyError, TypeError) as exc:
            return self._report("INVALID_OBSERVATION",
                                reason=str(exc) if isinstance(exc, ContractError) else "S13_MALFORMED_ROW")
        if signal is None:
            return self._report("NO_QUALIFIED_FIXTURE")
        raw = canonical(signal)
        signal_id = signal["signal_id"]
        try:
            self._put("signal/" + signal_id.removeprefix("fixture-"), raw)
        except (ContractError, TypeError):
            return self._report("INVALID_STORED_SIGNAL", signal_id=signal_id)
        return self.resume(signal_id)

    def _stored_signal_valid(self, signal):
        return True

    def resume(self, signal_id, *, expected_sha256=None):
        """Resume a stored fixture or restore only with an independent checksum pin."""
        if not isinstance(signal_id, str):
            raise ContractError("S13_FIXTURE_ID_REQUIRED")
        stem = signal_id.removeprefix("fixture-")
        if not signal_id.startswith("fixture-") or len(stem) != 64 or any(c not in "0123456789abcdef" for c in stem):
            raise ContractError("S13_FIXTURE_ID_REQUIRED")
        key = "signal/" + stem
        try:
            raw = self.journal.read(key)
        except (ContractError, TypeError):
            return self._report("INVALID_STORED_SIGNAL", signal_id=signal_id)
        if raw is not None and not isinstance(raw, bytes):
            return self._report("INVALID_STORED_SIGNAL", signal_id=signal_id)
        if raw is None:
            if expected_sha256 is None:
                return self._report("RESTORE_PIN_REQUIRED", signal_id=signal_id)
            try:
                raw = self.ports.github.read(signal_id)
            except MockUnavailable:
                return self._report("RESTORE_UNAVAILABLE", signal_id=signal_id)
            if not isinstance(raw, bytes):
                return self._report("RESTORE_UNAVAILABLE", signal_id=signal_id)
        sha = digest(raw)
        if expected_sha256 is not None and sha != expected_sha256:
            return self._report("RESTORE_CHECKSUM_MISMATCH", signal_id=signal_id)
        try:
            signal = json.loads(raw)
            if (signal.get("signal_id") != signal_id or signal.get("scope") != SCOPE
                    or signal.get("schema") != VERSION or signal.get("trading_authorized") is not False
                    or canonical(signal) != raw or not self._stored_signal_valid(signal)):
                raise ValueError
        except (AttributeError, TypeError, ValueError):
            return self._report("INVALID_STORED_SIGNAL", signal_id=signal_id)
        receipts, pending = {}, []
        for stage in STAGES:
            stage_key = digest(canonical([stage,signal_id]))
            local_key = "ack/" + stage_key
            expected_ack = canonical({"mock":True, "key":stage_key, "signal_id":signal_id,
                                      "stage":stage, "sha256":sha})
            try:
                cached = self.journal.read(local_key)
            except (ContractError, TypeError):
                return self._report("INVALID_STORED_ACK", stage=stage, signal_id=signal_id)
            if cached is None:
                pending.append((stage, stage_key, local_key, expected_ack))
            elif type(cached) is not bytes or cached != expected_ack:
                return self._report("INVALID_STORED_ACK", stage=stage, signal_id=signal_id)
            else:
                receipts[stage] = json.loads(cached)
        try:
            self._put(key, raw)
        except (ContractError, TypeError):
            return self._report("INVALID_STORED_SIGNAL", signal_id=signal_id)
        for stage, stage_key, local_key, expected_ack in pending:
            try:
                if stage == "github":
                    ack = self.ports.github.put(stage_key, signal_id, raw)
                    if self.ports.github.read(signal_id) != raw:
                        return self._report("STORAGE_READBACK_MISMATCH", signal_id=signal_id,
                                            sha256=sha, receipts=receipts)
                elif stage.startswith("telegram_"):
                    ack = self.ports.telegram(stage_key, stage[-1].upper(), signal_id, raw)
                elif stage == "sql":
                    ack = self.ports.sql(stage_key, signal_id, raw)
                else:
                    ack = self.ports.outcome(stage_key, signal_id, raw)
            except MockUnavailable:
                return self._report("PENDING_MOCK_RETRY", stage=stage, signal_id=signal_id,
                                    sha256=sha, receipts=receipts)
            if ack != stage_key:
                return self._report("INVALID_MOCK_ACK", stage=stage, signal_id=signal_id,
                                    sha256=sha, receipts=receipts)
            try:
                self._put(local_key, expected_ack)
            except (ContractError, TypeError):
                return self._report("INVALID_STORED_ACK", stage=stage, signal_id=signal_id)
            receipts[stage] = json.loads(expected_ack)
        return self._report("MOCK_PASS", signal_id=signal_id, sha256=sha, receipts=receipts)

    def recover_page(self, *, after=None, limit=20):
        """Recover a bounded page of local fixture records without scanning."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ContractError("S13_RECOVERY_PAGE_LIMIT")
        keys = self.journal.list_keys("signal", after=after, limit=limit+1)
        reports = []
        for key in keys[:limit]:
            report = self.resume("fixture-" + key.removeprefix("signal/"))
            reports.append(report)
            if report["status"] != "MOCK_PASS":
                # Keep the caller's cursor at the last verified record.
                return self._report("RECOVERY_BLOCKED", reports=reports, next_after=after)
            after = key
        return self._report("RECOVERY_PAGE_PASS", reports=reports,
                            next_after=after if len(keys) > limit else None)

    def run(self, cycles):
        if type(cycles) is not int or not 1 <= cycles <= 1000:
            raise ContractError("S13_CYCLE_LIMIT")
        reports, samples = [], []
        for _ in range(cycles):
            before = self.ports.monotonic_ns()
            reports.append(self.scan_once())
            after = self.ports.monotonic_ns()
            if type(before) is not int or type(after) is not int or after < before:
                raise ContractError("S13_MONOTONIC_CLOCK_INVALID")
            samples.append(after-before)
        ordered = sorted(samples)
        return {"reports":reports, "mock_latency_ns":{
            "p50":ordered[ceil(len(ordered)*.50)-1], "p95":ordered[ceil(len(ordered)*.95)-1]},
            "health":"MOCK_HEALTHY" if all(r["status"] in ("MOCK_PASS","NO_QUALIFIED_FIXTURE")
                                          for r in reports) else "MOCK_DEGRADED",
            "readiness":"NOT_READY", "trading_authorized":False}
