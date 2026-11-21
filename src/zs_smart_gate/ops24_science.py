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
