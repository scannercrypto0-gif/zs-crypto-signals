"""ZS03 P0: offline-only, deliberately unarmable field harness.

NO socket/HTTP/WS client, no credentials, no scheduling, no live command.
Guards model *physical attempts* and can only record synthetic reservations.
A passing synthetic gate is NOT legal authority, market PIT or FIELD_CAPTURE_GO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

SCHEMA = "zs03.p0.offline-field-guard.v1"
MODE = "SYNTHETIC_ONLY"
REAL_FIELD_AUTHORIZED = False
GET_MAX = 12
GET_BASE = 11
GET_WEIGHT_MAX = 46
WS_MAX = 12
RAW_MAX = 4 * 1024 * 1024
FILE_MAX = 32
UNCERTAINTY_NS_MAX_EXCLUSIVE = 1_500_000_000
GENESIS = "0" * 64

REST_BASE = {
    "exchangeInfo/BTCUSDT,ETHUSDT": 20,
    "ticker/24hr/BTCUSDT,ETHUSDT": 2,
    "ticker/bookTicker/BTCUSDT,ETHUSDT": 4,
    **{f"klines/{pair}/{interval}": 2
       for pair in ("BTCUSDT", "ETHUSDT")
       for interval in ("5m", "1h", "1d", "1w")},
}
assert len(REST_BASE) == GET_BASE and sum(REST_BASE.values()) == 42
WS_BASE = {
    f"{pair.lower()}@{stream}"
    for pair in ("BTCUSDT", "ETHUSDT")
    for stream in ("bookTicker", "ticker", "kline_1m")
}
assert len(WS_BASE) == 6


class FieldBlocked(Exception):
    """Fail-closed. Never fall back to an external transport."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise FieldBlocked(reason)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bytes(obj: dict) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def synthetic_fixture() -> bytes:
    return b"origin=SYNTHETIC_ONLY\nmarket_requests=0\npayload=P0_HARNESS_DUMMY\n"


def synthetic_context(raw: bytes | None = None) -> dict:
    """Only a synthetic test fixture; these claims CANNOT authorize real capture."""
    raw = synthetic_fixture() if raw is None else raw
    return {
        "schema": SCHEMA,
        "mode": MODE,
        "armed": False,
        "host": "OFFLINE_FIXTURE",
        "licensed_for": "OFFLINE_SYNTHETIC_FIXTURE_ONLY",
        "pm_go": "SYNTHETIC_TEST_ONLY",
        "owner_go": "SYNTHETIC_TEST_ONLY",
        "receipt": {
            "owner_external_custody": "SYNTHETIC_SIMULATION_ONLY",
            "file_sha256_verified": True,
            "raw_sha256": _sha(raw),
            "raw_size_bytes": len(raw),
            "restored_raw_verified": True,
            "manifest_identity_verified": True,
        },
        "clock": {
            "nts_authenticated": True,  # injected simulation, never a live probe
            "sources_selected": "TEST_NTS_PEER_1",
            "authdata_selected": "TEST_NTS_PEER_1",
            "ntpdata_selected": "TEST_NTS_PEER_1",
            "tracking_selected": "TEST_NTS_PEER_1",
            "leap_normal": True,
            "source_fresh": True,
            "monotonic_ok": True,
            "utc_uncertainty_ns": 100_000_000,
            "input_available_latest_ns": 1_000_000_000,
            "decision_earliest_ns": 2_000_000_000,
        },
    }


def check_synthetic_context(ctx: dict, raw: bytes) -> None:
    require(isinstance(ctx, dict) and ctx.get("schema") == SCHEMA,
            "MISSING_APPROVED_SCHEMA")
    require(ctx.get("mode") == MODE and ctx.get("armed") is False,
            "LIVE_MODE_OR_ARMED_FORBIDDEN")
    require(ctx.get("host") == "OFFLINE_FIXTURE",
            "HOST_NOT_OFFLINE_ALLOWLIST")
    require(ctx.get("licensed_for") == "OFFLINE_SYNTHETIC_FIXTURE_ONLY",
            "SOURCE_LICENSE_NOT_PROVEN")
    require(ctx.get("pm_go") == "SYNTHETIC_TEST_ONLY" and
            ctx.get("owner_go") == "SYNTHETIC_TEST_ONLY",
            "APPROVALS_MISSING_OR_WRONG_SCOPE")
    require(type(raw) is bytes and raw.startswith(b"origin=SYNTHETIC_ONLY\n")
            and b"market_requests=0\n" in raw and
            b"payload=" in raw and len(raw) <= RAW_MAX,
            "SOURCE_NOT_SYNTHETIC_OR_RAW_OVERSIZE")
    rc = ctx.get("receipt")
    require(isinstance(rc, dict) and
            rc.get("owner_external_custody") == "SYNTHETIC_SIMULATION_ONLY" and
            rc.get("file_sha256_verified") is True and
            rc.get("restored_raw_verified") is True and
            rc.get("manifest_identity_verified") is True and
            rc.get("raw_sha256") == _sha(raw) and
            type(rc.get("raw_size_bytes")) is int and
            rc["raw_size_bytes"] == len(raw),
            "MISSING_OR_MISMATCHED_RAW_AND_OWNER_RECEIPT")
    clk = ctx.get("clock")
    require(isinstance(clk, dict), "CLOCK_WITNESS_MISSING")
    require(clk.get("nts_authenticated") is True and
            clk.get("source_fresh") is True and
            clk.get("leap_normal") is True and
            clk.get("monotonic_ok") is True,
            "CLOCK_WITNESS_INVALID_OR_STALE")
    peers = [clk.get(k) for k in ("sources_selected", "authdata_selected",
                                "ntpdata_selected", "tracking_selected")]
    require(all(x == "TEST_NTS_PEER_1" for x in peers),
            "CLOCK_SELECTED_PEER_MISMATCH")
    unc = clk.get("utc_uncertainty_ns")
    require(type(unc) is int and 0 <= unc < UNCERTAINTY_NS_MAX_EXCLUSIVE,
            "CLOCK_UNCERTAINTY_NOT_STRICTLY_BELOW_1_5S")
    availability = clk.get("input_available_latest_ns")
    decision = clk.get("decision_earliest_ns")
    require(type(availability) is int and type(decision) is int and
            availability <= decision, "AS_OF_CAUSAL_ORDER_UNPROVEN")


