"""Genuine retained-source Stage03 -> existing 03A research contract replay.

No synthetic R2 object conversion, signal IDs, published scores, Telegram,
orders or external GET. Honest real-source functional integration verdict;
not full R2 N01-N12 source qualification or historical publisher PIT.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from .core import Candle, MarketSnapshot
from .mtf_contracts import CandleWindow, ReconciliationTolerance
from .stage03_qualification_readiness import assess_readiness
from .stage03a_contracts import Direction, Horizon
from .stage03_windows_field_review import check_file, verify, instant
from .stage03_windows_field_capture import canonical, parse_time, digest

SOURCE_ID="BINANCE:SPOT:BTCUSDT:REST_MARKETDATA_V1"
CONTRACT="ZS03_REAL_SOURCE_TO_03A_FUNCTIONAL_REPLAY_V1"

def received_time(req):
    """Use worst-case late arrival as source availability."""
    return instant(req)[1]

def asof_request(req, cutoff, name):
    if received_time(req)>=cutoff:
        raise ValueError("SOURCE_ASOF_NOT_PROVEN_"+name)

def win(rec, row):
    frame=rec["selected"]["interval"]
    open_at=datetime.fromtimestamp(int(row["open_ms"])/1000,timezone.utc)
    close=datetime.fromtimestamp(int(row["close_exclusive_ms"])/1000,timezone.utc)
    receipt=parse_time(rec["received_utc_unattested"])
    available=received_time(rec)
    return CandleWindow(
        frame,open_at,close,receipt,available,SOURCE_ID,
        Decimal(row["open"]),Decimal(row["high"]),Decimal(row["low"]),
        Decimal(row["close"]),Decimal(row["base_volume"]),
        Decimal(row["quote_volume"]))

def strict_pivot_mode(pre, parent_open):
    """Independent pre-parent 4h mode; return UNAVAILABLE rather than infer."""
    rec=pre["requests"][1]
    asof_request(rec,parent_open,"MODE_PRE_PARENT")
    bars=rec["selected"]["bars"]
    if len(bars)<32:
        return {"status":"UNAVAILABLE","reason":"MODE_32_4H_HISTORY_REQUIRED"}
    # All pivot confirmations must have occurred and been received before parent.
    highs,lows=[],[]
    for i in range(2,len(bars)-2):
        v=Decimal(bars[i]["high"])
        h=[Decimal(bars[k]["high"]) for k in range(i-2,i+3) if k!=i]
        w=Decimal(bars[i]["low"])
        l=[Decimal(bars[k]["low"]) for k in range(i-2,i+3) if k!=i]
        if v>max(h):
            highs.append((i,v))
        if w<min(l):
            lows.append((i,w))
    if len(highs)<2 or len(lows)<2:
        return {"status":"UNAVAILABLE","reason":"CONFIRMED_PIVOTS_INSUFFICIENT"}
    rising=highs[-1][1]>highs[-2][1] and lows[-1][1]>lows[-2][1]
    falling=highs[-1][1]<highs[-2][1] and lows[-1][1]<lows[-2][1]
    if rising==falling:
        return {"status":"UNAVAILABLE","reason":"PRIOR_MODE_AMBIGUOUS"}
    return {"status":"PRIOR_MODE_RESEARCH_ONLY","trend":"UP" if rising else "DOWN",
            "available_before_parent":True,
            "version":"ZS03_PRIOR_CONFIRMED_4H_PIVOT_MODE/V0_1_OPS_CANDIDATE_NO_REAL_PIT",
            "input_source_sha256":rec["raw_sha256"],
            "confirmation_indices":{"highs":[highs[-2][0],highs[-1][0]],
                                    "lows":[lows[-2][0],lows[-1][0]]}}

def run(pre_path,post_path,rights_path):
    review=verify(pre_path,post_path,rights_path)
    pre,post=check_file(pre_path),check_file(post_path)
    parent_open=parse_time(pre["parent_open_utc"])
    parent_end=parent_open+timedelta(hours=4)
    dw=post["decision_witness"]
    decision=parse_time(dw["at_local_utc_unattested"])
    earliest=parse_time(dw["earliest_utc"])
    # All inputs must be available at the original, recorded decision.
    for i,rec in enumerate(post["requests"]):
        asof_request(rec,earliest,"POST_"+str(i))
    for i,rec in enumerate(pre["requests"]):
        asof_request(rec,parent_open,"PRE_"+str(i))
    parent_rec,child_rec,core_rec=post["requests"][3],post["requests"][2],post["requests"][0]
    parent_candidates=[row for row in parent_rec["selected"]["bars"]
                       if int(row["close_exclusive_ms"])==int(parent_end.timestamp()*1000)]
    if len(parent_candidates)!=1:
        raise ValueError("EXACT_4H_PARENT_NOT_FOUND")
    parent=win(parent_rec,parent_candidates[0])
    hours=[row for row in child_rec["selected"]["bars"]
           if int(parent_open.timestamp()*1000)<=int(row["open_ms"])
           and int(row["close_exclusive_ms"])<=int(parent_end.timestamp()*1000)]
    if len(hours)!=4:
        raise ValueError("EXACT_4X1H_PARENT_CHILDREN_NOT_FOUND")
    children=tuple(win(child_rec,row) for row in hours)
    fives=[row for row in core_rec["selected"]["bars"]
           if int(row["close_exclusive_ms"])<=int(parent_end.timestamp()*1000)]
    if len(fives)<21 or int(fives[-1]["close_exclusive_ms"])!=int(parent_end.timestamp()*1000):
        raise ValueError("EXACT_21X5M_CORE_PARENT_END_MISSING")
    core=tuple(Candle(w.open_at,w.close_at,w.received_at,w.available_at,
                      w.open,w.high,w.low,w.close,w.base_volume,w.quote_volume)
               for w in (win(core_rec,row) for row in fives[-21:]))
    info=pre["requests"][0]["selected"]
    book,ticker=post["requests"][4]["selected"],post["requests"][5]["selected"]
    market=MarketSnapshot(
        "BTCUSDT","USDT",True,info["status"],
        Decimal(ticker["quoteVolume"]),Decimal(book["bidPrice"]),
        Decimal(book["askPrice"]),
        max(received_time(post["requests"][4]),received_time(post["requests"][5])))
    # Tight, fixed absolute reconciliation tolerances; no tuning to force PASS.
    tolerance=ReconciliationTolerance(Decimal("0.00000001"),
                                     Decimal("0.00000001"),Decimal("0.0001"),
                                     "BINANCE_SPOT_EXACT_PRICE_BASE_1E-8_QUOTE_1E-4_V1")
    evidence_id=hashlib.sha256((review["pre_receipt_sha256"]+
                                review["post_receipt_sha256"]).encode("ascii")).hexdigest()
    # One observed original-source Stage03 -> Stage03A functional E2E.
    outcome=assess_readiness(symbol="BTCUSDT",horizon=Horizon.SWING,
        direction=Direction.UP,parent=parent,children=children,core_5m=core,
        market=market,decision_at=decision,tolerance=tolerance,
        event_discriminator="REAL_SOURCE_RECEIPTS_SHA256:"+evidence_id)
    mode=strict_pivot_mode(pre,parent_open)
    # This 03A bridge is source-observed; R2 normalizer code still has
    # explicitly synthetic-only guards and is NOT run on falsely relabeled data.
    success=outcome["status"]=="RESEARCH_CANDIDATE"
    packet={
        "schema":CONTRACT,"source":"BINANCE_SPOT_PUBLIC_REST_BTCUSDT",
        "capture_pre_sha256":review["pre_receipt_sha256"],
        "capture_post_sha256":review["post_receipt_sha256"],
        "rights_attestation_sha256":review["rights_evidence_sha256"],
        "rights_legally_verified_by_provider":False,
        "network_utc_bound_under_1_5s":True,
        "network_clock_authenticated":False,
        "publisher_time_verified":False,
        "historic_pit_verified":False,
        "original_source_e2e_executed":True,
        "stage03_to_03a_research_functional_pass":success,
        "real_03a_status":outcome["status"],
        "real_03a_reason_codes":outcome["reason_codes"],
        "research_identity":outcome["identity"],
        "reconciliation":outcome["reconciliation"],
        "prior_mode":mode,
        "r2_n01_to_n12_real_source_qualified":False,
        "r2_live_adapter":"NOT_AUTHORIZED_SYNTHETIC_ONLY_R2_CONTRACT_UNCHANGED",
        "n03_source_qualification":"UNAVAILABLE",
        "scientific_stage03_closed":False,
        "score":None,"signal_id":None,"publishable":False,"market_requests":0,
    }
    packet["packet_sha256"]=digest(packet)
    return packet

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--pre",required=True)
    p.add_argument("--post",required=True)
    p.add_argument("--rights-attestation",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args(argv)
    try:
        result=run(a.pre,a.post,a.rights_attestation)
        target=Path(a.output)
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open("x",encoding="utf-8") as f:
            f.write(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    except (ValueError,TypeError,KeyError,ArithmeticError,FileNotFoundError,FileExistsError) as exc:
        print("ZS03_FIELD_REAL_E2E_BLOCKED:"+str(exc))
        return 2
    print("REAL_SOURCE_RESEARCH_E2E="+result["real_03a_status"])
    print("RECONCILIATION="+str(result["reconciliation"]["status"] if result["reconciliation"] else None))
    print("RESULT_SHA256="+result["packet_sha256"])
    print("RESULT_FILE="+str(target))
    print("STAGE03_CLOSED=false")
    return 0 if result["stage03_to_03a_research_functional_pass"] else 3

if __name__=="__main__":
    raise SystemExit(main())
