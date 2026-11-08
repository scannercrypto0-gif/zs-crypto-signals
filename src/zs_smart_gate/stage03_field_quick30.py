"""ZS03 emergency shorter prospective 30m research cycle using an EXISTING real PRE.

This is a new separate, manual, research-only path inside PR39. Reuses the
read-only 4h PRE packet collected before 08:00Z as a pre-parent source
receipt for 08:00–08:30Z; does not modify old 4h event or allow replay.
Only FOUR extra allowlisted original Binance Spot GETs at 30m CLOSE.
No orders, scheduler, keys, Telegram, synthetic source substitution,
scientific promotion, or future/PIT retroactive evidence construction.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from .core import Candle, MarketSnapshot
from .mtf_contracts import ReconciliationTolerance
from .stage03a_contracts import Direction, Horizon
from .stage03_qualification_readiness import assess_readiness
from .stage03_field_clock import witness_pair
from .stage03_windows_field_capture import (
    PHASES, SYMBOL, VERSION as PRE_VERSION, acquire, check_rights, digest,
    iso, parse_time, utcnow,
)
from .stage03_windows_field_review import (
    check_file as check_existing_pre, instant, _bars,
)
from .stage03_field_real_e2e import win, strict_pivot_mode

VERSION = "ZS03_QUICK30_PROSPECTIVE_RESEARCH_V1"
ALLOWED = (
    PHASES["post"][0],  # 5m candles, 80 bars
    PHASES["post"][1],  # 30m candles, 22 bars
    PHASES["post"][4],  # bookTicker
    PHASES["post"][5],  # rolling 24hr ticker
)

def paths(folder: Path, parent: datetime) -> tuple[Path, Path, Path]:
    root = "zs03-" + parent.strftime("%Y%m%dT%H%MZ")
    return (folder / (root + "-pre.json"),
            folder / (root + "-quick30-post.json"),
            folder / (root + "-quick30-e2e.json"))

def validate_open(text: str) -> datetime:
    parent = parse_time(text)
    if parent.minute or parent.second or parent.microsecond or parent.hour not in (0,4,8,12,16):
        raise ValueError("QUICK30_PARENT_MUST_BE_APPROVED_4H_UTC_BOUNDARY")
    return parent

def precheck(path: Path, parent: datetime, rights_path: Path, *, fresh: bool) -> dict:
    # Verify the actual PRE receipt and every conservative received-time upper bound.
    pre = check_existing_pre(path)
    sha = check_rights(str(rights_path), require_fresh=fresh)
    if (pre["phase"] != "pre" or pre["version"] != PRE_VERSION
            or pre["symbol"] != SYMBOL or pre["parent_open_utc"] != iso(parent)
            or pre.get("attempted") != 4 or len(pre["requests"]) != 4
            or pre.get("rights_evidence_sha256") != sha
            or pre.get("rights_scope") != "PRIVATE_NONCOMMERCIAL_RESEARCH"
            or pre.get("rights_status") !=
               "OPERATOR_ATTESTATION_NOT_INDEPENDENT_LICENSE_VERIFICATION"):
        raise ValueError("ORIGINAL_PRE_SCOPE_RIGHTS_OR_PARENT_UNVERIFIED")
    for entry, (endpoint, params) in zip(pre["requests"], PHASES["pre"]):
        if (entry.get("path") != endpoint or entry.get("params") != params
                or entry.get("status") != 200
                or not isinstance(entry.get("raw_sha256"),str)
                or len(entry["raw_sha256"]) != 64
                or instant(entry)[1] >= parent):
            raise ValueError("ORIGINAL_PRE_SOURCE_CLOCK_OR_REQUEST_INVALID")
    info = pre["requests"][0]["selected"]
    if (info["symbol"] != SYMBOL or info["quoteAsset"] != "USDT"
            or info["status"] != "TRADING" or not
            (info.get("isSpotTradingAllowed") is True or
             any("SPOT" in x for x in (info.get("permissionSets") or [])))):
        raise ValueError("ORIGINAL_PRE_SPOT_NOT_ELIGIBLE")
    for item in pre["requests"][1:]:
        _bars(item, parent)
    if (len(pre["requests"][1]["selected"]["bars"]) < 32
            or len(pre["requests"][3]["selected"]["bars"]) < 18):
        raise ValueError("ORIGINAL_PRE_4H_MODE_OR_18W_CONTEXT_MISSING")
    return pre

def inspect_decision(post: dict, quick_close: datetime) -> datetime:
    dw = post.get("decision_witness")
    if (not isinstance(dw,dict) or dw.get("publisher_clock_verified") is not False
            or dw["independent_utc"].get("authenticated") is not False):
        raise ValueError("REAL_DECISION_CLOCK_WITNESS_MISSING")
    u = float(dw["independent_utc"]["conservative_absolute_utc_error_seconds"])
    decision = parse_time(dw["at_local_utc_unattested"])
    earliest, latest = parse_time(dw["earliest_utc"]),parse_time(dw["latest_utc"])
    if not 0 < u < 1.5 or abs((decision-earliest).total_seconds()-u)>0.00001 or (
            abs((latest-decision).total_seconds()-u)>0.00001):
        raise ValueError("REAL_DECISION_CLOCK_INTERVAL_INVALID")
    if earliest <= quick_close:
        raise ValueError("DECISION_COULD_PRECEDE_30M_CLOSE")
    # Worst-case original receipt availability against earliest actual decision.
    if max(instant(e)[1] for e in post["requests"]) >= earliest:
        raise ValueError("ORIGINAL_SOURCE_NOT_AVAILABLE_AT_DECISION")
    book, ticker = post["requests"][2:4]
    if ((latest - instant(book)[0]).total_seconds() > 5 or
            (latest - instant(ticker)[0]).total_seconds() > 60):
        raise ValueError("NONATOMIC_MARKET_FRESHNESS_UNPROVEN")
    return decision

def save_record(f, record):
    record["record_sha256"] = digest({k:v for k,v in record.items() if k!="record_sha256"})
    f.seek(0)
    f.write(json.dumps(record,sort_keys=True,indent=2,ensure_ascii=False))
    f.truncate()
    f.flush()
    os.fsync(f.fileno())

def capture(pre_path: Path, target: Path, parent: datetime, rights_path: Path):
    if target.exists():
        raise ValueError("QUICK30_ATTEMPT_EXISTS_NO_RETRY")
    pre = precheck(pre_path,parent,rights_path,fresh=True)
    end = parent + timedelta(minutes=30)
    now = utcnow()
    if not (end+timedelta(seconds=2)<=now<end+timedelta(minutes=10)):
        raise ValueError("QUICK30_POST_MUST_RUN_2S_TO_10MIN_AFTER_30M_CLOSE")
    witness_pair()
    if target.parent.is_symlink():
        raise ValueError("SYMLINK_EVIDENCE_FOLDER_REJECTED")
    # Write-once journal created before FIRST provider request.
    with target.open("x",encoding="utf-8") as f:
        record = {
            "version":VERSION,"phase":"quick30_post","symbol":SYMBOL,
            "parent_open_utc":iso(parent),"parent_end_utc":iso(end),
            "reuse_pre_record_sha256":pre["record_sha256"],
            "rights_evidence_sha256":pre["rights_evidence_sha256"],
            "rights_status":"OPERATOR_ATTESTATION_NOT_PROVIDER_LICENSE",
            "requested_by":"MANUAL_OWNER","requests":[],
            "attempted":0,"completed":False,
            "scientific_qualification":"INCOMPLETE_NOT_STAGE03_CLOSED",
        }
        save_record(f,record)
        try:
            for endpoint, params in ALLOWED:
                record["attempted"] += 1
                save_record(f,record)
                entry = acquire(endpoint,params)
                if instant(entry)[0] <= end:
                    raise ValueError("QUICK30_RECEIPT_MAY_PRECEDE_30M_CLOSE")
                record["requests"].append(entry)
                save_record(f,record)
            time.sleep(0.6)
            last = witness_pair()
            decision=utcnow()
            u=float(last["conservative_absolute_utc_error_seconds"])
            if not 0 < u < 1.5:
                raise ValueError("DECISION_U_AT_OR_ABOVE_1_5_S")
            record["decision_witness"] = {
                "at_local_utc_unattested":iso(decision),
                "earliest_utc":iso(decision-timedelta(seconds=u)),
                "latest_utc":iso(decision+timedelta(seconds=u)),
                "independent_utc":last,
                "publisher_clock_verified":False,
            }
            inspect_decision(record,end)
            record["completed"]=True
            save_record(f,record)
        except Exception as exc:
            record["failure_code"]=type(exc).__name__+":"+str(exc)[:120]
            save_record(f,record)
            raise
    return record

def verify(pre_path:Path, post_path:Path, parent:datetime, rights_path:Path):
    pre=precheck(pre_path,parent,rights_path,fresh=False)
    with post_path.open("rb") as f:
        raw=f.read(700001)
    if len(raw)>700000:
        raise ValueError("QUICK30_RECEIPT_OVERSIZE")
    post=json.loads(raw)
    signed=post.pop("record_sha256",None)
    if signed!=digest(post):
        raise ValueError("QUICK30_RECEIPT_HASH_INVALID")
    post["record_sha256"]=signed
    end=parent+timedelta(minutes=30)
    if (post.get("version")!=VERSION or post.get("phase")!="quick30_post"
            or post.get("symbol")!=SYMBOL
            or post.get("parent_open_utc")!=iso(parent)
            or post.get("parent_end_utc")!=iso(end)
            or post.get("reuse_pre_record_sha256")!=pre["record_sha256"]
            or post.get("rights_evidence_sha256")!=pre["rights_evidence_sha256"]
            or post.get("attempted")!=4 or post.get("completed") is not True
            or len(post.get("requests",[]))!=4):
        raise ValueError("QUICK30_RECEIPT_SCOPE_OR_COMPLETION_INVALID")
    for entry, (path,params) in zip(post["requests"],ALLOWED):
        if (entry.get("path")!=path or entry.get("params")!=params
                or entry.get("status")!=200 or entry.get("raw_bytes",0)<=0
                or not isinstance(entry.get("raw_sha256"),str)
                or len(entry["raw_sha256"])!=64
                or instant(entry)[0] <= end):
            raise ValueError("QUICK30_MARKET_SOURCE_INVALID")
    for entry in post["requests"][:2]:
        _bars(entry,instant(entry)[1])
    info=pre["requests"][0]["selected"]
    book,ticker=[r["selected"] for r in post["requests"][2:4]]
    if (book["symbol"]!=SYMBOL or ticker["symbol"]!=SYMBOL
            or ticker.get("unit")!="USDT"
            or ticker.get("window")!="ROLLING_24H"):
        raise ValueError("QUICK30_SPOT_OR_TICKER_UNITS_INVALID")
    bid,ask,volume=(Decimal(book["bidPrice"]),Decimal(book["askPrice"]),
                    Decimal(ticker["quoteVolume"]))
    if (not all(v.is_finite() for v in (bid,ask,volume))
            or bid<=0 or ask<bid or volume<Decimal("10000000")
            or Decimal("20000")*(ask-bid)/(ask+bid)>Decimal("20")):
        raise ValueError("QUICK30_BOOK_OR_24H_INELIGIBLE")
    decision=inspect_decision(post,end)
    return pre,post,decision

def e2e(pre_path:Path,post_path:Path,parent:datetime,rights_path:Path):
    pre,post,decision=verify(pre_path,post_path,parent,rights_path)
    end=parent+timedelta(minutes=30)
    first,second=post["requests"][:2]
    bar30=[b for b in second["selected"]["bars"]
           if int(b["close_exclusive_ms"])==int(end.timestamp()*1000)]
    if len(bar30)!=1:
        raise ValueError("QUICK30_EXACT_PARENT_NOT_CLOSED")
    parentwin=win(second,bar30[0])
    fives=first["selected"]["bars"]
    exact=[b for b in fives if
           int(parent.timestamp()*1000)<=int(b["open_ms"]) and
           int(b["close_exclusive_ms"])<=int(end.timestamp()*1000)]
    if len(exact)!=6:
        raise ValueError("QUICK30_SIX_5M_CHILDREN_MISSING")
    children=tuple(win(first,x) for x in exact)
    last21=[b for b in fives if int(b["close_exclusive_ms"])<=int(end.timestamp()*1000)][-21:]
    if (len(last21)!=21 or
            int(last21[-1]["close_exclusive_ms"])!=int(end.timestamp()*1000)):
        raise ValueError("QUICK30_CORE_21X5M_PARENT_NOT_ALIGNED")
    core=tuple(Candle(w.open_at,w.close_at,w.received_at,w.available_at,
                      w.open,w.high,w.low,w.close,w.base_volume,w.quote_volume)
               for w in (win(first,r) for r in last21))
    book,ticker=post["requests"][2:4]
    market=MarketSnapshot(
        SYMBOL,"USDT",True,pre["requests"][0]["selected"]["status"],
        Decimal(ticker["selected"]["quoteVolume"]),
        Decimal(book["selected"]["bidPrice"]),
        Decimal(book["selected"]["askPrice"]),
        max(instant(book)[1],instant(ticker)[1]))
    tol=ReconciliationTolerance(Decimal("0.00000001"),Decimal("0.00000001"),
                                Decimal("0.0001"),
                                "BINANCE_SPOT_EXACT_PRICE_BASE_1E-8_QUOTE_1E-4_V1")
    outcome=assess_readiness(
        symbol=SYMBOL,horizon=Horizon.INTRADAY,direction=Direction.UP,
        parent=parentwin,children=children,core_5m=core,market=market,
        decision_at=decision,tolerance=tol,
        event_discriminator="QUICK30_REAL_PREPOST_SHA256:"+
            pre["record_sha256"]+":"+post["record_sha256"])
    mode=strict_pivot_mode(pre,parent)  # research-only; no invented mode
    passed=outcome["status"]=="RESEARCH_CANDIDATE"
    result={
        "schema":"ZS03_QUICK30_ORIGINAL_TO_03A_RESEARCH_V1",
        "real_30m_03a_e2e":"PASS" if passed else "REJECTED",
        "real_03a_status":outcome["status"],
        "real_03a_reason_codes":outcome["reason_codes"],
        "reconciliation":outcome["reconciliation"],
        "research_identity":outcome["identity"],
        "original_pre_sha256":pre["record_sha256"],
        "original_quick_post_sha256":post["record_sha256"],
        "rights_attestation_sha256":post["rights_evidence_sha256"],
        "pre4h_mode_review":mode,
        "independent_network_clock_bound_pass":True,
        "independent_clock_authenticated":False,
        "publisher_time_verified":False,
        "legal_license_verified_by_provider":False,
        "historic_pit_verified":False,
        "r2_n01_to_n12_real_source_qualified":False,
        "stage03_closed":False,"publishable":False,
        "score":None,"signal_id":None,"external_orders":0,
    }
    result["packet_sha256"]=digest(result)
    return result

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--phase",choices=("precheck","post","review"),required=True)
    p.add_argument("--parent-open-utc",required=True)
    p.add_argument("--evidence-dir",required=True)
    p.add_argument("--rights-attestation",required=True)
    p.add_argument("--manual-authorized",action="store_true")
    a=p.parse_args(argv)
    if not a.manual_authorized:
        p.error("EXPLICIT_OWNER_MANUAL_AUTHORIZATION_REQUIRED")
    try:
        parent=validate_open(a.parent_open_utc)
        folder=Path(a.evidence_dir).resolve()
        rights=Path(a.rights_attestation).resolve()
        pre,post,out=paths(folder,parent)
        if a.phase=="precheck":
            receipt=precheck(pre,parent,rights,fresh=True)
            print("QUICK30_PRECHECK=PASS")
            print("ORIGINAL_PRE_SHA256="+receipt["record_sha256"])
            print("REAL_30M_PARENT_OPEN_UTC="+iso(parent))
            print("QUICK30_EARLIEST_POST_UTC="+iso(parent+timedelta(minutes=30,seconds=2)))
            return 0
        if a.phase=="post":
            record=capture(pre,post,parent,rights)
            print("QUICK30_POST_RECEIPT="+str(post))
            print("QUICK30_POST_SHA256="+record["record_sha256"])
            print("QUICK30_POST_CAPTURE=PASS_UNREVIEWED")
            return 0
        result=e2e(pre,post,parent,rights)
        with out.open("x",encoding="utf-8") as f:
            f.write(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+"\n")
        print("REAL_30M_03A_E2E="+result["real_30m_03a_e2e"])
        print("REAL_03A_STATUS="+result["real_03a_status"])
        print("RESEARCH_RESULT_SHA256="+result["packet_sha256"])
        print("RESULT_PATH="+str(out))
        print("STAGE03_CLOSED=false")
        return 0 if result["real_30m_03a_e2e"]=="PASS" else 3
    except (ValueError,KeyError,TypeError,ArithmeticError,OSError) as exc:
        print("QUICK30_BLOCKED:"+str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
