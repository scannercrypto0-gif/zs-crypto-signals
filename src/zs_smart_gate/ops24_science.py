"""B1 original-byte scientific intake. No qualification or invented future labels."""
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from .marketwide_research import FRAMES, packet_from_receipts, evaluate
from .ops24_budget import Hold
from .stage05_contracts import canonical, digest


def intake(root):
    root=Path(root)
    path=root/"result.json"
    if not path.exists():
        return dict(status="NOT_EVALUATED_NO_FULL_SOURCE_DECISION",events=0,
                    up_qualified=False,down_qualified=False,precision=None,recall=None)
    result=json.loads(path.read_bytes())
    if digest(path.read_bytes())!=(root/"result.sha256").read_text().strip():
        raise Hold("SCIENCE_RESULT_HASH_MISMATCH")
    snapshot=json.loads((root/"inventory.private.json").read_bytes())
    if snapshot["snapshot_sha256"]!=result["inventory_id"]:
        raise Hold("SCIENCE_SNAPSHOT_IDENTITY_MISMATCH")
    receipts=[]
    with closing(sqlite3.connect(root/"budget.sqlite")) as db:
        rows=list(db.execute("SELECT key,path,params,state,body_sha,receipt FROM requests ORDER BY key"))
    for key,route,params,state,pin,raw_receipt in rows:
        if state!="COMMITTED":
            continue
        body=(root/(key+".private")).read_bytes()
        if digest(body)!=pin:
            raise Hold("SCIENCE_ORIGINAL_BODY_HASH_MISMATCH")
        receipt=json.loads(raw_receipt)
        if receipt["path"]!=route or receipt["params"]!=json.loads(params) or receipt["body_sha256"]!=pin:
            raise Hold("SCIENCE_RECEIPT_IDENTITY_MISMATCH")
        receipts.append({**receipt,"payload":json.loads(body)})
    counts={direction:Counter() for direction in ("UP","DOWN")}
    events=[]
    for row in result["rows"]:
        if row["state"]!="VALIDATED":
            continue
        item=next(r for r in snapshot["rows"] if r["symbol"]==row["symbol"])
        frames=[]
        for frame in FRAMES:
            matches=[r for r in receipts if r["path"]=="klines"
                     and r["params"].get("symbol")==row["symbol"] and r["params"].get("interval")==frame]
            if len(matches)!=1:
                raise Hold("SCIENCE_FRAME_SOURCE_NOT_UNIQUE")
            frames.extend(matches)
        packet=packet_from_receipts(item,frames,boundary_ms=result["boundary_ms"],
            decision_at=result["decision_at"],scope="PUBLIC_SPOT_CONDITIONAL_RESEARCH",
            clock_status="OPERATIONAL_TIME_ACCEPTED")
        if digest(canonical(packet))!=row["input_sha256"]:
            raise Hold("SCIENCE_FINAL_DECISION_INPUT_MISMATCH")
        recomputed=evaluate(packet)
        if recomputed!=row["directions"]:
            raise Hold("SCIENCE_DIRECTIONAL_REPLAY_MISMATCH")
        for direction in recomputed:
            counts[direction["direction"]][direction["status"]]+=1
        events.append(dict(symbol=row["symbol"],input_sha256=row["input_sha256"],
                           directional_states={r["direction"]:r["status"] for r in recomputed}))
    return dict(schema="zs.ops24.science-source-intake.v1",status="SCIENCE_NOT_APPROVED",
                source_authenticity="SELF_ATTESTED_ORIGINAL_SOURCE_REVIEW_REQUIRED",
                inventory_id=result["inventory_id"],boundary_ms=result["boundary_ms"],
                dataset_sha256=digest(canonical(events)),events=len(events),rows=events,
                counts={k:dict(v) for k,v in counts.items()},up_qualified=False,down_qualified=False,
                dev="SOURCE_REPLAY_ONLY",oos="NOT_OPENED_UNTOUCHED_HOLDOUT_REQUIRED",
                forward="NO_FUTURE_RESULTS_CLAIMED",precision=None,recall=None,calibration=None,
                return_after_costs=None,signals_created=0,
                blockers=["INDEPENDENT_PIT_SOURCE_REVIEW","PRE_REGISTERED_DEV_OOS_FORWARD",
                          "COST_MODEL_AND_SAMPLE_SIZE","INDEPENDENT_DIRECTIONAL_ACCEPTANCE"])


