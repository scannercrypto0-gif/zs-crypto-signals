"""007A: one existing-owner-archive, DEV-only, price/volume descriptive R2 replay.

The original 010-B data are downloaded separately from an existing PRIVATE
GitHub Release. Zero market requests. NEVER construct R2.Candle,
R2.SourceReceipt, R2.ClockWitness, or call R2.evaluate_r2 on historical data.
Only pure preexisting numerical functions consume close-only HistoricalOHLCV.
No original historical receipt, publisher time, market book, qualifying signal,
production score, trade execution, profitability, OOS or Forward is certified.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

from zs_smart_gate.stage03_order022 import (
    MONTHS, SYMBOLS, ResearchBlocked, file_sha, filename, read_month_zip,
    read_protocol,
)
from zs_smart_gate.stage03a_contracts import Direction
from zs_smart_gate.stage03_r2_offline import (
    Unavailable, close_parts, path_parts, volume_continuity,
    prior_range_alignment, atr14_prev, fpos,
)

ROOT = Path(__file__).resolve().parents[1]
OLD_MANIFEST_SHA256 = "45116717abe2ddda7d906ab5bf97a5507a39720c64fbbd175e7daf2c4e67c738"
OLD_DATASET_INDEX_SHA256 = "ce0a3716f24612ea04427b12454e420f9f7e10a0a9bedd622c0ac866a372da79"
ASSET_TAG = "order022-private-010b-2025-v1"
VERSION = "ZS03_R2_007A_PRICE_VOLUME_DEV_DESCRIPTIVE_ONLY_V1"
FIVE_MIN = 300_000
HOUR = 12 * FIVE_MIN
FOUR_HOUR = 4 * HOUR
DAY = 24 * HOUR
WEEK = 7 * DAY


def fail(reason: str):
    raise ResearchBlocked(reason)


@dataclass(frozen=True)
class HistoricalOHLCV:
    """Price/volume observations only: deliberately NO receipt/available/clock."""
    start: int
    end: int
    o: Decimal
    h: Decimal
    l: Decimal
    c: Decimal
    q: Decimal


def from_source(bar):
    return HistoricalOHLCV(bar.start, bar.end, bar.open, bar.high,
                           bar.low, bar.close, bar.quote_volume)


def sha_obj(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()


def require_chain(bars, step):
    if not bars or any(b.end-b.start != step for b in bars):
        raise Unavailable("CANDLE_INTERVAL_INVALID")
    if any(a.end != b.start for a, b in zip(bars, bars[1:])):
        raise Unavailable("CANDLE_GAP_OR_OVERLAP")
    if any(not b.o > 0 or not b.c > 0 or b.q < 0
           or b.l > min(b.o, b.c) or b.h < max(b.o, b.c) for b in bars):
        raise Unavailable("CANDLE_OHLCV_INVALID")


def aggregate(bars, frame):
    require_chain(bars, FIVE_MIN)
    if bars[0].start % frame or bars[-1].end != bars[0].start + frame:
        raise Unavailable("PARENT_BOUNDARY_OR_COMPLETENESS")
    if len(bars) != frame // FIVE_MIN:
        raise Unavailable("INCOMPLETE_PARENT")
    return HistoricalOHLCV(bars[0].start, bars[-1].end, bars[0].o,
                           max(b.h for b in bars), min(b.l for b in bars),
                           bars[-1].c, sum((b.q for b in bars), Decimal(0)))


def resample(source, frame):
    """Only complete UTC-aligned bars. The weekly boundary is ISO Monday UTC."""
    if frame % FIVE_MIN:
        fail("UNSUPPORTED_RESAMPLE_FRAME")
    result = []
    q = frame // FIVE_MIN
    for i in range(0, len(source)-q+1):
        b = source[i]
        # Unix epoch was Thursday: ISO Monday is 3 days before epoch.
        aligned = (b.start + (3*DAY if frame == WEEK else 0)) % frame == 0
        if not aligned:
            continue
        seg = source[i:i+q]
        try:
            require_chain(seg, FIVE_MIN)
            if seg[-1].end != seg[0].start+frame:
                raise Unavailable("PARTIAL_PARENT")
            result.append(HistoricalOHLCV(seg[0].start, seg[-1].end, seg[0].o,
                max(x.h for x in seg), min(x.l for x in seg), seg[-1].c,
                sum((x.q for x in seg), Decimal(0))))
        except Unavailable:
            continue
    return result


def history_before(frames, ends, anchor, n, frame, *, aligned_last=False):
    """No source times are simulated. All contexts end <= evaluation cutoff."""
    idx = bisect_right(ends, anchor)
    if idx < n:
        raise Unavailable("HISTORICAL_CONTEXT_WARMUP_INSUFFICIENT")
    seq = frames[idx-n:idx]
    require_chain(seq, frame)
    if seq[-1].end > anchor or anchor-seq[-1].end >= frame:
        raise Unavailable("HISTORICAL_CONTEXT_STALE")
    if aligned_last and seq[-1].end != anchor:
        raise Unavailable("HISTORICAL_CONTEXT_NOT_ADJACENT")
    return seq


def bounded(value):
    if not value.is_finite() or not Decimal(0) <= value <= Decimal(1):
        raise Unavailable("R2_NORMALIZER_OUT_OF_RANGE")
    return value


def numeric_groups(parent, children, frames, ends, direction, horizon):
    """Reuses unchanged existing R2 PURE math, no synthetic time/PIT wrappers."""
    groups = {}
    missing = {}
    expected = (("30M_STRONG_CLOSE","SIX_5M_INTERNAL_QUALITY",
                 "MOMENTUM_EARLY_TIMING","VOLUME_CONTINUITY",
                 "MTF_NEARBY_STRUCTURE","LIQUIDITY_QUALITY")
                if horizon == "INTRADAY" else
                ("MARKET_STRUCTURE","FOUR_H_STRONG_CLOSE",
                 "FOUR_1H_INTERNAL_QUALITY","DAILY_WEEKLY_CONTEXT",
                 "MOMENTUM_VOLUME","LIQUIDITY_QUALITY"))
    # Explicit missingness: cannot infer receipt/market snapshots from OHLCV.
    blocked = {
        "MOMENTUM_EARLY_TIMING":"UNAVAILABLE_FULL_IMPULSE_UNFROZEN",
        "MARKET_STRUCTURE":"UNAVAILABLE_VERIFIED_STRUCTURAL_LIQUIDITY",
        "LIQUIDITY_QUALITY":"UNAVAILABLE_HISTORICAL_BOOK_24H",
        "DAILY_WEEKLY_CONTEXT":"UNAVAILABLE_MODE_AND_18W_WARMUP_NOT_VERIFIED",
    }
    for name in expected:
        if name in blocked:
            groups[name] = None
            missing[name] = blocked[name]
            continue
        try:
            if name in ("30M_STRONG_CLOSE", "FOUR_H_STRONG_CLOSE"):
                k,b,w = close_parts(parent,direction)
                value = ((8*k+6*b+6*w)/20 if horizon == "INTRADAY"
                         else Decimal(".4")*k+Decimal(".3")*b+Decimal(".3")*w)
            elif name in ("SIX_5M_INTERNAL_QUALITY", "FOUR_1H_INTERNAL_QUALITY"):
                g,e,t=path_parts(children,direction)
                value = ((8*g+8*e+4*t)/20 if horizon == "INTRADAY"
                         else Decimal(".4")*g+Decimal(".4")*e+Decimal(".2")*t)
            elif name == "VOLUME_CONTINUITY":
                prev = history_before(frames["5m"],ends["5m"],parent.start,20,FIVE_MIN,
                                      aligned_last=True)
                value=volume_continuity(children,prev)
            elif name == "MTF_NEARBY_STRUCTURE":
                hr = history_before(frames["1h"],ends["1h"],parent.start,21,HOUR)
                four = history_before(frames["4h"],ends["4h"],parent.start,21,FOUR_HOUR)
                value=(10*prior_range_alignment(hr,direction)
                       +5*prior_range_alignment(four,direction))/15
            elif name == "MOMENTUM_VOLUME":
                prior=history_before(frames["4h"],ends["4h"],parent.start,20,FOUR_HOUR,
                                     aligned_last=True)
                a=atr14_prev(prior)
                mean=sum((x.q for x in prior),Decimal(0))/20
                if mean <= 0:
                    raise Unavailable("VOLUME_REFERENCE_ZERO")
                d=Decimal(1) if direction is Direction.UP else Decimal(-1)
                momentum=max(Decimal(0),d*(parent.c-parent.o))/a
                surplus=max(Decimal(0),parent.q/mean-Decimal(1))
                value=Decimal(".6")*fpos(momentum)+Decimal(".4")*fpos(surplus)
            else:
                raise Unavailable("NOT_A_PRICE_ONLY_GROUP")
            groups[name]=bounded(value)
        except (Unavailable, ValueError, ArithmeticError, ZeroDivisionError) as exc:
            groups[name]=None
            missing[name]="UNAVAILABLE_"+str(exc).split(":",1)[0]
    return groups,missing


def source_preflight(directory):
    """Fail on original 010-B pin mismatch BEFORE opening any market CSV."""
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        fail("PRIVATE_RELEASE_DIRECTORY_REQUIRED")
    mpath = directory/"manifest.json"
    ipath = directory/"dataset-index.json"
    if file_sha(mpath)!=OLD_MANIFEST_SHA256 or file_sha(ipath)!=OLD_DATASET_INDEX_SHA256:
        fail("OLD_010B_MANIFEST_OR_INDEX_SHA_MISMATCH")
    old=json.loads(mpath.read_bytes())
    pins={}
    for obj in old.get("files",[]):
        key=(obj.get("symbol"),obj.get("name"))
        if (key[0] in SYMBOLS and key[1] in
            {filename(s,m) for s in SYMBOLS for m in MONTHS} and
            obj.get("interval")=="5m"):
            if key in pins:fail("ORIGINAL_ZIP_PIN_DUPLICATE")
            pins[key]=obj.get("sha256")
    if len(pins)!=12:fail("TWELVE_ORIGINAL_ZIP_PINS_MISSING")
    files={}
    for sym in SYMBOLS:
        for mon in MONTHS:
            name=filename(sym,mon)
            path=directory/name
            if not path.is_file() or path.is_symlink():
                fail("ORIGINAL_ZIP_NOT_FOUND")
            actual=file_sha(path)
            if not isinstance(pins[(sym,name)],str) or not re.fullmatch(r"[0-9a-f]{64}",pins[(sym,name)]):
                fail("ORIGINAL_PIN_MALFORMED")
            if actual != pins[(sym,name)]:
                fail("ORIGINAL_ZIP_SHA256_MISMATCH")
            files[name]=actual
    return files


def create_freeze(out, directory):
    """WRITE-ONCE experiment identity and hashes; called before ANY CSV evaluation."""
    files=source_preflight(directory)
    protocol, protocol_sha=read_protocol()
    dev=protocol["partitions"]["DEV"]
    # R2, source parser and original manifest must be bound to exact bytes.
    code_paths=("scripts/r2-historical-dev.py",
                "src/zs_smart_gate/stage03_r2_offline.py",
                "src/zs_smart_gate/stage03_order022.py",
                "src/zs_smart_gate/stage03a_contracts.py")
    root=ROOT
    frozen={
        "version":VERSION,
        "status":"FROZEN_BEFORE_DEV_COMPUTATION",
        "source":"EXISTING_OWNER_PRIVATE_RELEASE_ONLY",
        "release_tag":ASSET_TAG,
        "archive_sha256":files,
        "original_manifest_sha256":OLD_MANIFEST_SHA256,
        "original_dataset_index_sha256":OLD_DATASET_INDEX_SHA256,
        "protocol_sha256":protocol_sha,
        "dev_partition":dev,
        "code_sha256":{p:file_sha(root/p) for p in code_paths},
        "github_pr_head_sha":os.environ.get("PR_HEAD_SHA","NOT_ATTESTED_LOCAL_ONLY"),
        "historical_pit":"HISTORICAL_DESCRIPTIVE_PIT_UNVERIFIED",
        "modes":"UNCLASSIFIED_NO_BOS_CHOCH_ATTESTATION",
        "scientific_pass":False,
    }
    raw=(json.dumps(frozen,sort_keys=True,separators=(",",":"),ensure_ascii=True)+"\n").encode()
    with (out/"freeze-007a.json").open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    return frozen,hashlib.sha256(raw).hexdigest(),protocol


class Stats:
    def __init__(self,names):
        self.windows=0
        self.values={n:{"n":0,"sum":Decimal(0),"sum_squared":Decimal(0)} for n in names}
        self.missing={n:Counter() for n in names}
        self.up_closed=0
        self.down_closed=0
        self.zero_closed=0

    def add(self,parent,groups,missing):
        self.windows+=1
        delta=parent.c-parent.o
        self.up_closed+=int(delta>0)
        self.down_closed+=int(delta<0)
        self.zero_closed+=int(delta==0)
        for name in self.values:
            value=groups[name]
            if value is None:
                self.missing[name][missing[name]]+=1
            else:
                self.values[name]["n"]+=1
                self.values[name]["sum"]+=value
                self.values[name]["sum_squared"]+=value*value

    def export(self):
        return {
            "observed_closed_windows":self.windows,
            "price_only_same_window_reference":{"positive":self.up_closed,
                "negative":self.down_closed,"unchanged":self.zero_closed,
                "meaning":"UNCONDITIONAL_SAME_CANDLE_REFERENCE_NOT_MATCHED_TREATMENT"},
            "groups":{n:{
                "n":v["n"],
                "mean":(format(v["sum"]/v["n"],".8f") if v["n"] else None),
                "std_population":(format(max(Decimal(0),
                      v["sum_squared"]/v["n"]-(v["sum"]/v["n"])**2).sqrt(),".8f")
                      if v["n"] else None),
                "missing_n":sum(self.missing[n].values()),
                "missing_reason_counts":dict(sorted(self.missing[n].items()))
            } for n,v in self.values.items()}
        }


def study_one_symbol(symbol, directory, protocol):
    source=[]
    coverage=[]
    for month in MONTHS:
        raw,meta=read_month_zip(directory/filename(symbol,month),symbol,month)
        coverage.append(meta)
        source.extend(from_source(x) for x in raw)
    if not source:
        fail("EMPTY_SOURCE_AFTER_VERIFICATION")
    for before,after in zip(source,source[1:]):
        if after.start <= before.start:
            fail("SOURCE_CROSS_MONTH_NON_MONOTONIC")
    source_gaps=sum((after.start-before.end)//FIVE_MIN
                    for before,after in zip(source,source[1:]) if before.end!=after.start)
    frames={"5m":source,"1h":resample(source,HOUR),"4h":resample(source,FOUR_HOUR)}
    ends={name:[x.end for x in bars] for name,bars in frames.items()}
    frame_counts={key:len(value) for key,value in frames.items()}
    allowed_dev=protocol["partitions"]["DEV"]
    lo,hi=allowed_dev["start_ms"],allowed_dev["end_exclusive_ms"]
    counts={}
    for horizon,frame,name_list in [
        ("INTRADAY",6*FIVE_MIN,("30M_STRONG_CLOSE","SIX_5M_INTERNAL_QUALITY",
            "MOMENTUM_EARLY_TIMING","VOLUME_CONTINUITY",
            "MTF_NEARBY_STRUCTURE","LIQUIDITY_QUALITY")),
        ("SWING",FOUR_HOUR,("MARKET_STRUCTURE","FOUR_H_STRONG_CLOSE",
            "FOUR_1H_INTERNAL_QUALITY","DAILY_WEEKLY_CONTEXT",
            "MOMENTUM_VOLUME","LIQUIDITY_QUALITY")),
    ]:
        series=resample(source,frame)
        by_direction={d:Stats(name_list) for d in (Direction.UP,Direction.DOWN)}
        dev_windows=0
        week_blocks=set()
        gap_reject=0
        for p in series:
            if not(lo<=p.start and p.end<=hi):
                continue
            children=source[bisect_right(ends["5m"],p.start):bisect_right(ends["5m"],p.end)]
            # Use 1h children for swing; exact 4h parent must reconcile.
            if horizon=="SWING":
                children=frames["1h"][bisect_right(ends["1h"],p.start):
                                      bisect_right(ends["1h"],p.end)]
                step=HOUR
            else:
                step=FIVE_MIN
            try:
                require_chain(children,step)
                if (len(children)!=frame//step or children[0].start!=p.start or
                    children[-1].end!=p.end or
                    children[0].o!=p.o or children[-1].c!=p.c or
                    p.h!=max(c.h for c in children) or
                    p.l!=min(c.l for c in children) or
                    p.q!=sum((c.q for c in children),Decimal(0))):
                    raise Unavailable("PARENT_CHILD_MISMATCH")
            except Unavailable:
                gap_reject+=1
                continue
            dev_windows+=1
            week_blocks.add((p.start+3*DAY)//WEEK)
            for d in (Direction.UP,Direction.DOWN):
                result,missing=numeric_groups(p,children,frames,ends,d,horizon)
                by_direction[d].add(p,result,missing)
        counts[horizon]={
            "unique_parent_decision_windows":dev_windows,
            "directional_rows_share_same_windows":2*dev_windows,
            "pre_eligibility_parent_or_child_gap_rejects":gap_reject,
            "distinct_UTC_week_blocks":len(week_blocks),
            "mode_classification":"UNCLASSIFIED_NOT_BOS_CHoCH",
            "continuation_events_qualified":None,
            "reversal_events_qualified":None,
            "pre_move_events_qualified":None,
            "by_direction":{d.value:by_direction[d].export() for d in by_direction},
        }
    return {"coverage_5m_by_month":coverage, "five_minute_source_bars":len(source),
            "cross_month_missing_5m_slots":source_gaps,
            "completed_frames":frame_counts,
            "dev":counts}


def run(directory, out):
    out=Path(out)
    if out.exists():
        fail("OUTPUT_MUST_BE_CREATE_ONCE")
    out.mkdir(parents=True,exist_ok=False)
    # The full release verifier additionally checks asset-index, old manifest,
    # dataset-index, transfer receipt and SHA of ALL bytes (no market GET).
    custody_path=ROOT/"scripts/order025-github-custody.py"
    spec=importlib.util.spec_from_file_location("order025_custody_007a",custody_path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    custody=mod.verify_download(directory,require_transfer_receipt=True)
    if custody["status"]!="GITHUB_TRANSFER_HASHES_VERIFIED":
        fail("PRIVATE_RELEASE_VERIFICATION_FAILED")
    freeze,freeze_sha,proto=create_freeze(out,directory)
    symbols={}
    for symbol in SYMBOLS:
        symbols[symbol]=study_one_symbol(symbol,Path(directory),proto)
    report={
        "schema":VERSION,
        "status":"DEV_REAL_HISTORICAL_PRICE_VOLUME_DESCRIPTIVE_ONLY",
        "source_verified":"OWNER_PRIVATE_RELEASE_HASHES_VERIFIED_12_OF_12",
        "release":ASSET_TAG,
        "freeze_sha256":freeze_sha,
        "code_pr_head_sha":freeze["github_pr_head_sha"],
        "protocol_sha256":freeze["protocol_sha256"],
        "partition":freeze["dev_partition"],
        "symbols":symbols,
        "market_rest_get":0,"market_ws":0,"new_live_nts":0,
        "mode_classification":"UNCLASSIFIED",
        "pre_move_status":"UNAVAILABLE_FULL_IMPULSE_UNFROZEN",
        "pit_status":"HISTORICAL_DESCRIPTIVE_PIT_UNVERIFIED",
        "qualification":False,"score":None,"probability":None,
        "signal_id":None,"delivery_authorized":False,
        "execution_cost_status":"UNKNOWN_HISTORICAL_BID_ASK_FILL_ABSENT",
        "down_spot_status":"NO_SHORT_AND_NO_INVENTORY_PNL_ESTIMATED",
        "statistical_N_eff":"UNDETERMINED_DIRECTIONAL_AND_OVERLAPPING_WINDOWS",
        "N_REQUIRED":"UNDETERMINED_NO_QUALIFIED_EFFECT_VARIANCE_POWER",
        "oos":"NOT_RUN","forward":"NOT_RUN",
        "science_pass":False,"stage05":"FULL_HOLD",
    }
    target=out/"dev-aggregate-007a.json"
    raw=(json.dumps(report,sort_keys=True,separators=(",",":"),ensure_ascii=True)+"\n").encode()
    with target.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    return {"status":report["status"],"report_sha256":hashlib.sha256(raw).hexdigest(),
            "freeze_sha256":freeze_sha,
            "source_zip_sha256_verified":12,
            "total_unique_parent_windows_by_horizon":{
                horizon:sum(x["dev"][horizon]["unique_parent_decision_windows"]
                            for x in symbols.values())
                for horizon in ("INTRADAY","SWING")},
            "output":"REDACTED_AGGREGATES_ONLY",
            "market_requests":0,"scientific_pass":False}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--download-dir",required=True)
    ap.add_argument("--output-dir",required=True)
    args=ap.parse_args(argv)
    try:
        print(json.dumps(run(Path(args.download_dir),Path(args.output_dir)),
                         sort_keys=True))
        return 0
    except (ResearchBlocked,Unavailable,OSError,ValueError,KeyError,TypeError,
            json.JSONDecodeError) as exc:
        print(json.dumps({"status":"DEV_BLOCKED_FAIL_CLOSED",
              "reason":str(exc).split(":",1)[0],
              "market_requests":0,"scientific_pass":False},sort_keys=True),
              file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
