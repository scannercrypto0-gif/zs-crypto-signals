"""03B2 opt-in single frozen retrospective session over public Binance REST.

One fixed asset/horizon/window per invocation, at most 6 logical requests and
8 *physical* attempts incl retries. Historical re-fetch is NOT historical PIT.
Nothing writes signals, Telegram, orders or durable storage; no 03B1 changes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
import time
from typing import Callable

from .binance_live import BASE, LiveBlocked, LiveFailure, get_json, is_spot_enabled, require_dict, timestamp
from .core import MarketSnapshot, check_eligibility, decimal, utc
from .mtf_contracts import reconcile
from .scanner import MAX_HTTP_REQUESTS, SOFT_PRE_REQUEST_GUARD_SECONDS, STOP_USED_WEIGHT_1M
from .stage03a_contracts import Direction, Horizon
from .stage03b1_live import CONFIG, DURATION_MS, EXACT, parse_kline, deviations
from .stage03b2_manifest import MANIFEST, Partition, RETROSPECTIVE_EVIDENCE
from .stage03b2_research import competing_features, frozen_hash, seal_record


def run_session(*, symbol: str, horizon: Horizon, partition: Partition,
                getter: Callable = get_json,
                clock_ms: Callable[[], float] = lambda: time.time()*1000,
                monotonic: Callable[[], float] = time.perf_counter) -> dict:
    """Present-time verification of frozen historical OHLCV, not a replay decision."""
    if not isinstance(horizon, Horizon) or not isinstance(partition, Partition):
        raise ValueError("INVALID_FROZEN_SESSION_ENUMS")
    window = MANIFEST.session(symbol,horizon,partition)
    frame, child_frame, expected, duration_ms = CONFIG[horizon]
    close_ms = int(window.close_at.timestamp()*1000)
    start_ms = close_ms-duration_ms
    begun = monotonic()
    attempts: list[str] = []
    calls: list[dict] = []
    offset = None
    rtt = None
    now_stamp = datetime.now(timezone.utc).isoformat()

    def telemetry() -> dict:
        elapsed_ms=round((monotonic()-begun)*1000,2)
        return {"physical_http_attempts":len(attempts),
                "successful_calls":len(calls),
                "http_attempt_budget":MAX_HTTP_REQUESTS,
                "attempted_paths":list(attempts),
                "elapsed_ms":elapsed_ms,
                "soft_guard_s":SOFT_PRE_REQUEST_GUARD_SECONDS,
                "soft_guard_kind":"PRE_ATTEMPT_ONLY_NOT_HARD_CANCEL",
                "deadline_exceeded":elapsed_ms>SOFT_PRE_REQUEST_GUARD_SECONDS*1000,
                "clock_offset_estimate_ms":round(offset,2) if offset is not None else None,
                "clock_rtt_ms":round(rtt,2) if rtt is not None else None,
                "true_clock_uncertainty_ms":None,
                "source_publication_timestamp":None,
                "http":[{k:x.get(k) for k in
                         ("path","http_status","latency_ms","used_weight_1m")} for x in calls]}

    def before_attempt(path: str) -> None:
        if len(attempts)>=MAX_HTTP_REQUESTS:
            raise LiveBlocked("PHYSICAL_HTTP_ATTEMPT_BUDGET_EXHAUSTED")
        if monotonic()-begun>SOFT_PRE_REQUEST_GUARD_SECONDS:
            raise LiveBlocked("SOFT_PRE_REQUEST_GUARD_EXCEEDED")
        if calls and calls[-1].get("used_weight_1m") is not None and int(
            calls[-1]["used_weight_1m"])>=STOP_USED_WEIGHT_1M:
            raise LiveBlocked("EXCHANGE_USED_WEIGHT_SAFETY_STOP")
        attempts.append(path)

    def read(path: str, params: dict | None = None) -> tuple[object,dict]:
        data,meta=getter(path,params,on_attempt=before_attempt)
        if not isinstance(meta,dict) or not isinstance(meta.get("received_local_ms"),(int,float)):
            raise LiveFailure("MISSING_TRANSPORT_RECEIPT")
        calls.append(meta)
        return data,meta

    base = {
        "stage":"03B2_FROZEN_RETROSPECTIVE_RESEARCH",
        "manifest_version":MANIFEST.version,
        "study_id":MANIFEST.study_id,
        "symbol":symbol, "horizon":horizon.value, "partition":partition.value,
        "declared_liquidity_cohort":next(a.declared_cohort for a in MANIFEST.assets
                                         if a.symbol==symbol),
        "parent_close_at":window.close_at.isoformat(),
        "parent_frame":frame, "child_frame":child_frame,
        "expected_child_count":expected,
        "retrospective_assumption":RETROSPECTIVE_EVIDENCE,
        "source_id":MANIFEST.provider_source,
        "host":BASE,
        "historical_eligibility":None,
        "source_publication_at":None,
        "historical_decision_at":None,
        "score":None, "score_status":"SCORE_UNAVAILABLE",
        "trade_plan_status":"RESEARCH_ONLY","signal_id":None,
        "qualified_signal":False,"futures":False,"telegram":False,
        "forward_outcome":None,"fee_model":None,"slippage":None,
        "limits":["Historical Binance OHLCV re-fetch observed now; no contemporaneous snapshot",
                  "Actual past market eligibility and source publisher time UNKNOWN",
                  "2 frozen time windows, not independent market regimes/prediction evidence",
                  "Spot public only; per-job max 8 physical requests, no market-wide scan"],
    }
    try:
        server,sm=read("/api/v3/time")
        server=require_dict(server,("serverTime",),"TIME_SCHEMA")
        server_ms=int(server["serverTime"])
        rtt=sm["received_local_ms"]-sm["t0_local_ms"]
        if rtt<0:
            raise LiveFailure("CLOCK_RECEIPT_PRECEDES_START")
        offset=server_ms-(sm["t0_local_ms"]+sm["received_local_ms"])/2
        if close_ms>server_ms:
            raise LiveFailure("FUTURE_PARENT_WINDOW_NOT_CLOSED")
        exch,em=read("/api/v3/exchangeInfo",{"symbol":symbol})
        ticker,tm=read("/api/v3/ticker/24hr",{"symbol":symbol})
        book,bm=read("/api/v3/ticker/bookTicker",{"symbol":symbol})
        exch=require_dict(exch,("symbols",),"EXCHANGE_SCHEMA")
        infos=exch["symbols"]
        if not isinstance(infos,list) or len(infos)!=1:
            raise LiveFailure("EXACT_SPOT_IDENTITY_MISSING")
        info=require_dict(infos[0],("symbol","quoteAsset","status"),"SPOT_SCHEMA")
        ticker=require_dict(ticker,("symbol","quoteVolume"),"TICKER_SCHEMA")
        book=require_dict(book,("symbol","bidPrice","askPrice"),"BOOK_SCHEMA")
        if any(x["symbol"]!=symbol for x in (info,ticker,book)):
            raise LiveFailure("WRONG_SPOT_SYMBOL_METADATA")
        observed=timestamp(max(x["received_local_ms"] for x in (em,tm,bm))+offset)
        market=MarketSnapshot(symbol,info["quoteAsset"],is_spot_enabled(info),
                              info["status"],decimal(ticker["quoteVolume"]),
                              decimal(book["bidPrice"]),decimal(book["askPrice"]),observed)
        eligibility=check_eligibility(market,observed)
        base["current_market_observed_at"]=market.observed_at.isoformat()
        base["current_quote_volume_24h"]=str(market.quote_volume_24h)
        base["current_eligibility_reasons"]=list(eligibility)
        if eligibility:
            raise LiveFailure("CURRENT_MARKET_INELIGIBLE_" + ",".join(eligibility))

        parent_rows,pm=read("/api/v3/klines",{
            "symbol":symbol,"interval":frame,"startTime":str(start_ms),
            "endTime":str(close_ms-1),"limit":"1"})
        child_rows,cm=read("/api/v3/klines",{
            "symbol":symbol,"interval":child_frame,"startTime":str(start_ms),
            "endTime":str(close_ms-1),"limit":str(expected)})
        base["coverage"]={
            "parent_received":len(parent_rows) if isinstance(parent_rows,list) else 0,
            "children_received":len(child_rows) if isinstance(child_rows,list) else 0,
            "parent_expected":1,"children_expected":expected,
            "selected_symbols_in_job":1,"selected_horizons_in_job":1,
            "full_market_coverage":False}
        if not isinstance(parent_rows,list) or len(parent_rows)!=1 or (
            not isinstance(child_rows,list) or len(child_rows)!=expected):
            raise LiveFailure("ABSENT_OR_PARTIAL_HISTORICAL_WINDOW")
        received_parent=timestamp(pm["received_local_ms"]+offset)
        received_child=timestamp(cm["received_local_ms"]+offset)
        parent=parse_kline(parent_rows[0],frame,received_parent)
        children=[parse_kline(c,child_frame,received_child) for c in child_rows]
        if int(parent.open_at.timestamp()*1000)!=start_ms or parent.close_at!=window.close_at:
            raise LiveFailure("PARENT_OUTSIDE_FROZEN_MANIFEST_WINDOW")
        # Freeze REAL current retrieval decision, NOT historical fake decision.
        retrieved_at=max(timestamp(clock_ms()+offset),market.observed_at,
                         parent.available_at,*(c.available_at for c in children))
        rec=reconcile(parent,children,retrieved_at,tolerance=EXACT)
        base["retrieved_at"]=retrieved_at.isoformat()
        base["source_payload_sha256"]=frozen_hash({
            "parent_kline_raw":parent_rows, "child_klines_raw":child_rows,
            "symbol":symbol,"horizon":horizon.value,
            "parent_close_at":window.close_at.isoformat()})
        base["reconciliation"]=rec.as_dict()
        base["signed_parent_minus_children_deltas"]=deviations(parent,children)
        if rec.status=="PASS":
            base["features"]={
                direction.value:competing_features(parent,children,direction=direction,
                                                  decision_at=retrieved_at)
                for direction in MANIFEST.directions}
            base["status"]="OBSERVED_EXACT_RECONCILIATION"
        else:
            base["status"]="INVALID"
            base["reason"]="RECONCILIATION_INVALID"
            base["reason_codes"]=list(rec.reason_codes)
        base["measurements"]=telemetry()
        if base["measurements"]["deadline_exceeded"]:
            base["status"]="FAIL"
            base["reason"]="SOFT_GUARD_OVERRUN_IN_FLIGHT"
            base.pop("features",None)
        return seal_record(base)
    except (LiveBlocked,LiveFailure,ValueError,TypeError,OverflowError,KeyError) as exc:
        base["status"]="BLOCKED" if isinstance(exc,LiveBlocked) else "FAIL"
        base["reason"]=str(exc) if isinstance(exc,(LiveBlocked,LiveFailure)) else "INVALID_HISTORICAL_SCHEMA"
        base["measurements"]=telemetry()
        return seal_record(base)


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="03B2 single frozen historical retrieval, no Signal")
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--symbol",required=True,choices=[a.symbol for a in MANIFEST.assets])
    parser.add_argument("--horizon",required=True,choices=[h.value for h in MANIFEST.horizons])
    parser.add_argument("--partition",required=True,choices=[p.value for p in Partition])
    args=parser.parse_args(argv)
    if not args.live:
        parser.error("EXPLICIT_LIVE_OPT_IN_REQUIRED")
    out=run_session(symbol=args.symbol,horizon=Horizon(args.horizon),
                    partition=Partition(args.partition))
    print(json.dumps(out,sort_keys=True))
    return 0 if out["status"]=="OBSERVED_EXACT_RECONCILIATION" else (
        2 if out["status"]=="BLOCKED" else 1)


if __name__=="__main__":
    sys.exit(main())
