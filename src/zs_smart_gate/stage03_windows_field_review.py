"""Offline genuine Binance Spot packet verification; no network / no synthetic promotion.

A successful packet review proves consistency of retained locally captured fields,
not provider rights, authenticated UTC or historical publisher timestamps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from .stage03_windows_field_capture import VERSION, digest, parse_time, check_rights

EXPECTED = {
    "pre": [("exchangeInfo", None), ("klines", "4h"), ("klines", "1d"),
            ("klines", "1w")],
    "post": [("klines", "5m"), ("klines", "30m"), ("klines", "1h"),
             ("klines", "4h"), ("bookTicker", None), ("24hr", None)],
}
SECONDS = {"5m":300,"30m":1800,"1h":3600,"4h":14400,"1d":86400,"1w":604800}

def check_file(path):
    raw = Path(path).read_bytes()
    if len(raw) > 700_000:
        raise ValueError("EVIDENCE_FILE_TOO_LARGE")
    obj = json.loads(raw)
    sha = obj.pop("record_sha256", None)
    if sha != digest(obj):
        raise ValueError("RECEIPT_RECORD_SHA_MISMATCH")
    obj["record_sha256"] = sha
    if obj.get("version") != VERSION or obj.get("completed") is not True:
        raise ValueError("INCOMPLETE_OR_WRONG_VERSION")
    if obj.get("symbol") != "BTCUSDT":
        raise ValueError("UNEXPECTED_PAIR")
    return obj

def instant(receipt):
    w = receipt["clock_witness"]
    if receipt["independent_utc_witness"] != "DUAL_NETWORK_NTP_UNAUTHENTICATED":
        raise ValueError("INDEPENDENT_NTP_WITNESS_MISSING")
    u = float(receipt["uncertainty_bound_s"])
    if not (math.isfinite(u) and 0 < u < 1.5):
        raise ValueError("CLOCK_BOUND_INVALID")
    for phase in ("before","after"):
        pair = w[phase]
        if (pair["authenticated"] is not False
                or [p["host"] for p in pair["probes"]]
                != ["time.cloudflare.com","time.google.com"]):
            raise ValueError("NTP_WITNESS_SOURCE_UNEXPECTED")
        if any(p["server_authentication"] != "UNAUTHENTICATED_PUBLIC_NTP"
               for p in pair["probes"]):
            raise ValueError("NTP_AUTHENTICATION_CLAIM_FORBIDDEN")
    if abs(u - (max(w["before"]["conservative_absolute_utc_error_seconds"],
                     w["after"]["conservative_absolute_utc_error_seconds"]) + .015)) > .000005:
        raise ValueError("CLOCK_BOUND_FORMULA_MISMATCH")
    t = parse_time(receipt["received_utc_unattested"])
    lower = t - timedelta(seconds=u)
    upper = t + timedelta(seconds=u)
    if abs(lower.timestamp() - w["utc_received_earliest_unix_seconds"]) > .00001:
        raise ValueError("EARLIEST_RECEIPT_TIME_UNMATCHED")
    if abs(upper.timestamp() - w["utc_received_latest_unix_seconds"]) > .00001:
        raise ValueError("LATEST_RECEIPT_TIME_UNMATCHED")
    return lower, upper

def _bars(item, decision):
    rows = item["selected"]["bars"]
    frame = item["selected"]["interval"]
    if len(rows) == 0:
        raise ValueError("NO_CLOSED_KLINES")
    length = SECONDS[frame] * 1000
    seen = set()
    for bar in rows:
        o, end = int(bar["open_ms"]), int(bar["close_exclusive_ms"])
        if (end-o != length or end > int(decision.timestamp() * 1000)
                or o in seen):
            raise ValueError("KLINE_OPEN_FUTURE_DUPLICATE_OR_BAD_DURATION")
        seen.add(o)
        v = [Decimal(bar[name]) for name in ("open","high","low","close",
                                            "base_volume","quote_volume")]
        if (any(not z.is_finite() for z in v) or v[0] <= 0 or v[3] <= 0
                or v[2] <= 0 or v[1] < max(v[0],v[3])
                or v[2] > min(v[0],v[3]) or v[4] < 0 or v[5] < 0):
            raise ValueError("BAD_OHLCV_FIELDS")
    if any(int(b["open_ms"])-int(a["open_ms"]) != length for a,b in zip(rows,rows[1:])):
        raise ValueError("KLINE_CONTEXT_GAP")
    return rows

def verify(pre_path, post_path, rights_attestation=None):
    pre, post = check_file(pre_path), check_file(post_path)
    if (pre.get("phase") != "pre" or post.get("phase") != "post"
            or pre.get("parent_open_utc") != post.get("parent_open_utc")):
        raise ValueError("PHASE_PARENT_CONFLICT")
    parent = parse_time(pre["parent_open_utc"])
    end = parent + timedelta(hours=4)
    sha = pre.get("rights_evidence_sha256")
    if (not isinstance(sha,str) or len(sha)!=64
            or sha != post.get("rights_evidence_sha256")):
        raise ValueError("RIGHTS_EVIDENCE_HASH_CONFLICT")
    if rights_attestation is not None and check_rights(rights_attestation) != sha:
        raise ValueError("RIGHTS_ATTESTATION_FILE_HASH_MISMATCH")
    if any(obj.get("rights_scope")!="PRIVATE_NONCOMMERCIAL_RESEARCH"
           or obj.get("rights_status")!="OPERATOR_ATTESTATION_NOT_INDEPENDENT_LICENSE_VERIFICATION"
           for obj in (pre,post)):
        raise ValueError("RIGHTS_SCOPE_OR_STATUS_MISMATCH")
    for obj in (pre,post):
        expected = EXPECTED[obj["phase"]]
        if (len(obj["requests"]) != len(expected)
                or obj.get("attempted") != len(expected)):
            raise ValueError("REQUEST_COUNT_OR_ATTEMPT_INVALID")
        for request, (name, frame) in zip(obj["requests"], expected):
            if (request.get("path") != "/api/v3/" + ("ticker/" + name if name in
                 ("bookTicker","24hr") else name)
                or request.get("params",{}).get("symbol")!="BTCUSDT"
                or request.get("status")!=200
                or request.get("raw_bytes",0)<=0
                or not isinstance(request.get("raw_sha256"),str)
                or len(request["raw_sha256"])!=64):
                raise ValueError("REQUEST_ALLOWLIST_OR_BODY_HASH_INVALID")
            if frame is not None and request["params"].get("interval")!=frame:
                raise ValueError("REQUEST_INTERVAL_MISMATCH")
            first,last=instant(request)
            if obj["phase"]=="pre" and last>=parent:
                raise ValueError("PRE_RECEIPT_MAY_BE_AFTER_PARENT")
            if obj["phase"]=="post" and first<=end:
                raise ValueError("POST_RECEIPT_MAY_PRECEDE_PARENT_CLOSE")
            if frame is not None:
                _bars(request,last)
    info=pre["requests"][0]["selected"]
    if (info["symbol"]!="BTCUSDT" or info["status"]!="TRADING"
            or info["quoteAsset"]!="USDT" or not
            (info.get("isSpotTradingAllowed") is True or
             any("SPOT" in x for x in (info.get("permissionSets") or [])))):
        raise ValueError("SPOT_ELIGIBILITY")
    four=_bars(pre["requests"][1],parent)
    week=_bars(pre["requests"][3],parent)
    if len(four)<32 or len(week)<18:
        raise ValueError("PRE_PARENT_MODE_OR_WEEKLY_WARMUP_MISSING")
    if int(four[-1]["close_exclusive_ms"])>int(parent.timestamp()*1000):
        raise ValueError("PRE_PARENT_4H_LOOKAHEAD")
    book,ticker=post["requests"][4]["selected"],post["requests"][5]["selected"]
    if book["symbol"]!=ticker["symbol"] or book["symbol"]!="BTCUSDT":
        raise ValueError("BOOK_TICKER_SOURCE_IDENTITY")
    if ticker["unit"]!="USDT" or ticker["window"]!="ROLLING_24H":
        raise ValueError("TICKER_VOLUME_UNIT_WINDOW")
    bid,ask,volume=(Decimal(book["bidPrice"]),Decimal(book["askPrice"]),
                    Decimal(ticker["quoteVolume"]))
    if (not all(v.is_finite() for v in (bid,ask,volume))
            or bid<=0 or ask<bid or volume<10000000):
        raise ValueError("LIQUIDITY_INVALID")
    spread=Decimal(20000)*(ask-bid)/(ask+bid)
    if spread>20:
        raise ValueError("SPREAD_INELIGIBLE")
    book_first,book_last=instant(post["requests"][4])
    tick_first,tick_last=instant(post["requests"][5])
    # No invented atomicity. Worst-case freshness at final decision boundary.
    decision=tick_last+timedelta(milliseconds=30)
    if (decision-book_first).total_seconds()>5 or (decision-tick_first).total_seconds()>60:
        raise ValueError("NONATOMIC_MARKET_SNAPSHOTS_STALE")
    return {"schema":"ZS03_ORIGINAL_SOURCE_REVIEW_V2",
            "source":"BINANCE_SPOT_PUBLIC_REST","symbol":"BTCUSDT",
            "pre_receipt_sha256":pre["record_sha256"],
            "post_receipt_sha256":post["record_sha256"],
            "rights_evidence_sha256":sha,
            "rights_state":"OPERATOR_ATTESTED_UNVERIFIED_BY_PROVIDER",
            "network_clock_bound_under_1_5_s":True,
            "network_clock_authenticated":False,
            "publisher_clock_verified":False,
            "historical_pit_verified":False,
            "requests_verified":10,
            "spread_bps":str(spread),"quote_volume_24h_usdt":str(volume),
            "decision_at_review":decision.isoformat(),
            "source_qualified":False,
            "stage03_e2e":"PENDING_TYPED_03A_REVIEW",
            "score":None,"signal_id":None,"publishable":False}

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--pre",required=True)
    p.add_argument("--post",required=True)
    p.add_argument("--rights-attestation")
    a=p.parse_args(argv)
    try:
        result=verify(a.pre,a.post,a.rights_attestation)
    except (ValueError,TypeError,KeyError,ArithmeticError,FileNotFoundError) as exc:
        print("ZS03_REAL_SOURCE_REVIEW_BLOCKED:"+str(exc))
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
