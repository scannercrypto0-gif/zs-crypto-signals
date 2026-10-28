"""03B3 bounded terminal accounting: 12 fixed slots, no replacement or future outcomes.

The code can prevent duplicate evidence rows; GitHub Actions opt-in dispatch is
not a transactional global 96-GET quota without Stage04 persistent state.
Only one *authorized* manual execution per declared slot is permitted.
"""
from __future__ import annotations

from datetime import datetime,timezone
import json
from pathlib import Path

from .core import utc
from .stage03b3_manifest import MANIFEST
from .stage03b2_research import frozen_hash

STATES={"OBSERVED_PIT","INELIGIBLE","FAILED","LATE","NOT_ATTEMPTED"}


def terminal_report(records: list[dict],*, as_of: datetime) -> dict:
    as_of=utc(as_of)
    expected={(symbol,s.horizon.value,s.label):s for symbol in MANIFEST.assets
              for s in MANIFEST.slots}
    seen={}
    attempts=0
    counts={x:0 for x in sorted(STATES)}
    for record in records:
        if not isinstance(record,dict) or record.get("evidence_sha256")!=frozen_hash(
                {k:v for k,v in record.items() if k!="evidence_sha256"}):
            raise ValueError("UNSEALED_OR_TAMPERED_PROSPECTIVE_RECORD")
        if record.get("study_id")!=MANIFEST.study_id:
            raise ValueError("UNAPPROVED_OR_CHANGED_STUDY_MANIFEST")
        key=(record.get("symbol"),record.get("horizon"),record.get("slot"))
        if key not in expected:
            raise ValueError("SLOT_OUTSIDE_FROZEN_MANIFEST")
        if key in seen:
            raise ValueError("DUPLICATE_PROSPECTIVE_SLOT_OR_RERUN")
        seen[key]=record
        if record.get("parent_close_at")!=expected[key].close_at.isoformat():
            raise ValueError("SLOT_CLOSE_TIME_REWRITE")
        state=record.get("status")
        if state not in STATES:
            raise ValueError("UNRECOGNIZED_TERMINAL_EVIDENCE_STATE")
        if (record.get("signal_id") is not None or record.get("score") is not None or
            record.get("qualified_signal") is not False or
            record.get("trade_plan_status")!="RESEARCH_ONLY"):
            raise ValueError("FORBIDDEN_SIGNAL_OR_TRADE_OUTPUT")
        telemetry=record.get("telemetry")
        if not isinstance(telemetry,dict):
            raise ValueError("MISSING_PHYSICAL_ATTEMPT_TELEMETRY")
        n=telemetry.get("physical_http_attempts")
        if type(n)!=int or n<0 or n>MANIFEST.physical_attempts_per_slot:
            raise ValueError("PER_SLOT_PHYSICAL_ATTEMPT_CEILING_EXCEEDED")
        attempts+=n
        if state=="OBSERVED_PIT":
            receipt=record.get("receipt_at")
            if not isinstance(receipt,dict) or set(receipt)!={"market","parent","child_batch"}:
                raise ValueError("PIT_SOURCE_RECEIPT_MISSING")
            limit=expected[key].close_at.timestamp()+MANIFEST.receipt_grace_seconds
            dt=utc(datetime.fromisoformat(record["decision_at"]))
            if not expected[key].close_at<=dt or dt.timestamp()>limit or dt>MANIFEST.stop_at:
                raise ValueError("BACKDATED_OR_LATE_PIT_DECISION")
            if any(not expected[key].close_at<=utc(datetime.fromisoformat(v))<=dt
                   for v in receipt.values()):
                raise ValueError("PIT_RECEIPT_OUTSIDE_DECISION")
            if (record.get("reconciliation",{}).get("status")!="PASS" or
                not record.get("features") or record.get("source_publication_at") is not None or
                not record.get("source_payload_sha256")):
                raise ValueError("MISSING_STAGE03A_OR_RESEARCH_PROVENANCE")
            raw=record.get("source_parsed_original_numeric_strings")
            if raw is None or frozen_hash(raw)!=record["source_payload_sha256"]:
                raise ValueError("RAW_CANDLE_CONTENT_REVISED")
        elif record.get("features") is not None:
            raise ValueError("NON_PIT_FEATURE_LEAKAGE")
        counts[state]+=1
    missing=[]
    for key,slot in expected.items():
        if key not in seen:
            counts["NOT_ATTEMPTED"]+=1
            missing.append({"symbol":key[0],"horizon":key[1],"slot":key[2],
                            "close_at":slot.close_at.isoformat(),"status":"NOT_ATTEMPTED"})
    if attempts>MANIFEST.total_slot_attempt_ceiling:
        raise ValueError("AGGREGATE_PHYSICAL_REQUEST_CEILING_EXCEEDED")
    observed=counts["OBSERVED_PIT"]
    ended=(as_of>=MANIFEST.stop_at or len(seen)==MANIFEST.planned_observations)
    return {
        "study_id":MANIFEST.study_id,
        "stage":"03B3_FINITE_PIT_RESEARCH",
        "engineering_implementation":"REQUIRES_INDEPENDENT_PM_REVIEW",
        "capture_state":("TERMINAL" if ended else "PENDING_FUTURE_WINDOWS"),
        "terminal_evidence_status":(
            "INSUFFICIENT_EVIDENCE" if ended and observed else
            "BLOCKED_DATA" if ended else "PENDING"),
        "predictive_inference":"INSUFFICIENT_EVIDENCE",
        "numeric_trade_authorization":False,
        "observed_pit":observed,"planned":MANIFEST.planned_observations,
        "statuses":counts,"accounted_slots":sum(counts.values()),
        "actual_http_attempts":attempts,
        "maximum_aggregate_session_attempts":MANIFEST.total_slot_attempt_ceiling,
        "separate_bootstrap_attempt_budget":MANIFEST.preselection_attempt_ceiling,
        "selection_evidence_run":MANIFEST.selection_run,
        "universe_sha256":MANIFEST.eligible_universe_sha256,
        "missing_slots":missing,"present_record_count":len(seen),
        "source_publication_times":"UNKNOWN",
        "actual_source_wire_bytes":"NOT_AVAILABLE_IN_LEGACY_JSON_TRANSPORT",
        "raw_parsed_numeric_strings":"STORED_IN_TRANSIENT_ARTIFACTS_ONLY",
        "future_outcomes":None,"fees":None,"slippage":None,
        "limits":[
            "No prediction, threshold, calibrated probability or forward outcome from finite 24h acquisition",
            "No original PIT may be inferred from late re-fetched historical bars",
            "Global cross-run dispatch budget cannot be transactionally enforced without Stage04 owner-approved storage; manual one-run-per-slot governance is mandatory",
            "GitHub Actions artifact retention finite; no permanent independent archive",
            "Clock offset measured, true UTC publisher and clock uncertainty unknown",
        ]}


def collect_directory(directory: str,*,as_of: datetime) -> dict:
    records=[]
    for path in sorted(Path(directory).glob("*.json")):
        with path.open("r",encoding="utf-8") as stream:
            records.append(json.load(stream))
    return terminal_report(records,as_of=as_of)


def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description="03B3 finite 12-slot evidence auditor")
    p.add_argument("--directory",required=True)
    args=p.parse_args(argv)
    print(json.dumps(collect_directory(args.directory,
              as_of=datetime.now(timezone.utc)),sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