def legacy_research_replay(root, expected_result_sha):
    """A new offline research calculation; never edits original live outcomes."""
    from .ops_windows_time import REVIEWED_POLICY_SHA256
    from .stage05_contracts import parse_utc
    root=Path(root)
    original_bytes=(root/"result.json").read_bytes()
    if digest(original_bytes)!=expected_result_sha:
        raise Hold("LEGACY_SOURCE_RESULT_PIN_MISMATCH")
    original=json.loads(original_bytes)
    if (original["clock"]["status"]!="OPERATIONAL_TIME_ACCEPTED"
            or original["clock"].get("policy_sha256")!=REVIEWED_POLICY_SHA256):
        raise Hold("LEGACY_OPERATIONAL_CLOCK_NOT_RECORDED")
    snapshot=json.loads((root/"snapshot.private.json").read_bytes())
    log=[json.loads(row) for row in (root/"requests.jsonl").read_bytes().splitlines()]
    receipts=[]
    pins=[]
    seen=set()
    for row in log:
        if row["state"]!="RECEIVED":
            continue
        attempt=row["attempt"]
        if type(attempt) is not int or not 1<=attempt<=11 or attempt in seen:
            raise Hold("LEGACY_REQUEST_ID_INVALID_OR_DUPLICATE")
        seen.add(attempt)
        body=(root/("response-"+str(attempt)+".private")).read_bytes()
        if digest(body)!=row["body_sha256"] or row["http_status"]!=200 or len(body)!=row["body_bytes"]:
            raise Hold("LEGACY_ORIGINAL_BODY_NOT_VERIFIED")
        receipts.append(dict(path=row["path"],params=row["params"],received_at=row["received_at"],
                             body_sha256=row["body_sha256"],payload=json.loads(body)))
        pins.append(dict(file="response-"+str(row["attempt"])+".private",sha256=digest(body)))
    if not receipts:
        raise Hold("LEGACY_SOURCE_EMPTY")
    if (snapshot["snapshot_sha256"]!=original["snapshot"]["snapshot_sha256"]
            or digest(canonical(receipts))!=original["receipt_manifest_sha256"]):
        raise Hold("LEGACY_SOURCE_MANIFEST_BINDING_MISMATCH")
    decision=max((r["received_at"] for r in receipts),key=parse_utc)
    boundary=original["boundary_preflight"]["boundary_ms"]
    symbols=sorted({r["params"]["symbol"] for r in receipts if r["path"]=="klines"})
    counts={direction:Counter() for direction in ("UP","DOWN")}
    events=[]
    for symbol in symbols:
        frames=[r for frame in FRAMES for r in receipts if r["path"]=="klines"
                and r["params"].get("symbol")==symbol and r["params"].get("interval")==frame]
        if len(frames)!=4:
            events.append(dict(symbol=symbol,status="INCOMPLETE_FOUR_FRAME_HISTORY"))
            continue
        item=next(row for row in snapshot["rows"] if row["symbol"]==symbol)
        packet=packet_from_receipts(item,frames,boundary_ms=boundary,decision_at=decision,
                 scope="PUBLIC_SPOT_CONDITIONAL_RESEARCH",clock_status="OPERATIONAL_TIME_ACCEPTED")
        outcomes=evaluate(packet)
        for row in outcomes:
            counts[row["direction"]][row["status"]]+=1
        events.append(dict(symbol=symbol,input_sha256=digest(canonical(packet)),directions=outcomes))
    return dict(schema="zs.ops24.legacy-original-research-replay.v1",
        scope="NEW_OFFLINE_CALCULATION_FROM_ORIGINAL_RECORDED_BODIES",
        original_live_result_sha256=expected_result_sha,
        original_live_funnel=original["funnel"],original_live_outcome_unchanged=True,
        decision_definition="MAX_RECORDED_RESPONSE_RECEIPT_NOT_ORIGINAL_RUNTIME_DECISION",
        decision_at=decision,boundary_ms=boundary,source_body_pins=pins,
        clock_evidence="RECORDED_ADMIN_PILOT_SELF_ATTESTED_REVIEW_REQUIRED",
        events=events,counts={key:dict(value) for key,value in counts.items()},
        science="NOT_APPROVED",oos="NOT_EVALUATED",forward="NOT_OBSERVED",
        precision=None,recall=None,calibration=None,return_after_costs=None,signals_created=0)