class SyntheticJournal:
    """One-writer, create-once, fsync-before-attempt event ledger. No network.

    An already existing journal is *blocked* on restart. Chain integrity can
    detect inadvertent damage, not malicious writer/admin alteration or WORM.
    """
    def __init__(self, path: Path, context: dict, raw: bytes):
        check_synthetic_context(context, raw)
        self.path = Path(path)
        self.ctx = context
        self.raw = raw
        self.prev = GENESIS
        self.rows: list[dict] = []
        self.rest_unique: set[str] = set()
        self.rest_count = 0
        self.rest_weight = 0
        self.ws_count = 0
        self.ws_unique: set[str] = set()
        self.raw_bytes = 0
        self.raw_files = 0
        self.blocked = False
        require(self.path.parent.is_dir(), "JOURNAL_PARENT_MISSING")
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except OSError as exc:
            raise FieldBlocked("JOURNAL_EXISTS_OR_UNWRITABLE_NO_RESUME") from exc
        self.handle = os.fdopen(fd, "wb", buffering=0)
        try:
            self._write("BEGIN", "OFFLINE_NO_NETWORK_CAPABILITY", 0)
        except Exception:
            self.blocked = True
            self.handle.close()
            raise

    def _write(self, kind: str, item: str, amount: int) -> None:
        require(not self.blocked and not self.handle.closed,
                "JOURNAL_BLOCKED")
        row = {"index": len(self.rows), "kind": kind, "item": item,
               "amount": amount, "prev": self.prev}
        digest = _sha(_bytes(row))
        row["hash"] = digest
        try:
            self.handle.write(_bytes(row))
            self.handle.flush()
            os.fsync(self.handle.fileno())  # persist BEFORE any model attempt
        except OSError as exc:
            self.blocked = True
            raise FieldBlocked("JOURNAL_PERSISTENCE_FAILURE") from exc
        self.rows.append(row)
        self.prev = digest

    def _ready(self) -> None:
        require(not self.blocked, "EVENT_ALREADY_BLOCKED")
        check_synthetic_context(self.ctx, self.raw)

    def reserve_rest(self, endpoint: str, *, reserve_approved: bool = False) -> None:
        self._ready()
        require(type(endpoint) is str and endpoint in REST_BASE,
                "REST_ENDPOINT_PAIR_OR_PARAMS_NOT_ALLOWLISTED")
        weight = REST_BASE[endpoint]
        require(self.rest_count < GET_MAX and
                self.rest_weight + weight <= GET_WEIGHT_MAX,
                "REST_ATTEMPT_OR_WEIGHT_CAP")
        if endpoint == "exchangeInfo/BTCUSDT,ETHUSDT":
            require(endpoint not in self.rest_unique,
                    "EXCHANGEINFO_REPEAT_FORBIDDEN")
        if endpoint in self.rest_unique:
            require(len(self.rest_unique) == GET_BASE and
                    self.rest_count == GET_BASE and
                    reserve_approved is True and
                    endpoint != "exchangeInfo/BTCUSDT,ETHUSDT",
                    "EXTRA_REST_NOT_APPROVED_OR_BASE_INCOMPLETE")
        self._write("REST_RESERVED_NO_SEND", endpoint, weight)
        self.rest_count += 1
        self.rest_weight += weight
        self.rest_unique.add(endpoint)

    def reserve_ws(self, stream: str, *, reserve_approved: bool = False) -> None:
        self._ready()
        require(type(stream) is str and stream in WS_BASE,
                "WS_STREAM_NOT_ALLOWLISTED")
        require(self.ws_count < WS_MAX, "WS_SUBSCRIPTION_CAP")
        if stream in self.ws_unique:
            require(self.ws_count >= len(WS_BASE) and
                    len(self.ws_unique) == len(WS_BASE) and
                    reserve_approved is True,
                    "EXTRA_WS_NOT_APPROVED_OR_BASE_INCOMPLETE")
        self._write("WS_SUB_RESERVED_NO_CONNECT", stream, 1)
        self.ws_count += 1
        self.ws_unique.add(stream)

    def register_raw(self, name: str, raw: bytes, *,
                     restored_sha256: str, owner_receipt_sha256: str) -> None:
        self._ready()
        require(type(name) is str and name.startswith("synthetic_") and
                name.endswith(".txt") and "/" not in name and "\\" not in name,
                "RAW_PATH_NOT_SYNTHETIC")
        require(type(raw) is bytes and raw.startswith(b"origin=SYNTHETIC_ONLY\n") and
                b"market_requests=0\n" in raw,
                "RAW_SOURCE_NOT_SYNTHETIC")
        require(type(restored_sha256) is str and
                type(owner_receipt_sha256) is str and
                restored_sha256 == _sha(raw) and
                owner_receipt_sha256 == _sha(raw),
                "RAW_RESTORE_OR_OWNER_RECEIPT_MISMATCH")
        require(self.raw_files + 1 <= FILE_MAX and
                self.raw_bytes + len(raw) <= RAW_MAX,
                "RAW_BYTES_OR_FILE_COUNT_CAP")
        require(not any(row["item"] == name and row["kind"] == "RAW_REGISTERED"
                        for row in self.rows),
                "RAW_NAME_DUPLICATE")
        self._write("RAW_REGISTERED", name, len(raw))
        self.raw_files += 1
        self.raw_bytes += len(raw)

    def observe_status(self, status: int) -> None:
        self._ready()
        if type(status) is not int or status == 429 or status == 418 or not 200 <= status < 300:
            self.blocked = True
            raise FieldBlocked("HTTP_RATE_LIMIT_BAN_OR_TRANSPORT_FAILURE")

    def observe_disconnect(self) -> None:
        self.blocked = True
        raise FieldBlocked("WS_DISCONNECTED_NO_AUTOMATIC_RETRY")

    def stop(self, reason: str) -> None:
        self.blocked = True
        raise FieldBlocked("STOP_" + reason)

    def close(self) -> None:
        if not self.handle.closed:
            self.handle.close()

    def snapshot(self) -> dict:
        self._ready()
        return {
            "mode": MODE, "real_field_authorized": REAL_FIELD_AUTHORIZED,
            "rest_reserved": self.rest_count, "rest_weight": self.rest_weight,
            "ws_reserved": self.ws_count, "raw_bytes": self.raw_bytes,
            "raw_files": self.raw_files, "journal_head": self.prev,
            "market_get_executed": 0, "market_ws_connected": 0,
            "permission_to_dispatch": False,
        }


