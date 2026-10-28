"""03B3 prospective, one-slot, no-loop, explicit opt-in public Spot PIT capture.

MUST run within 10 min of a DECLARED FUTURE parent close. Earlier => NOT_ATTEMPTED;
later => LATE without HTTP. No time-travel/re-fetch. Prior 03A/B1/B2 untouched.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
import sys
import time
from typing import Callable

from .binance_live import (LiveBlocked,LiveFailure,get_json,is_spot_enabled,
                           require_dict,timestamp)
from .core import MarketSnapshot,check_eligibility,decimal
from .mtf_contracts import reconcile
from .scanner import (MAX_HTTP_REQUESTS,SOFT_PRE_REQUEST_GUARD_SECONDS,
                      STOP_USED_WEIGHT_1M)
from .stage03a_contracts import Horizon
from .stage03b1_live import CONFIG,EXACT,parse_kline,deviations
from .stage03b2_research import competing_features,frozen_hash,seal_record
from .stage03b3_manifest import MANIFEST

STAGE="03B3_PROSPECTIVE_CAPTURE_RESEARCH_ONLY"


def capture_once(*,symbol: str,horizon: Horizon,slot_label: str,
                 getter: Callable=get_json,
                 local_ms: Callable[[],float]=lambda:time.time()*1000,
                 monotonic: Callable[[],float]=time.perf_counter) -> dict:
    slot=MANIFEST.slot(symbol,horizon,slot_label)
    parent_frame,child_frame,n,span_ms=CONFIG[horizon]
    close_ms=int(slot.close_at.timestamp()*1000)
    stop_ms=int(MANIFEST.stop_at.timestamp()*1000)
    limit_ms=close_ms+MANIFEST.receipt_grace_seconds*1000
    begun=monotonic()
    attempts=[]
    calls=[]
    offset=None
    rtt=None
    record={
        "stage":STAGE,"study_id":MANIFEST.study_id,
        "symbol":symbol,"horizon":horizon.value,"slot":slot.label,
        "parent_frame":parent_frame,"child_frame":child_frame,
        "parent_close_at":slot.close_at.isoformat(),
        "capture_start_at":MANIFEST.start_at.isoformat(),
        "study_stop_at":MANIFEST.stop_at.isoformat(),
        "source_id":MANIFEST.source,"source_publication_at":None,
        "clock_true_uncertainty_ms":None,
        "signal_id":None,"score":None,"score_status":"SCORE_UNAVAILABLE",
        "trade_plan_status":"RESEARCH_ONLY","forward_outcome":None,
        "qualified_signal":False,"historical_eligibility":None,
        "original_http_wire_bytes_available":False,
        "normalized_source_bytes_note":"Original Binance numeric strings retained from parsed JSON; canonical UTF-8 JSON snapshot is not literal HTTP wire bytes",
        "retries_after_study_close":False,
    }

    def telemetry():
        elapsed=(monotonic()-begun)*1000
        return {"physical_http_attempts":len(attempts),
                "http_attempt_budget":MAX_HTTP_REQUESTS,
                "total_study_slot_attempt_ceiling":MANIFEST.total_slot_attempt_ceiling,
                "separate_preselection_attempt_ceiling":MANIFEST.preselection_attempt_ceiling,
                "logical_calls_succeeded":len(calls),
                "elapsed_ms":round(elapsed,2),
                "deadline_exceeded":elapsed>SOFT_PRE_REQUEST_GUARD_SECONDS*1000,
                "soft_guard_kind":"PRE_ATTEMPT_ONLY_NOT_INFLIGHT_CANCEL",
                "attempt_paths":list(attempts),
                "clock_rtt_ms":round(rtt,2) if rtt is not None else None,
                "clock_offset_estimate_ms":round(offset,2) if offset is not None else None,
                "true_clock_uncertainty_ms":None,
                "source_publication_time":None,
                "http":[{k:m.get(k) for k in
                         ("path","http_status","latency_ms","used_weight_1m",
                          "t0_local_ms","received_local_ms")} for m in calls]}

    def done(status,reason):
        record.update(status=status,reason=reason,telemetry=telemetry())
        record.pop("features",None)
        return seal_record(record)

    # Local gate has NO side effects, protecting finite calls even when the
    # investigator accidentally dispatches early/late. Server clock is checked
    # once the local precondition is satisfied.
    now=local_ms()
    if now<close_ms:
        return done("NOT_ATTEMPTED","PARENT_NOT_YET_CLOSED_NO_HTTP")
    if now>min(stop_ms,limit_ms):
        return done("LATE","OUTSIDE_PREDECLARED_RECEIPT_WINDOW_NO_HTTP")

    def attempt(path):
        if len(attempts)>=MAX_HTTP_REQUESTS:
            raise LiveBlocked("PHYSICAL_ATTEMPT_BUDGET_EXHAUSTED")
        if monotonic()-begun>SOFT_PRE_REQUEST_GUARD_SECONDS:
            raise LiveBlocked("SOFT_PRE_REQUEST_GUARD_EXCEEDED")
        if calls and calls[-1].get("used_weight_1m") is not None and int(
                calls[-1]["used_weight_1m"])>=STOP_USED_WEIGHT_1M:
            raise LiveBlocked("EXCHANGE_WEIGHT_GUARD")
        # Check the observed UTC client time at every send, never retry after
        # the fixed 600s grace deadline or the finite 24h study.
        request_ms=local_ms()
        if request_ms>min(stop_ms,limit_ms):
            raise LiveBlocked("CAPTURE_WINDOW_EXPIRED_BEFORE_HTTP_ATTEMPT")
        attempts.append(path)

    def read(path,params=None):
        data,meta=getter(path,params,on_attempt=attempt)
        if not isinstance(meta,dict) or not isinstance(meta.get("received_local_ms"),(int,float)):
            raise LiveFailure("SOURCE_HTTP_RECEIPT_MISSING")
        calls.append(meta)
        return data,meta

    try:
        server,sm=read("/api/v3/time")
        server=require_dict(server,("serverTime",),"TIME_SCHEMA")
        server_ms=int(server["serverTime"])
        rtt=sm["received_local_ms"]-sm["t0_local_ms"]
        if rtt<0:
            raise LiveFailure("BACKWARDS_LOCAL_CLOCK")
        offset=server_ms-(sm["t0_local_ms"]+sm["received_local_ms"])/2
        if server_ms<close_ms:
            return done("NOT_ATTEMPTED","EXCHANGE_PARENT_NOT_YET_CLOSED")
        if server_ms>min(stop_ms,limit_ms):
            return done("LATE","EXCHANGE_TIME_AFTER_PREDECLARED_GRACE")
        exch,xm=read("/api/v3/exchangeInfo",{"symbol":symbol})
        tick,tm=read("/api/v3/ticker/24hr",{"symbol":symbol})
        book,bm=read("/api/v3/ticker/bookTicker",{"symbol":symbol})
        exch=require_dict(exch,("symbols",),"EXCHANGE_SCHEMA")
        if not isinstance(exch["symbols"],list) or len(exch["symbols"])!=1:
            raise LiveFailure("EXACT_SPOT_SYMBOL_NOT_FOUND")
        info=require_dict(exch["symbols"][0],("symbol","quoteAsset","status"),
                          "SPOT_SCHEMA")
        tick=require_dict(tick,("symbol","quoteVolume"),"TICKER_SCHEMA")
        book=require_dict(book,("symbol","bidPrice","askPrice"),"BOOK_SCHEMA")
        if any(x["symbol"]!=symbol for x in (info,tick,book)):
            raise LiveFailure("SPOT_IDENTITY_MISMATCH")
        observed=timestamp(max(x["received_local_ms"] for x in (xm,tm,bm))+offset)
        market=MarketSnapshot(symbol,info["quoteAsset"],is_spot_enabled(info),
                              info["status"],decimal(tick["quoteVolume"]),
                              decimal(book["bidPrice"]),decimal(book["askPrice"]),
                              observed)
        record["market_observed_at"]=market.observed_at.isoformat()
        record["market_quote_volume_24h"]=str(market.quote_volume_24h)
        eligibility=check_eligibility(market,market.observed_at)
        record["market_eligibility_reasons"]=list(eligibility)
        if eligibility:
            return done("INELIGIBLE","CURRENT_PIT_MARKET_INELIGIBLE_"+",".join(eligibility))
        start_ms=close_ms-span_ms
        params={"symbol":symbol,"interval":parent_frame,
                "startTime":str(start_ms),"endTime":str(close_ms-1),"limit":"1"}
        p_rows,pm=read("/api/v3/klines",params)
        c_rows,cm=read("/api/v3/klines",{
            "symbol":symbol,"interval":child_frame,
            "startTime":str(start_ms),"endTime":str(close_ms-1),"limit":str(n)})
        record["coverage"]={"expected_parent":1,"expected_children":n,
                            "parent_fetched":len(p_rows) if isinstance(p_rows,list) else 0,
                            "children_fetched":len(c_rows) if isinstance(c_rows,list) else 0}
        if (not isinstance(p_rows,list) or len(p_rows)!=1 or
            not isinstance(c_rows,list) or len(c_rows)!=n):
            raise LiveFailure("MISSING_OR_PARTIAL_OR_DUPLICATE_KLINE_BATCH")
        parent=parse_kline(p_rows[0],parent_frame,
                           timestamp(pm["received_local_ms"]+offset))
        children=[parse_kline(c,child_frame,
                             timestamp(cm["received_local_ms"]+offset)) for c in c_rows]
        if int(parent.open_at.timestamp()*1000)!=start_ms:
            raise LiveFailure("PARENT_NOT_IN_FROZEN_WINDOW")
        decision=max(timestamp(local_ms()+offset),market.observed_at,
                     parent.available_at,*(c.available_at for c in children))
        record["decision_at"]=decision.isoformat()
        record["receipt_at"]={
            "market":market.observed_at.isoformat(),
            "parent":parent.received_at.isoformat(),
            "child_batch":children[0].received_at.isoformat()}
        # Conservative timing margin: clock RTT is observable, but real clock
        # error and publisher availability remain fundamentally UNKNOWN.
        # This validates *actual observed receipts*, not future knowledge.
        earliest=min(market.observed_at,parent.received_at,
                     *(c.received_at for c in children))
        if earliest<slot.close_at:
            return done("FAILED","EARLY_OR_UNCLOSED_RECEIPT_AT_SOURCE")
        if (decision.timestamp()*1000 > limit_ms or
            decision.timestamp()*1000 > stop_ms or
            local_ms()>min(stop_ms,limit_ms)):
            return done("LATE","DATA_ARRIVED_AFTER_PREDECLARED_CAPTURE_GRACE")
        reconciliation=reconcile(parent,children,decision,tolerance=EXACT)
        record["reconciliation"]=reconciliation.as_dict()
        record["deltas"]=deviations(parent,children)
        source={"symbol":symbol,"parent":p_rows,"children":c_rows,
                "close_exclusive":slot.close_at.isoformat(),
                "http_receipt_estimates":record["receipt_at"]}
        record["source_parsed_original_numeric_strings"]=source
        record["source_canonical_utf8_size"]=len(json.dumps(
            source,sort_keys=True,ensure_ascii=True,separators=(",",":")).encode("utf-8"))
        record["source_payload_sha256"]=frozen_hash(source)
        if reconciliation.status!="PASS":
            return done("FAILED","PARENT_CHILD_RECONCILIATION_"+",".join(reconciliation.reason_codes))
        record["features"]={d.value:competing_features(
            parent,children,direction=d,decision_at=decision)
            for d in MANIFEST.directions}
        record.update(status="OBSERVED_PIT",reason=None,telemetry=telemetry())
        if record["telemetry"]["deadline_exceeded"]:
            return done("FAILED","SOFT_REQUEST_GUARD_OVERRUN_INFLIGHT")
        return seal_record(record)
    except (LiveBlocked,LiveFailure,ValueError,TypeError,OverflowError,KeyError) as exc:
        reason=str(exc) if isinstance(exc,(LiveBlocked,LiveFailure)) else "SOURCE_SCHEMA_INVALID"
        if isinstance(exc,LiveBlocked) and "WINDOW_EXPIRED" in reason:
            return done("LATE",reason)
        return done("FAILED",reason)


def main(argv=None):
    p=argparse.ArgumentParser(description="03B3 explicit single frozen prospective PIT capture")
    p.add_argument("--live",action="store_true")
    p.add_argument("--symbol",required=True,choices=MANIFEST.assets)
    p.add_argument("--horizon",required=True,choices=[x.value for x in Horizon])
    p.add_argument("--slot",required=True,choices=[s.label for s in MANIFEST.slots])
    args=p.parse_args(argv)
    if not args.live:
        p.error("EXPLICIT_LIVE_OPT_IN_REQUIRED")
    data=capture_once(symbol=args.symbol,horizon=Horizon(args.horizon),
                      slot_label=args.slot)
    print(json.dumps(data,sort_keys=True))
    # NOT_ATTEMPTED and LATE are honest study states, not transport passes.
    return 0 if data["status"]=="OBSERVED_PIT" else 2


if __name__=="__main__":
    sys.exit(main())
