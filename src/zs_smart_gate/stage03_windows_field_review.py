"""Offline verifier of REAL, separately captured Stage03 field packets.

Verifies capture/replay integrity, source identity, key arithmetic and causal
cutoffs. NOT an independent UTC attestation, legal opinion or source-qualified
Stage03->03A scientific acceptance. No network access.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import json

from .stage03_windows_field_capture import VERSION, digest, parse_time

def check_file(path):
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    sha = obj.pop("record_sha256", None)
    if sha != digest(obj):
        raise ValueError("RECEIPT_RECORD_SHA_MISMATCH")
    obj["record_sha256"] = sha
    if obj.get("version") != VERSION or not obj.get("completed"):
        raise ValueError("INCOMPLETE_OR_WRONG_VERSION")
    if obj.get("symbol") != "BTCUSDT":
        raise ValueError("UNEXPECTED_PAIR")
    return obj

def verify(pre_path, post_path):
    pre, post = check_file(pre_path), check_file(post_path)
    if pre["phase"] != "pre" or post["phase"] != "post":
        raise ValueError("PHASE_ORDER")
    if pre["parent_open_utc"] != post["parent_open_utc"]:
        raise ValueError("PARENT_MISMATCH")
    parent = parse_time(pre["parent_open_utc"])
    end = parent + timedelta(hours=4)
    if len(pre["requests"]) != 4 or len(post["requests"]) != 6:
        raise ValueError("REQUEST_COUNT")
    if pre.get("attempted") != 4 or post.get("attempted") != 6:
        raise ValueError("REQUEST_ATTEMPT_COUNT")
    for obj in (pre, post):
        if obj["rights_scope"] != "PRIVATE_NONCOMMERCIAL_RESEARCH":
            raise ValueError("RIGHTS_SCOPE_UNACCEPTED")
        for request in obj["requests"]:
            if request["status"] != 200 or len(request["raw_sha256"]) != 64:
                raise ValueError("RAW_RECEIPT_OR_HTTP_INVALID")
            if request["independent_utc_witness"] != "NOT_ATTESTED":
                raise ValueError("UNTRUSTED_CLOCK_ATTESTATION_IN_FILE")
            if request["duration_monotonic_ns"] < 0:
                raise ValueError("NEGATIVE_DURATION")
            if parse_time(request["received_utc_unattested"]) < parse_time(request["start_utc_unattested"]):
                raise ValueError("WALL_CLOCK_ORDER_UNSAFE")
    if any(parse_time(r["received_utc_unattested"]) >= parent for r in pre["requests"]):
        raise ValueError("PRE_MODE_RECEIVED_AFTER_PARENT")
    if any(parse_time(r["received_utc_unattested"]) <= end for r in post["requests"]):
        raise ValueError("POST_RECEIVED_BEFORE_PARENT_CLOSE")
    expected = [("exchangeInfo", None), ("klines", "4h"), ("klines", "1d"), ("klines", "1w")]
    expected_post = [("klines", "5m"), ("klines", "30m"), ("klines", "1h"),
                     ("klines", "4h"), ("bookTicker", None), ("24hr", None)]
    for obj, wanted in ((pre, expected), (post, expected_post)):
        for request, (endpoint, interval) in zip(obj["requests"], wanted):
            if not request["path"].endswith("/" + endpoint):
                raise ValueError("UNEXPECTED_ENDPOINT")
            if interval is not None and request["selected"].get("interval") != interval:
                raise ValueError("WRONG_INTERVAL")
    info = pre["requests"][0]["selected"]
    if info["status"] != "TRADING" or info["quoteAsset"] != "USDT" or (
        info["isSpotTradingAllowed"] is not True
        and not any("SPOT" in x for x in (info.get("permissionSets") or []))
    ):
        raise ValueError("SPOT_ELIGIBILITY_MISSING")
    for record in pre["requests"][1:] + post["requests"][:4]:
        selected = record["selected"]
        bars = selected["bars"]
        if not bars:
            raise ValueError("EMPTY_CLOSED_BAR_HISTORY")
        if any(int(bar["close_exclusive_ms"]) > int(parse_time(record["received_utc_unattested"]).timestamp() * 1000)
               for bar in bars):
            raise ValueError("OPEN_OR_FUTURE_CANDLE")
        if any(Decimal(bar["high"]) < max(Decimal(bar["open"]), Decimal(bar["close"]))
               or Decimal(bar["low"]) > min(Decimal(bar["open"]), Decimal(bar["close"]))
               or Decimal(bar["quote_volume"]) < 0 for bar in bars):
            raise ValueError("OHLCV_INVALID")
    # Pre-parent 4h context may not include the bar that closes at parent open.
    old_4h = pre["requests"][1]["selected"]["bars"]
    if len(old_4h) < 32 or old_4h[-1]["close_exclusive_ms"] > int(parent.timestamp() * 1000):
        raise ValueError("PRIOR_4H_MODE_HISTORY_MISSING")
    weekly = pre["requests"][3]["selected"]["bars"]
    if len(weekly) < 18:
        raise ValueError("WEEKLY_WARMUP_MISSING")
    book, ticker = post["requests"][4]["selected"], post["requests"][5]["selected"]
    bid, ask = Decimal(book["bidPrice"]), Decimal(book["askPrice"])
    volume = Decimal(ticker["quoteVolume"])
    if bid <= 0 or ask < bid or volume < 10000000:
        raise ValueError("BOOK_OR_24H_INELIGIBLE")
    spread = Decimal(20000) * (ask-bid) / (ask+bid)
    if spread > 20:
        raise ValueError("SPREAD_TOO_WIDE")
    if ticker["window"] != "ROLLING_24H" or ticker["unit"] != "USDT":
        raise ValueError("TICKER_QUOTE_WINDOW_UNVERIFIED")
    # We cannot substitute an unattested Windows wall clock for an independent
    # UTC witness, nor recover exchange publisher time from kline closeTime.
    return {"schema": "ZS03_ORIGINAL_SOURCE_OFFLINE_REVIEW_V1",
            "source": "BINANCE_SPOT_PUBLIC_REST", "symbol": "BTCUSDT",
            "pre_receipt_sha256": pre["record_sha256"],
            "post_receipt_sha256": post["record_sha256"],
            "requests_verified": 10,
            "spread_bps": str(spread),
            "quote_volume_24h_usdt": str(volume),
            "evidence": "REAL_SOURCE_SELECTED_FIELDS_WITH_UNATTESTED_LOCAL_RECEIPTS",
            "clock": "INDEPENDENT_EVENT_UTC_NOT_VERIFIED",
            "source_qualified": False,
            "stage03_e2e": "BLOCKED_CLOCK_RIGHTS_AND_TYPED_REAL_ADAPTER",
            "score": None, "signal_id": None, "publishable": False}

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--pre", required=True)
    p.add_argument("--post", required=True)
    args = p.parse_args(argv)
    try:
        out = verify(args.pre, args.post)
        print(json.dumps(out, sort_keys=True, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
        print("ZS03_REAL_SOURCE_REVIEW_BLOCKED:" + str(exc))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