def verify_journal(path: Path) -> dict:
    try:
        content = path.read_bytes()
        require(content.endswith(b"\n"), "TRUNCATED_JOURNAL")
        rows = [json.loads(line) for line in content.splitlines()]
    except (OSError, ValueError) as exc:
        raise FieldBlocked("JOURNAL_UNREADABLE_OR_INVALID") from exc
    require(bool(rows), "EMPTY_JOURNAL")
    last = GENESIS
    for index, row in enumerate(rows):
        require(type(row) is dict and set(row) ==
                {"index", "kind", "item", "amount", "prev", "hash"},
                "JOURNAL_ROW_INVALID")
        require(type(row["index"]) is int and row["index"] == index and
                row["prev"] == last, "JOURNAL_ORDER_OR_CHAIN_MISMATCH")
        values = {k: v for k, v in row.items() if k != "hash"}
        require(row["hash"] == _sha(_bytes(values)), "JOURNAL_DIGEST_MISMATCH")
        last = row["hash"]
    require(rows[0]["kind"] == "BEGIN" and
            rows[0]["item"] == "OFFLINE_NO_NETWORK_CAPABILITY",
            "JOURNAL_BEGIN_MISSING")
    return {"rows": len(rows), "head_sha256": last,
            "status": "SYNTHETIC_JOURNAL_CHAIN_SELF_CONSISTENT_ONLY"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--describe", action="store_true")
    args = p.parse_args(argv)  # --live / --arm / --network are NOT recognized
    print(json.dumps({
        "status": "NO_GO_REAL_EVENT",
        "mode": MODE,
        "market_transport_present": False,
        "field_authorized": REAL_FIELD_AUTHORIZED,
        "rest_max": GET_MAX,
        "rest_weight_max": GET_WEIGHT_MAX,
        "ws_max": WS_MAX,
        "bytes_max": RAW_MAX,
        "files_max": FILE_MAX,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
