"""Stage12 offline evaluation contracts. Only synthetic computations are enabled."""
from decimal import Decimal, DecimalException, localcontext
from datetime import timedelta
from itertools import groupby
from math import sqrt

from .stage05_contracts import ContractError, canonical, digest, parse_utc

VERSION = "zs.stage12.predictive-research.v1"
PARTITIONS = ("DEV", "OOS", "FORWARD")
FRAMES = {"Intraday": ("15m", "30m"), "Swing": ("1h", "4h", "8h")}
LABELS = {"SUCCESS": 1, "FAILURE": 0, "QUIET": 0}
MAX_ROWS = 10000


def decimal(value, minimum=None, maximum=None):
    if not isinstance(value, str):
        raise ContractError("S12_DECIMAL_STRING_REQUIRED")
    try:
        n = Decimal(value)
    except DecimalException:
        raise ContractError("S12_INVALID_DECIMAL") from None
    if (not n.is_finite() or (minimum is not None and n < minimum)
            or (maximum is not None and n > maximum)):
        raise ContractError("S12_DECIMAL_OUT_OF_RANGE")
    return n


def require_id(value):
    if not isinstance(value, str) or not value.strip():
        raise ContractError("S12_ID_REQUIRED")


def validate_dataset(dataset, registration, registration_pin, dataset_pin):
    if digest(canonical(registration)) != registration_pin:
        raise ContractError("S12_REGISTRATION_PIN_MISMATCH")
    if digest(canonical(dataset)) != dataset_pin:
        raise ContractError("S12_DATASET_PIN_MISMATCH")
    if dataset["registration_sha256"] != registration_pin:
        raise ContractError("S12_REGISTRATION_LINK_MISMATCH")
    require_id(dataset["dataset_id"])
    source = dataset["source_id"]
    if not isinstance(source, str) or not source.startswith("SYNTHETIC:") or source == "SYNTHETIC:":
        raise ContractError("S12_SYNTHETIC_SOURCE_REQUIRED")
    if dataset["coverage"] != "COMPLETE_SYNTHETIC_FIXTURE":
        raise ContractError("S12_COVERAGE_REQUIRED")
    frozen = parse_utc(dataset["frozen_at"])
    registered = parse_utc(registration["registered_at"])
    if not registered < frozen:
        raise ContractError("S12_REGISTRATION_TIME_INVALID")
    for field in ("hypothesis_id", "baseline_id", "quiet_definition", "success_definition",
                  "failure_definition", "multiplicity_policy"):
        require_id(registration[field])
    windows = {}
    for key in PARTITIONS:
        start, end = (parse_utc(registration["partitions"][key][k]) for k in ("start", "end"))
        if not registered <= start < end <= frozen or (windows and start < next(reversed(windows.values()))[1]):
            raise ContractError("S12_PARTITION_OVERLAP_OR_ORDER")
        windows[key] = (start, end)
    for field in ("fee_bps_per_side", "slippage_bps_per_side"):
        decimal(registration["costs"][field], 0, 10000)
    threshold = decimal(registration["fixture_threshold"], 0, 1)
    rows = dataset["rows"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise ContractError("S12_BOUNDED_ROWS_REQUIRED")
    if type(dataset["row_count"]) is not int or dataset["row_count"] != len(rows):
        raise ContractError("S12_ROW_COUNT_MISMATCH")
    seen = set()
    event_origins = {}
    scopes = {field: set() for field in ("asset", "year", "regime")}
    for row in rows:
        scope, frame = row["horizon"], row["frame"]
        if (scope not in FRAMES or frame not in FRAMES[scope] or row["version"] not in ("V1","V2")
                or row["setup"] not in ("CONTINUATION","REVERSAL") or row["direction"] not in ("UP","DOWN")):
            raise ContractError("S12_COHORT_INVALID")
        period = row["horizon_length"]
        if type(period) is not int or not 1 <= period <= (24 if scope == "Intraday" else 30):
            raise ContractError("S12_HORIZON_INVALID")
        horizon = timedelta(hours=period) if scope == "Intraday" else timedelta(days=period)
        feature, received, available, decision, label_end, finalized = (
            parse_utc(row[k]) for k in ("feature_at","received_at","available_at","decision_at",
                                       "label_end_at","label_final_at"))
        if row["source_id"] != source or not feature <= received <= available <= decision:
            raise ContractError("S12_SOURCE_OR_FEATURE_PIT_INVALID")
        start, end = windows[row["partition"]]
        if not start <= decision < label_end == decision+horizon <= finalized < end:
            raise ContractError("S12_LABEL_IMMATURE_OR_CROSSES_PARTITION")
        require_id(row["event_id"])
        event = row["event_id"]
        origin = (row["partition"], row["asset"], decision)
        if event_origins.setdefault(event, origin) != origin:
            raise ContractError("S12_EVENT_ORIGIN_CONFLICT")
        identity = (event, row["version"], scope, frame, period, row["setup"], row["direction"])
        if identity in seen:
            raise ContractError("S12_DUPLICATE_EVENT")
        seen.add(identity)
        if row["label"] not in LABELS:
            raise ContractError("S12_LABEL_INVALID")
        if type(row["year"]) is not int or row["year"] != decision.year:
            raise ContractError("S12_YEAR_INVALID")
        for field in ("asset","regime"):
            require_id(row[field])
        for field in scopes:
            scopes[field].add(row[field])
        for field in ("baseline_probability_fixture","model_probability_fixture"):
            decimal(row[field], 0, 1)
        for field in ("mae", "mfe"):
            decimal(row[field], 0)
        for field in ("lead_seconds","persistence_seconds"):
            if row[field] is not None:
                decimal(row[field], 0, Decimal(str(horizon.total_seconds())))
    for field, actual in scopes.items():
        declared = dataset["scope"][field]
        if not isinstance(declared, list) or len(set(declared)) != len(declared) or set(declared) != actual:
            raise ContractError("S12_DATASET_SCOPE_MISMATCH")
    return rows, threshold


def wilson(hits, count):
    if not count:
        return None
    z = 1.959963984540054
    p = hits / count
    denominator = 1 + z*z/count
    center = (p + z*z/(2*count))/denominator
    radius = z*sqrt((p*(1-p) + z*z/(4*count))/count)/denominator
    return [max(0.0, center-radius), min(1.0, center+radius)]


def probability_metrics(pairs, threshold):
    positives = sum(label for _, label in pairs)
    tp = sum(label for score, label in pairs if score >= threshold)
    calls = sum(score >= threshold for score, _ in pairs)
    # Step-integrated PR curve with tied scores advanced together.
    ordered = sorted(pairs, reverse=True)
    count = hits = 0
    area = Decimal(0)
    for _, group in groupby(ordered, key=lambda pair: pair[0]):
        labels = [label for _, label in group]
        gain = sum(labels)
        count += len(labels)
        hits += gain
        if positives:
            area += Decimal(gain)/positives * Decimal(hits)/count
    calibration = []
    for index in range(5):
        bucket = [(score,label) for score,label in pairs if min(4,int(score*5)) == index]
        if bucket:
            size = len(bucket)
            calibration.append({"bin":index, "count":size,
                "mean_probability":str(sum(score for score,_ in bucket)/size),
                "observed_fraction":str(Decimal(sum(label for _,label in bucket))/size)})
    return {"pr_auc_step":str(area) if positives else None,
            "brier":str(sum((score-label)**2 for score,label in pairs)/len(pairs)),
            "precision":str(Decimal(tp)/calls) if calls else None,
            "recall":str(Decimal(tp)/positives) if positives else None,
            "calibration":calibration,
            "precision_wilson_95_iid_fixture":wilson(tp,calls),
            "recall_wilson_95_iid_fixture":wilson(tp,positives)}


def evaluate_research(dataset, *, registration=None, registration_sha256=None, dataset_sha256=None):
    blocked = {"schema":VERSION, "status":"BLOCKED_REAL_DATA_NOT_VERIFIED",
               "scientific_metrics":"NOT_EVALUATED", "signal_id":None, "trading_authorized":False}
    if not isinstance(dataset, dict) or dataset.get("source_scope") != "SYNTHETIC_TEST_ONLY":
        return blocked
    try:
        with localcontext() as ctx:
            ctx.prec = 34
            rows, threshold = validate_dataset(dataset, registration, registration_sha256, dataset_sha256)
            groups = {}
            for row in rows:
                key = tuple(row[field] for field in ("partition","version","horizon","frame",
                                                      "horizon_length","setup","direction"))
                groups.setdefault(key, []).append(row)
            reports = []
            for cohort, group in sorted(groups.items()):
                summary = {}
                for key in ("lead_seconds","persistence_seconds","mae","mfe"):
                    values = [Decimal(row[key]) for row in group if row[key] is not None]
                    summary[key] = {"count":len(values), "mean":str(sum(values)/len(values)) if values else None}
                reports.append({"cohort":list(cohort), "count":len(group),
                    "scope_counts": {field: [
                        {"value": value, "count": sum(row[field] == value for row in group)}
                        for value in sorted({row[field] for row in group})
                    ] for field in ("asset", "year", "regime")},
                    "baseline":probability_metrics([(Decimal(r["baseline_probability_fixture"]), LABELS[r["label"]])
                                                    for r in group], threshold),
                    "model_fixture":probability_metrics([(Decimal(r["model_probability_fixture"]), LABELS[r["label"]])
                                                         for r in group], threshold), "outcomes":summary})
    except ContractError:
        raise
    except (KeyError, TypeError, ValueError, DecimalException):
        raise ContractError("S12_MALFORMED_DATASET_OR_REGISTRATION") from None
    return {**blocked, "status":"SYNTHETIC_FIXTURE_EVALUATED", "dataset_sha256":dataset_sha256,
            "registration_sha256":registration_sha256, "fixture_metrics":reports}


def research_plan(candidate_id, direction, proposal=None, *, source=None, decision_at=None):
    require_id(candidate_id)
    blocked = {"candidate_id":candidate_id, "status":"UNVERIFIED_PLAN", "levels":None,
               "signal_id":None, "trading_authorized":False}
    if proposal is None or not isinstance(source, str) or not source.startswith("SYNTHETIC:"):
        return blocked
    try:
        decision = parse_utc(decision_at)
        if direction not in ("UP","DOWN") or proposal["source_scope"] != "SYNTHETIC_TEST_ONLY":
            return blocked
        for key in ("structure","volatility","execution_risk","costs"):
            evidence = proposal[key]
            require_id(evidence["evidence_id"])
            if (evidence["source_id"] != source or not
                    parse_utc(evidence["event_at"]) <= parse_utc(evidence["available_at"]) <= decision):
                return blocked
        costs = proposal["costs"]
        for key in ("fee_bps_per_side", "slippage_bps_per_side"):
            decimal(costs[key], 0, 10000)
        low, high = (decimal(p, 0) for p in proposal["entry_zone"])
        stop = decimal(proposal["stop"], 0)
        first, second, third = (decimal(p, 0) for p in proposal["targets"])
        ordered = stop < low <= high < first < second < third if direction == "UP" else (
            stop > high >= low > first > second > third)
        if not ordered or min(stop, low, high, first, second, third) <= 0:
            return blocked
    except (KeyError, ValueError, TypeError, DecimalException):
        return blocked
    return {**blocked, "status":"SYNTHETIC_HYPOTHESIS_ONLY", "levels":{
        "entry_zone":[str(low),str(high)], "stop":str(stop),
        "targets":[str(first),str(second),str(third)]}}
