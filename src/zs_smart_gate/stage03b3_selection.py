"""One-time, opt-in, public Binance Spot/USDT universe PRESELECTION ONLY.

Publication of complete sorted eligible list + digest precedes frozen manifest.
Never fetches klines, chooses symbol based on returns or retries selection.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
import sys
import time
from typing import Callable

from .binance_live import LiveBlocked,LiveFailure,get_json,require_dict,timestamp
from .scanner import (MAX_HTTP_REQUESTS,SOFT_PRE_REQUEST_GUARD_SECONDS,
                      STOP_USED_WEIGHT_1M,build_universe)
from .stage03b2_research import frozen_hash

EXCLUDE=("BTCUSDT","ETHUSDT")


def choose_third(eligible: list[str]) -> str | None:
    """Lexicographically first eligible Spot USDT outside the fixed two."""
    if eligible!=sorted(set(eligible)) or any(
        not isinstance(s,str) or not s.endswith("USDT") for s in eligible
    ):
        raise ValueError("ELIGIBLE_UNIVERSE_NOT_SORTED_UNIQUE_SPOT")
    return next((s for s in eligible if s not in EXCLUDE),None)


def preselect_once(*,getter: Callable=get_json,
                   monotonic: Callable=time.perf_counter) -> dict:
    started=monotonic()
    attempts=[]
    calls=[]
    def attempt(path):
        if len(attempts)>=MAX_HTTP_REQUESTS:
            raise LiveBlocked("PRESELECTION_PHYSICAL_REQUEST_BUDGET")
        if monotonic()-started>SOFT_PRE_REQUEST_GUARD_SECONDS:
            raise LiveBlocked("PRESELECTION_SOFT_GUARD")
        if calls and calls[-1].get("used_weight_1m") is not None and int(
                calls[-1]["used_weight_1m"])>=STOP_USED_WEIGHT_1M:
            raise LiveBlocked("PRESELECTION_EXCHANGE_WEIGHT_GUARD")
        attempts.append(path)
    def read(path,params=None):
        data,meta=getter(path,params,on_attempt=attempt)
        if not isinstance(meta,dict) or not isinstance(meta.get("received_local_ms"),(int,float)):
            raise LiveFailure("PRESELECTION_RECEIPT_METADATA_MISSING")
        calls.append(meta)
        return data,meta
    result={"stage":"03B3_ONE_TIME_SELECTION","status":"BLOCKED",
            "selected_third":None,"eligible_sorted":[],
            "physical_attempts":0,"attempt_budget":MAX_HTTP_REQUESTS,
            "source":"BINANCE:SPOT:PUBLIC_UNIVERSE","source_publication_time":None}
    try:
        server,sm=read("/api/v3/time")
        server=require_dict(server,("serverTime",),"TIME_SCHEMA")
        rtt=sm["received_local_ms"]-sm["t0_local_ms"]
        if rtt<0:
            raise LiveFailure("LOCAL_CLOCK_RECEIPT_ORDER_INVALID")
        offset=int(server["serverTime"])-(sm["received_local_ms"]+sm["t0_local_ms"])/2
        exch,em=read("/api/v3/exchangeInfo")
        tick,tm=read("/api/v3/ticker/24hr",{"type":"MINI"})
        book,bm=read("/api/v3/ticker/bookTicker")
        observed=timestamp(max(m["received_local_ms"] for m in (em,tm,bm))+offset)
        universe=build_universe(exch,tick,book,observed)
        eligible=sorted(x.symbol for x in universe if x.status=="ELIGIBLE")
        if "BTCUSDT" not in eligible or "ETHUSDT" not in eligible:
            raise LiveFailure("REQUIRED_REFERENCE_ASSET_CURRENTLY_INELIGIBLE")
        third=choose_third(eligible)
        if third is None:
            raise LiveFailure("NO_DETERMINISTIC_ELIGIBLE_THIRD")
        result.update(status="PRESELECTED",selected_third=third,selected_at=observed.isoformat(),
                      eligible_sorted=eligible,eligible_count=len(eligible),
                      full_usdt_inventory_count=len(universe),
                      eligible_universe_sha256=frozen_hash(eligible),
                      clock_offset_estimate_ms=round(offset,2),
                      clock_rtt_ms=round(rtt,2),
                      raw_public_universe_digest=frozen_hash({
                          "exchange":exch,"tickers":tick,"book":book}),
                      limitations=[
                          "CURRENT point-in-time selection only; not historical liquidity or future validity",
                          "sorted eligible list and source digest are ephemeral CI evidence, not Stage04 storage",
                          "one selection only; no market scan or candle fetch",
                      ])
    except (LiveBlocked,LiveFailure,ValueError,TypeError,KeyError) as exc:
        result["reason"]=str(exc) if isinstance(exc,(LiveBlocked,LiveFailure)) else "UNIVERSE_SCHEMA_INVALID"
    result["physical_attempts"]=len(attempts)
    result["elapsed_ms"]=round((monotonic()-started)*1000,2)
    result["http"]=[{k:m.get(k) for k in
                     ("path","http_status","latency_ms","used_weight_1m")} for m in calls]
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description="03B3 one-time public Spot universe selection")
    p.add_argument("--live",action="store_true")
    args=p.parse_args(argv)
    if not args.live:
        p.error("PRESELECTION_EXPLICIT_LIVE_OPT_IN_REQUIRED")
    result=preselect_once()
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="PRESELECTED" else 2


if __name__=="__main__":
    sys.exit(main())
