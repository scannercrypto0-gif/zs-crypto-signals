"""Bounded, manually invoked real Binance Spot Stage03 evidence collector.

No credentials, orders, loops, retries, scheduler, Telegram or score publishing.
Two strictly separated invocations: PRE before parent open, POST after parent
close. Never labels a Windows wall clock as an independently attested clock.
Raw HTTP payloads are processed in memory; project evidence stores selected
research fields plus SHA256, not a verbatim exchange payload.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .stage03_field_clock import witness_pair, bracketed_receive

BASE = "https://data-api.binance.vision"
SYMBOL = "BTCUSDT"
VERSION = "ZS03_WINDOWS_FIELD_CAPTURE_V2"
PHASES = {
    "pre": [
        ("/api/v3/exchangeInfo", {"symbol": SYMBOL}),
        ("/api/v3/klines", {"symbol": SYMBOL, "interval": "4h", "limit": "34", "timeZone": "0"}),
        ("/api/v3/klines", {"symbol": SYMBOL, "interval": "1d", "limit": "21", "timeZone": "0"}),
        ("/api/v3/klines", {"symbol": SYMBOL, "interval": "1w", "limit": "20", "timeZone": "0"}),
    ],
    "post": [
        ("/api/v3/klines", {"symbol": SYMBOL, "interval": "5m", "limit": "80", "timeZone": "0"}),
        ("/api/v3/klines", {"symbol": SYMBOL, "interval": "30m", "limit": "22", "timeZone": "0"}),
        ("/api/v3/klines", {"symbol": SYMBOL, "interval": "1h", "limit": "22", "timeZone": "0"}),
        ("/api/v3/klines", {"symbol": SYMBOL, "interval": "4h", "limit": "34", "timeZone": "0"}),
        ("/api/v3/ticker/bookTicker", {"symbol": SYMBOL}),
        ("/api/v3/ticker/24hr", {"symbol": SYMBOL, "type": "FULL"}),
    ],
}
INTERVAL_MS = {"5m": 300000, "30m": 1800000, "1h": 3600000,
               "4h": 14400000, "1d": 86400000, "1w": 604800000}

def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()

def utcnow():
    return datetime.now(timezone.utc)

def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")

def parse_time(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError("UTC_TIMESTAMP_REQUIRED")
    return dt.astimezone(timezone.utc)

def sanitize_payload(path, params, data, receipt_utc_ms):
    if path == "/api/v3/exchangeInfo":
        rows = data.get("symbols") if isinstance(data, dict) else None
        if not isinstance(rows, list) or len(rows) != 1:
            raise ValueError("EXCHANGE_INFO_SCHEMA")
        e = rows[0]
        if e.get("symbol") != SYMBOL or e.get("quoteAsset") != "USDT":
            raise ValueError("WRONG_SYMBOL_OR_QUOTE")
        return {"symbol": e["symbol"], "status": e.get("status"),
                "quoteAsset": e["quoteAsset"], "isSpotTradingAllowed": e.get("isSpotTradingAllowed"),
                "permissionSets": e.get("permissionSets")}
    if path == "/api/v3/klines":
        interval = params["interval"]
        if not isinstance(data, list) or len(data) > int(params["limit"]):
            raise ValueError("KLINES_SCHEMA")
        output = []
        for bar in data:
            if not isinstance(bar, list) or len(bar) < 11:
                raise ValueError("KLINE_FIELDS")
            opening, inclusive_close = int(bar[0]), int(bar[6])
            if opening + INTERVAL_MS[interval] - 1 != inclusive_close:
                raise ValueError("KLINE_CLOSE_SEMANTICS")
            if opening + INTERVAL_MS[interval] > receipt_utc_ms:
                continue  # forming bars are never retained or used
            output.append({"open_ms": opening, "close_exclusive_ms": opening + INTERVAL_MS[interval],
                           "open": str(bar[1]), "high": str(bar[2]), "low": str(bar[3]),
                           "close": str(bar[4]), "base_volume": str(bar[5]),
                           "quote_volume": str(bar[7])})
        if any(y["open_ms"] - x["open_ms"] != INTERVAL_MS[interval]
               for x, y in zip(output, output[1:])):
            raise ValueError("KLINE_NONCONTIGUOUS")
        return {"symbol": SYMBOL, "interval": interval, "bars": output,
                "forming_excluded": len(data) - len(output)}
    if not isinstance(data, dict) or data.get("symbol") != SYMBOL:
        raise ValueError("TICKER_SYMBOL")
    if path.endswith("/bookTicker"):
        return {"symbol": SYMBOL, "bidPrice": str(data["bidPrice"]),
                "askPrice": str(data["askPrice"]), "publisher_time": None}
    if path.endswith("/24hr"):
        return {"symbol": SYMBOL, "quoteVolume": str(data["quoteVolume"]),
                "window": "ROLLING_24H", "unit": "USDT",
                "openTime": int(data["openTime"]), "closeTime": int(data["closeTime"]),
                "publisher_time": None}
    raise ValueError("PATH_NOT_ALLOWED")

def check_rights(path: str, *, require_fresh: bool = True) -> str:
    """Operator attestation, never automated proof of an external data license."""
    raw = Path(path).read_bytes()
    if len(raw) > 4096:
        raise ValueError("RIGHTS_ATTESTATION_TOO_LARGE")
    obj = json.loads(raw)
    required = {
        "schema": "ZS03_RIGHTS_ATTESTATION_V1",
        "data_host": "data-api.binance.vision",
        "scope": "PRIVATE_NONCOMMERCIAL_RESEARCH",
        "redistribution": False,
        "commercial_use": False,
        "operator_reviewed_terms": True,
    }
    if not isinstance(obj, dict) or any(obj.get(k) != v for k,v in required.items()):
        raise ValueError("RIGHTS_ATTESTATION_MISSING_OR_NOT_AFFIRMATIVE")
    checked = parse_time(obj["reviewed_at_utc"])
    age = (utcnow() - checked).total_seconds()
    if age < 0 or (require_fresh and age > 86400):
        raise ValueError("RIGHTS_REVIEW_STALE_OR_FUTURE")
    if obj.get("terms_url") != "https://www.binance.com/en/about-legal/terms":
        raise ValueError("RIGHTS_TERMS_REFERENCE_REQUIRED")
    return hashlib.sha256(raw).hexdigest()


def acquire(path, params):
    url = BASE + path + "?" + urlencode(params)
    before_clock = witness_pair()
    started_wall = utcnow()
    started_mono = time.monotonic_ns()
    req = Request(url, headers={"Accept": "application/json",
                  "User-Agent": "ZS03-bounded-field-research/1"})
    try:
        # urlopen here is one single physical GET, with no retry.
        with urlopen(req, timeout=8) as res:
            if res.status != 200:
                raise RuntimeError("NON_200_RESPONSE")
            raw = res.read(2_000_001)
            status = res.status
            weight = res.headers.get("X-MBX-USED-WEIGHT-1M")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("NETWORK_OR_PROVIDER_REJECTED:" + type(exc).__name__) from exc
    finished_mono = time.monotonic_ns()
    finished_wall = utcnow()
    if len(raw) > 2_000_000:
        raise RuntimeError("OVERSIZED_RESPONSE")
    after_clock = witness_pair()
    bound = bracketed_receive(
        before_clock, after_clock, start_wall=started_wall.timestamp(),
        received_wall=finished_wall.timestamp(),
        request_duration_s=(finished_mono - started_mono)/1e9)
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise RuntimeError("INVALID_JSON") from exc
    return {
        "path": path, "params": params, "url": url, "status": status,
        "raw_sha256": hashlib.sha256(raw).hexdigest(), "raw_bytes": len(raw),
        "start_utc_unattested": iso(started_wall),
        "received_utc_unattested": iso(finished_wall),
        "duration_monotonic_ns": finished_mono - started_mono,
        "publisher_time": "UNKNOWN_UNLESS_PAYLOAD_HAS_EXPLICIT_PUBLISH_TIME",
        "independent_utc_witness": "DUAL_NETWORK_NTP_UNAUTHENTICATED",
        "uncertainty_bound_s": bound["utc_error_bound_seconds"],
        "clock_witness": bound,
        "request_weight_1m": weight if weight and weight.isdecimal() else None,
        "selected": sanitize_payload(path, params, payload,
                                      int(bound["utc_received_earliest_unix_seconds"] * 1000)),
    }

def run(args):
    rights_sha = check_rights(args.rights_attestation)
    witness_pair()  # no market GET when clock preflight fails
    parent = parse_time(args.parent_open_utc)
    if parent.minute or parent.second or parent.microsecond or parent.hour % 4:
        raise ValueError("PARENT_MUST_START_AT_00_04_08_12_16_20_UTC")
    now = utcnow()
    end = parent + timedelta(hours=4)
    if args.phase == "pre":
        if not (parent - timedelta(minutes=20) <= now < parent - timedelta(seconds=10)):
            raise ValueError("PRE_PHASE_MUST_RUN_20MIN_TO_10S_BEFORE_PARENT")
    else:
        if not (end + timedelta(seconds=2) <= now < end + timedelta(minutes=10)):
            raise ValueError("POST_PHASE_MUST_RUN_2S_TO_10MIN_AFTER_PARENT_END")
    if parent.weekday() == 6 and parent.hour == 20:
        raise ValueError("WEEKLY_BOUNDARY_RISK")
    if parent.hour == 20:
        raise ValueError("DAILY_BOUNDARY_RISK")
    evidence_dir = Path(args.evidence_dir).resolve()
    if evidence_dir.exists() and evidence_dir.is_symlink():
        raise ValueError("SYMLINK_OUTPUT_REJECTED")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    phase_filename = ("zs03-" + parent.strftime("%Y%m%dT%H%MZ") + "-" +
                      args.phase + ".json")
    target = evidence_dir / phase_filename
    other = evidence_dir / phase_filename.replace("-" + args.phase + ".json",
                                                   "-" + ("pre" if args.phase == "post" else "post") + ".json")
    if args.phase == "post":
        if not other.is_file():
            raise ValueError("MISSING_PRE_PHASE_EVIDENCE")
        with other.open("rb") as f:
            pre = json.load(f)
        if (pre.get("version") != VERSION or pre.get("phase") != "pre"
                or pre.get("parent_open_utc") != iso(parent)
                or pre.get("record_sha256") != digest({k: v for k, v in pre.items()
                                                       if k != "record_sha256"})
                or len(pre.get("requests", [])) != 4
                or pre.get("rights_evidence_sha256") != rights_sha
                or pre.get("completed") is not True):
            raise ValueError("PRE_PHASE_INTEGRITY_OR_SCOPE_INVALID")
    # Exclusive creation BEFORE any market request avoids accidental replay.
    with target.open("x", encoding="utf-8") as f:
        record = {"version": VERSION, "phase": args.phase, "parent_open_utc": iso(parent),
                  "parent_end_utc": iso(end), "symbol": SYMBOL, "requested_by": "MANUAL_OWNER",
                  "rights_scope": args.rights_scope,
                  "rights_evidence_sha256": rights_sha,
                  "rights_status": "OPERATOR_ATTESTATION_NOT_INDEPENDENT_LICENSE_VERIFICATION",
                  "retention": "PRIVATE_LOCAL_SELECTED_FIELDS_ONLY",
                  "source_status": "REAL_OBSERVED_NOT_PIT_ATTESTED",
                  "scientific_qualification": "BLOCKED_PENDING_INDEPENDENT_CLOCK_RIGHTS_AND_E2E",
                  "requests": [], "attempted": 0, "completed": False}
        def persist():
            record["record_sha256"] = digest({k: v for k, v in record.items() if k != "record_sha256"})
            f.seek(0)
            f.write(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
            f.truncate()
            f.flush()
            os.fsync(f.fileno())
        persist()
        for path, params in PHASES[args.phase]:
            record["attempted"] += 1
            persist()  # record attempt before network; never silently retry
            try:
                entry = acquire(path, params)
                u = timedelta(seconds=float(entry["uncertainty_bound_s"]))
                rtime = parse_time(entry["received_utc_unattested"])
                if args.phase == "pre" and rtime + u >= parent:
                    raise ValueError("PRE_RECEIPT_UNCERTAINTY_OVERLAPS_PARENT")
                if args.phase == "post" and rtime - u <= end:
                    raise ValueError("POST_RECEIPT_UNCERTAINTY_OVERLAPS_PARENT_CLOSE")
                record["requests"].append(entry)
                persist()
            except Exception as exc:
                record["failure_code"] = type(exc).__name__ + ":" + str(exc)[:120]
                persist()
                raise
        if args.phase == "post":
            # A real decision-time checkpoint, NOT a later invented replay timestamp.
            # The preceding requests may be rejected if too stale at this instant.
            time.sleep(0.6)
            last_clock = witness_pair()
            decision = utcnow()
            u = float(last_clock["conservative_absolute_utc_error_seconds"])
            if not 0 < u < 1.5:
                raise ValueError("DECISION_CLOCK_UNCERTAINTY_INVALID")
            lo = decision - timedelta(seconds=u)
            hi = decision + timedelta(seconds=u)
            if any(parse_time(x["received_utc_unattested"]) +
                   timedelta(seconds=float(x["uncertainty_bound_s"])) >= lo
                   for x in record["requests"]):
                raise ValueError("EVIDENCE_NOT_AVAILABLE_BEFORE_DECISION")
            # Book and ticker are separate, potentially non-atomic snapshots.
            book = record["requests"][4]
            ticker = record["requests"][5]
            if ((hi - (parse_time(book["received_utc_unattested"]) -
                       timedelta(seconds=float(book["uncertainty_bound_s"])))).total_seconds()>5
                or (hi - (parse_time(ticker["received_utc_unattested"]) -
                          timedelta(seconds=float(ticker["uncertainty_bound_s"])))).total_seconds()>60):
                raise ValueError("MARKET_SOURCE_EXPIRED_BEFORE_DECISION")
            record["decision_witness"] = {
                "at_local_utc_unattested": iso(decision),
                "earliest_utc": iso(lo),
                "latest_utc": iso(hi),
                "independent_utc": last_clock,
                "publisher_clock_verified": False,
            }
        record["completed"] = True
        persist()
    return target, record["record_sha256"]

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase", required=True, choices=("pre", "post"))
    p.add_argument("--parent-open-utc", required=True,
                   help="UTC ISO time at next 4h boundary, e.g. 2026-11-08T08:00:00Z")
    p.add_argument("--evidence-dir", required=True)
    p.add_argument("--rights-scope", required=True, choices=("PRIVATE_NONCOMMERCIAL_RESEARCH",),
                   help="Operator must independently verify applicable terms; no redistribution")
    p.add_argument("--rights-attestation", required=True,
                   help="Local terms-use attestation. Does not grant a third-party license")
    p.add_argument("--manual-authorized", action="store_true")
    args = p.parse_args(argv)
    if not args.manual_authorized:
        p.error("EXPLICIT_MANUAL_AUTHORIZATION_FLAG_REQUIRED")
    try:
        path, sha = run(args)
    except Exception as exc:
        print("ZS03_FIELD_BLOCKED: " + str(exc), file=sys.stderr)
        return 2
    print("EVIDENCE_FILE=" + str(path))
    print("RECORD_SHA256=" + sha)
    print("SCIENTIFIC_STATUS=BLOCKED_PENDING_INDEPENDENT_CLOCK_RIGHTS_AND_REAL_E2E")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
