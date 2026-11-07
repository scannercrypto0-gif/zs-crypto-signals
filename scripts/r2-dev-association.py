"""008: ONE exploratory DEV price association; NOT R2 qualified signals.

Uses real owner-retained private 010-B source, verified by 007A custody.
Strictly DEV-only outcomes. No synthetic/source receipt or claimed PIT.
Feature assignments are sealed before accessing forward price outcomes.
No optimization, trading, Telegram, OOS, Forward, or market network calls.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys

from zs_smart_gate.stage03a_contracts import Direction
from zs_smart_gate.stage03_order022 import (
    MONTHS, SYMBOLS, ResearchBlocked, filename, file_sha, read_month_zip,
    read_protocol,
)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "zs03_007a_existing_reader", ROOT / "scripts/r2-historical-dev.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

VERSION = "ZS03_008_ONE_DEV_PRICE_ASSOCIATION_V1"
PREDICTORS = {
    "INTRADAY": ("30M_STRONG_CLOSE", "SIX_5M_INTERNAL_QUALITY", "VOLUME_CONTINUITY"),
    "SWING": ("FOUR_H_STRONG_CLOSE", "FOUR_1H_INTERNAL_QUALITY", "MOMENTUM_VOLUME"),
}
FRAMES = {"INTRADAY": 6 * mod.FIVE_MIN, "SWING": mod.FOUR_HOUR}
FUTURES = {"INTRADAY": 4 * mod.HOUR, "SWING": 7 * mod.DAY}
UP = Direction.UP
DOWN = Direction.DOWN
NO_CI = "UNCERTAINTY_NOT_RELIABLY_ESTIMABLE_9_OR_FEWER_DEPENDENT_WEEKS"


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode()


def write_once(path, obj):
    raw = canonical(obj)
    with path.open("xb") as fp:
        fp.write(raw)
        fp.flush()
        os.fsync(fp.fileno())
    return hashlib.sha256(raw).hexdigest()


def prior_spec(directory, out):
    """Source/analysis contract is pinned BEFORE reading ANY OHLCV CSV rows."""
    mod.source_preflight(directory)
    protocol, proto_sha = read_protocol()
    dev = protocol["partitions"]["DEV"]
    if (dev["start_ms"], dev["end_exclusive_ms"]) != (1738368000000, 1743379200000):
        raise ResearchBlocked("ORIGINAL_DEV_PARTITION_CHANGED")
    policy = {
        "version": VERSION,
        "pre_outcome_state": "FROZEN_BEFORE_CSV_AND_OUTCOMES",
        "price_source": "EXISTING_VERIFIED_PRIVATE_RELEASE_010B_ONLY",
        "source_release_tag": mod.ASSET_TAG,
        "old_manifest_sha256": mod.OLD_MANIFEST_SHA256,
        "old_dataset_index_sha256": mod.OLD_DATASET_INDEX_SHA256,
        "original_archives_sha256": mod.source_preflight(directory),
        "protocol_sha256": proto_sha,
        "dev": dev,
        "only_symbols": list(SYMBOLS),
        "features": {k: list(v) for k, v in PREDICTORS.items()},
        "predictor": "UNWEIGHTED_ARITHMETIC_MEAN_OF_3_CURRENT_CLOSED_PARENT_FEATURES",
        "top_fraction": "0.20",
        "selection": "CEIL_20_PCT_RANK_BY_SCORE_DESC_THEN_PARENT_START_ASC",
        "selection_scope": "SYMBOL_HORIZON_DIRECTION_DEV_ONLY",
        "select_treatment_before_outcome_lookups": True,
        "entry": "NEXT_CONTIGUOUS_5M_OPEN_AFTER_PARENT_CLOSE",
        "outcome": "DIRECTIONAL_SIMPLE_PERCENTAGE_FROM_NEXT_OPEN_TO_EXACT_4H_OR_7D_CLOSE",
        "future_ms": FUTURES,
        "no_label_over_dev_end_exclusive": True,
        "baseline": "REMAINING_WINDOWS_SAME_SYMBOL_HORIZON_DIRECTION_DEV",
        "week_comparison": "UTC_MONDAY_WEEK_BLOCK_CONTRAST_WITH_BOTH_ARMS_ONLY",
        "no_independent_window_inference": True,
        "no_p_values_or_cis_with_9_weeks": True,
        "no_profitability_or_score": True,
        "code_sha256": {p: file_sha(ROOT / p) for p in (
            "scripts/r2-dev-association.py", "scripts/r2-historical-dev.py",
            "src/zs_smart_gate/stage03_r2_offline.py",
            "src/zs_smart_gate/stage03_order022.py",
            "src/zs_smart_gate/stage03a_contracts.py",
        )},
        "pr_head_sha": os.environ.get("PR_HEAD_SHA", "LOCAL_NOT_ATTESTED"),
        "pit": "HISTORICAL_REPLAY_PIT_UNVERIFIED",
        "oos": "NOT_RUN",
        "forward": "NOT_RUN",
    }
    return protocol, write_once(out / "freeze-008.json", policy)


def prep_source(symbol, directory):
    source = []
    for month in MONTHS:
        rows, meta = read_month_zip(Path(directory) / filename(symbol, month), symbol, month)
        if meta["invalid_rows"] or meta["duplicate_rows"] or meta["missing_5m_slots"]:
            raise ResearchBlocked("CSV_GAP_DUPLICATE_INVALID")
        source.extend(mod.from_source(x) for x in rows)
    mod.require_chain(source, mod.FIVE_MIN)
    frames = {"5m": source,
              "1h": mod.resample(source, mod.HOUR),
              "4h": mod.resample(source, mod.FOUR_HOUR)}
    ends = {key: [x.end for x in values] for key, values in frames.items()}
    return source, frames, ends


def children_for(parent, horizon, frames, ends):
    step = mod.FIVE_MIN if horizon == "INTRADAY" else mod.HOUR
    key = "5m" if horizon == "INTRADAY" else "1h"
    bars = frames[key]
    children = bars[bisect_right(ends[key], parent.start):
                    bisect_right(ends[key], parent.end)]
    mod.require_chain(children, step)
    if (len(children) != FRAMES[horizon] // step or
        children[0].start != parent.start or children[-1].end != parent.end or
        children[0].o != parent.o or children[-1].c != parent.c or
        max(x.h for x in children) != parent.h or
        min(x.l for x in children) != parent.l or
        sum((x.q for x in children), Decimal(0)) != parent.q):
        raise ResearchBlocked("PARENT_CHILD_RECONCILIATION_FAILURE")
    return children


def build_predictors(source, frames, ends, dev):
    """Look only backwards from each closed parent; NO future label reads here."""
    lo, hi = dev["start_ms"], dev["end_exclusive_ms"]
    grouped = {}
    census = {}
    for horizon, frame in FRAMES.items():
        parent_bars = mod.resample(source, frame)
        census[horizon] = Counter()
        groups = {d.value: [] for d in (UP, DOWN)}
        for parent in parent_bars:
            if not(lo <= parent.start and parent.end <= hi):
                continue
            census[horizon]["parents_in_original_dev"] += 1
            try:
                children = children_for(parent, horizon, frames, ends)
            except (mod.Unavailable, ResearchBlocked):
                census[horizon]["invalid_parent_children"] += 1
                continue
            for d in (UP, DOWN):
                values, reasons = mod.numeric_groups(
                    parent, children, frames, ends, d, horizon)
                wanted = PREDICTORS[horizon]
                if any(values[k] is None for k in wanted):
                    census[horizon]["missing_predictor_"+d.value] += 1
                    continue
                score = sum((values[k] for k in wanted), Decimal(0))/3
                if not Decimal(0) <= score <= Decimal(1):
                    raise ResearchBlocked("PREDICTOR_RANGE_INVALID")
                groups[d.value].append({
                    "start": parent.start, "end": parent.end,
                    "value": score, "week": (parent.start + 3*mod.DAY)//mod.WEEK,
                })
        grouped[horizon] = groups
    return grouped, census


def select_before_future(grouped, out, symbol):
    """Global DEV quantile fixed per asset/horizon/direction, rank ties causal."""
    assignments = {}
    seals = {}
    counts = {}
    for horizon, directions in grouped.items():
        assignments[horizon] = {}
        counts[horizon] = {}
        for direction, rows in directions.items():
            ordered = sorted(rows, key=lambda row: (-row["value"], row["start"]))
            n = len(ordered)
            k = (n + 4)//5  # ceil 20% with integer arithmetic
            selected = {r["start"] for r in ordered[:k]}
            sealed = [{"start": r["start"], "selected": r["start"] in selected,
                       "predictor":format(r["value"],".16f")}
                      for r in sorted(rows, key=lambda r:r["start"])]
            key = horizon+"_"+direction
            seals[key] = hashlib.sha256(canonical(sealed)).hexdigest()
            assignments[horizon][direction] = selected
            counts[horizon][direction] = {"predictor_available": n, "top_selected": k,
                                           "reference_selected":n-k}
    pre = {"state": "SEALED_BEFORE_FUTURE_OUTCOME_READ",
           "version": VERSION, "assignment_hashes": seals,
           "selection_counts": counts,
           "no_futures_read_so_far": True,
           "source_pit": "UNVERIFIED"}
    seal_sha = write_once(out / ("assignment-seal-008-" + symbol + ".json"), pre)
    return assignments, counts, seal_sha


def exact_future_label(source, starts, parent_end, future_ms, dev_end, direction):
    """Next 5m open, exact n-bar close, contiguous, wholly inside DEV."""
    end = parent_end + future_ms
    if end > dev_end:
        return None, "LABEL_CROSSES_DEV_END_PURGED"
    i = bisect_left(starts, parent_end)
    n = future_ms // mod.FIVE_MIN
    if (i+n > len(source) or i == len(source) or source[i].start != parent_end or
        source[i+n-1].end != end):
        return None, "LABEL_FUTURE_COVERAGE_MISSING"
    # Validate each intervening source bar BEFORE using its outcome close.
    for j in range(i,i+n-1):
        if source[j].end != source[j+1].start:
            return None, "LABEL_FUTURE_GAP_REJECTED"
    start_price, close_price = source[i].o, source[i+n-1].c
    if start_price <= 0:
        return None,"LABEL_ENTRY_PRICE_INVALID"
    sign = Decimal(1) if direction=="UP" else Decimal(-1)
    return 100*sign*(close_price-start_price)/start_price, None


def sample_stats(rows):
    if not rows: return {"n":0,"mean_pct":None,"median_pct":None,
                         "positive":0,"negative":0,"zero":0,"positive_fraction":None}
    values = [float(row["return_pct"]) for row in rows]
    n=len(values)
    return {"n":n, "mean_pct":round(statistics.fmean(values),8),
            "median_pct":round(statistics.median(values),8),
            "positive":sum(v>0 for v in values),
            "negative":sum(v<0 for v in values),
            "zero":sum(v==0 for v in values),
            "positive_fraction":round(sum(v>0 for v in values)/n,8)}


def compare(top, rest):
    """Comparison on outcome-available cases, not overlapping independent tests."""
    a=sample_stats(top)
    b=sample_stats(rest)
    return {"top":a,"rest":b,
            "mean_difference_pct_points":(round(a["mean_pct"]-b["mean_pct"],8)
                                          if a["n"] and b["n"] else None),
            "median_difference_pct_points":(round(a["median_pct"]-b["median_pct"],8)
                                            if a["n"] and b["n"] else None)}


def block_compare(top, rest):
    top_by=defaultdict(list)
    rest_by=defaultdict(list)
    for row in top: top_by[row["week"]].append(row)
    for row in rest: rest_by[row["week"]].append(row)
    weeks=sorted(set(top_by)|set(rest_by))
    contrasts=[]
    for w in weeks:
        if top_by[w] and rest_by[w]:
            a=sample_stats(top_by[w]); b=sample_stats(rest_by[w])
            contrasts.append({
                "week_id":int(w),"top_n":a["n"],"rest_n":b["n"],
                "top_mean_pct":a["mean_pct"],"rest_mean_pct":b["mean_pct"],
                "difference_pct_points":round(a["mean_pct"]-b["mean_pct"],8),
            })
    weights=sum(x["top_n"] for x in contrasts)
    return {"observed_asset_weeks":len(weeks),
            "weeks_with_both_groups":len(contrasts),
            "weeks_treatment_mean_above_control":sum(x["difference_pct_points"]>0 for x in contrasts),
            "weeks_treatment_mean_below_control":sum(x["difference_pct_points"]<0 for x in contrasts),
            "weeks_tied":sum(x["difference_pct_points"]==0 for x in contrasts),
            "top_weighted_within_week_difference_pct_points":(
                round(sum(x["top_n"]*x["difference_pct_points"] for x in contrasts)/weights,8)
                if weights else None),
            "week_aggregates":contrasts,
            "confidence_interval":None,
            "uncertainty_status":NO_CI}


def evaluate_future(source, grouped, selections, dev):
    starts=[x.start for x in source]
    result={}
    for horizon, directions in grouped.items():
        result[horizon]={}
        for direction, records in directions.items():
            top=[]; rest=[]
            missing=Counter()
            selected=selections[horizon][direction]
            for rec in records:
                value,reason=exact_future_label(
                    source,starts,rec["end"],FUTURES[horizon],
                    dev["end_exclusive_ms"],direction)
                if reason:
                    missing[reason]+=1
                    continue
                row={"return_pct":value,"week":rec["week"]}
                (top if rec["start"] in selected else rest).append(row)
            summary=compare(top,rest)
            summary["within_week"]=block_compare(top,rest)
            summary["candidate_predictors"]=len(records)
            summary["label_known"]=len(top)+len(rest)
            summary["label_unavailable"]=sum(missing.values())
            summary["label_unavailable_reasons"]=dict(sorted(missing.items()))
            summary["market_profitability"]="NOT_EVALUATED_PRICE_ASSOCIATION_ONLY"
            result[horizon][direction]=summary
    return result


def execute(directory, output):
    output=Path(output)
    if output.exists():
        raise ResearchBlocked("RESULT_DIRECTORY_CREATE_ONCE_ONLY")
    output.mkdir(parents=True)
    # Before any OHLCV examination: full release custody + study freeze.
    custody_path = ROOT / "scripts/order025-github-custody.py"
    cspec=importlib.util.spec_from_file_location("zs03_008_custody", custody_path)
    custody=importlib.util.module_from_spec(cspec)
    cspec.loader.exec_module(custody)
    verified=custody.verify_download(directory,require_transfer_receipt=True)
    if verified["zip_count"]!=12 or verified["status"]!="GITHUB_TRANSFER_HASHES_VERIFIED":
        raise ResearchBlocked("PRIVATE_SOURCE_VERIFICATION_FAILED")
    protocol,freeze_sha=prior_spec(directory,output)
    all_data={}
    for symbol in SYMBOLS:
        source,frames,ends=prep_source(symbol,directory)
        grouped,census=build_predictors(source,frames,ends,protocol["partitions"]["DEV"])
        selections,counts,seal_sha=select_before_future(grouped,output,symbol)
        associations=evaluate_future(source,grouped,selections,protocol["partitions"]["DEV"])
        all_data[symbol]={
            "source_5m_bars":len(source),
            "dev_window_census":{k:dict(sorted(v.items())) for k,v in census.items()},
            "selection_counts":counts,
            "assignment_seal_sha256":seal_sha,
            "eight_cells_by_horizon_and_direction":associations,
        }
        # One output per run, not raw rows. Extra isolated owner dataset evidence
        # never enters workflow artifacts or CI logs.
        # Each symbol's result is retained only in memory until combined report.
        # Remove the second seal once created? No: use unique per-symbol files.
    report={
        "schema":VERSION, "status":"ONE_EXPLORATORY_DEV_FORWARD_PRICE_ASSOCIATION",
        "code_pr_head_sha":os.environ.get("PR_HEAD_SHA","LOCAL_NOT_ATTESTED"),
        "freeze_sha256":freeze_sha,
        "source_zip_sha256_verified":12,
        "dev":protocol["partitions"]["DEV"],
        "data":all_data,
        "source_pit":"HISTORICAL_REPLAY_PIT_UNVERIFIED",
        "selection_note":"TOP20_UNWEIGHTED_R2_PRICE_ONLY_GROUPS_NOT_QUALIFIED",
        "tests_interpretation":"EXPLORATORY_MULTIPLE_CORRELATED_TESTS_NO_P_VALUE",
        "net_executable_pnl":None,"qualified_signal_count":None,
        "economic_costs":"UNAVAILABLE_BID_ASK_FILLS",
        "N_eff":"UNDETERMINED_OVERLAP_AND_TWO_CORRELATED_ASSETS",
        "N_REQUIRED":"UNDETERMINED_NO_VALID_EFFECT_POWER_AND_MATCHED_CONTROL",
        "science_confirmatory_pass":False, "oos":"NOT_RUN","forward":"NOT_RUN",
        "market_requests":0, "trading":False,"telegram":False,"stage05":"FULL_HOLD",
    }
    report["research_interpretation"]=(
        "INSUFFICIENT_EXPLORATORY_ONLY_NO_RELIABLE_WEEK_BLOCK_INFERENCE")
    digest=write_once(output/"aggregate-008.json",report)
    return {"status":report["status"],"report_sha256":digest,
            "freeze_sha256":freeze_sha,"source_zip_sha256_verified":12,
            "conclusion":report["research_interpretation"],
            "market_requests":0,"confirmatory_pass":False}


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--download-dir",required=True)
    p.add_argument("--output-dir",required=True)
    args=p.parse_args(argv)
    try:
        print(json.dumps(execute(Path(args.download_dir),Path(args.output_dir)),
                         sort_keys=True))
        return 0
    except (ResearchBlocked,mod.Unavailable,OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({"status":"008_BLOCKED_FAIL_CLOSED",
                          "reason":str(exc).split(":",1)[0],
                          "market_requests":0},sort_keys=True),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
