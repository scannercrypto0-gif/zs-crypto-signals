"""03B2 competing pure descriptive features and non-optimizing frozen cohort summary.

No thresholds, V2 total, forward labels, probabilities, trade economics or
backtests. Historical re-fetch is retrospective observation, not PIT replay.
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
from statistics import median
from typing import Sequence

from .core import decimal, utc
from .mtf_contracts import CandleWindow
from .research_metrics import describe
from .stage03a_contracts import Direction
from .stage03b2_manifest import MANIFEST, Partition, StudyManifest, RETROSPECTIVE_EVIDENCE


def frozen_hash(payload: object) -> str:
    """Digest exact reproducible JSON value (not a proof of publication time)."""
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
                     allow_nan=False)
    return sha256(raw.encode("utf-8")).hexdigest()


def competing_features(parent: CandleWindow, children: Sequence[CandleWindow],
                       *, direction: Direction, decision_at) -> dict:
    """One already-reconciled exact parent and children; no score construction."""
    if not isinstance(direction, Direction) or not children:
        raise ValueError("DIRECTION_AND_COMPLETE_CHILDREN_REQUIRED")
    if parent.errors_at(decision_at) or any(
        bar.errors_at(decision_at) or bar.source_id != parent.source_id for bar in children
    ):
        raise ValueError("RESEARCH_FEATURE_PIT_INPUT_INVALID")
    originals = describe(parent, children, direction=direction, decision_at=decision_at)
    by_name = {m.name: m for m in originals}
    sign = Decimal(1) if direction is Direction.UP else Decimal(-1)
    net = sign * (children[-1].close - children[0].open)
    # Complement the existing sum(abs(child body)) definition with a gap-aware
    # path: first candle body plus all subsequent previous-close→current-close
    # differences; no silent assumption about crypto bar continuity.
    path_gap_aware = abs(children[0].close - children[0].open) + sum(
        (abs(c.close - p.close) for p,c in zip(children, children[1:])), Decimal(0))
    total_base = sum((c.base_volume for c in children), Decimal(0))
    total_quote = sum((c.quote_volume for c in children), Decimal(0))
    half = len(children)//2
    base_later = sum((c.base_volume for c in children[half:]), Decimal(0))
    quote_later = sum((c.quote_volume for c in children[half:]), Decimal(0))
    favorable_base = sum((c.base_volume for c in children
                          if sign*(c.close-c.open) > 0), Decimal(0))
    favorable_quote = sum((c.quote_volume for c in children
                           if sign*(c.close-c.open) > 0), Decimal(0))
    denominator = parent.open

    def row(value, unit, basis, *, zero_reason="ZERO_DENOMINATOR") -> dict:
        return {"status": "RESEARCH_METRIC_UNAPPROVED", "value":
                str(value) if value is not None else None, "unit": unit,
                "basis": basis, "missing_reason": zero_reason if value is None else None,
                "source_id": parent.source_id, "source_close_at": parent.close_at.isoformat(),
                "available_at": max(c.available_at for c in (parent, *children)).isoformat()}

    data = {
        "DIRECTIONAL_CLOSE_LOCATION": by_name["DIRECTIONAL_PARENT_CLOSE_LOCATION"].as_dict(),
        "SIGNED_BODY_RANGE": by_name["SIGNED_PARENT_BODY_FRACTION"].as_dict(),
        "ADVERSE_WICK_RANGE": by_name["ADVERSE_WICK_FRACTION"].as_dict(),
        "NET_OVER_BODY_PATH": by_name["SIGNED_CHILD_NET_TO_PATH"].as_dict(),
        "NET_OVER_GAP_AWARE_PATH": row(net/path_gap_aware if path_gap_aware > 0 else None,
                                       "signed_ratio", "signed_net / (first_abs_body + sum(abs(child_close - previous_child_close)))"),
        "SECOND_HALF_BASE_SHARE": row(base_later/total_base if total_base > 0 else None,
                                      "fraction_0_1", "second_half_base / total_base"),
        "SECOND_HALF_QUOTE_SHARE": row(quote_later/total_quote if total_quote > 0 else None,
                                       "fraction_0_1", "second_half_quote / total_quote"),
        "FAVORABLE_BASE_SHARE": row(favorable_base/total_base if total_base > 0 else None,
                                    "fraction_0_1", "direction_favorable_body_base / total_base"),
        "FAVORABLE_QUOTE_SHARE": row(favorable_quote/total_quote if total_quote > 0 else None,
                                     "fraction_0_1", "direction_favorable_body_quote / total_quote"),
        "BASELINE_SIGNED_OC_PCT": row(
            sign*Decimal(100)*(parent.close-parent.open)/denominator if denominator > 0 else None,
            "percent", "direction*(parent_close-parent_open)*100/parent_open"),
        "BASELINE_PARENT_BASE_VOLUME": row(parent.base_volume, "base_asset_units", "untransformed_parent_base"),
        "BASELINE_PARENT_QUOTE_VOLUME": row(parent.quote_volume, "quote_asset_units", "untransformed_parent_quote"),
    }
    return data


def seal_record(record: dict) -> dict:
    """Prevent untracked in-memory revision of a returned study row."""
    payload = {k:v for k,v in record.items() if k != "evidence_sha256"}
    return {**payload, "evidence_sha256": frozen_hash(payload)}


def compare_study(records: Sequence[dict], manifest: StudyManifest = MANIFEST) -> dict:
    """Compute descriptive distributions, never train/tune/select on holdout.

    A future review MUST reconstruct raw data with source receipt evidence.
    One sample/window cannot support estimates of model performance.
    """
    if type(records) not in (tuple, list):
        raise ValueError("RECORDS_MUST_BE_FIXED_COLLECTION")
    seen = set()
    valid = []
    rejected = []
    asset_map = {a.symbol:a.declared_cohort for a in manifest.assets}
    window_map = {(w.partition.value,w.close_at.isoformat()):w for w in manifest.windows}
    for index, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise ValueError("INVALID_STUDY_RECORD")
        digest = rec.get("evidence_sha256")
        if not isinstance(digest,str) or digest != frozen_hash(
            {k:v for k,v in rec.items() if k != "evidence_sha256"}):
            raise ValueError("STUDY_EVIDENCE_TAMPER_OR_REVISION")
        if rec.get("study_id") != manifest.study_id:
            raise ValueError("STUDY_MANIFEST_MISMATCH")
        key = (rec.get("symbol"),rec.get("horizon"),rec.get("partition"))
        if key in seen:
            raise ValueError("DUPLICATE_FROZEN_STUDY_SESSION")
        seen.add(key)
        if (key[0] not in asset_map or key[1] not in
                [h.value for h in manifest.horizons] or
                (key[2], rec.get("parent_close_at")) not in window_map):
            raise ValueError("STUDY_SESSION_OR_TIME_SPLIT_LEAKAGE")
        if rec.get("retrospective_assumption") != RETROSPECTIVE_EVIDENCE:
            raise ValueError("HISTORICAL_PIT_PROOF_INVENTED")
        if rec.get("status") != "OBSERVED_EXACT_RECONCILIATION":
            rejected.append({"session": key, "reason": rec.get("reason","NOT_OBSERVED")})
            continue
        if not rec.get("retrieved_at") or not rec.get("source_payload_sha256"):
            raise ValueError("MISSING_RETRIEVAL_PROVENANCE")
        if utc(__import__("datetime").datetime.fromisoformat(rec["retrieved_at"])) <= utc(
            __import__("datetime").datetime.fromisoformat(rec["parent_close_at"])):
            raise ValueError("RETROSPECTIVE_RETRIEVAL_TIME_INVALID")
        if rec.get("source_publication_at") is not None or rec.get("historical_eligibility") is not None:
            raise ValueError("FABRICATED_HISTORICAL_SOURCE_OR_ELIGIBILITY")
        metrics = rec.get("features")
        if not isinstance(metrics,dict) or set(metrics) != {"UP","DOWN"}:
            raise ValueError("MISSING_DIRECTIONAL_RESEARCH_FEATURES")
        valid.append(rec)

    samples = {}
    for partition in Partition:
        for horizon in manifest.horizons:
            for direction in manifest.directions:
                for asset in manifest.assets:
                    group = [r for r in valid if (r["partition"],r["horizon"],r["symbol"]) ==
                             (partition.value,horizon.value,asset.symbol)]
                    name = "|".join((partition.value,horizon.value,direction.value,asset.declared_cohort))
                    vals = {}
                    if group:
                        for feature_name, feature in group[0]["features"][direction.value].items():
                            value = feature.get("value")
                            vals[feature_name] = None if value is None else str(decimal(value))
                    samples[name] = {"n_windows":len(group),"feature_values":vals}
    expected = manifest.planned_sessions
    return {"study_id":manifest.study_id,
            "status":"INSUFFICIENT_EVIDENCE",
            "independent_predictive_evidence":False,
            "observed_sessions":len(valid),
            "failed_or_missing_sessions":expected-len(valid),
            "expected_sessions":expected,
            "observed_by_partition":{p.value:sum(r["partition"]==p.value for r in valid)
                                     for p in Partition},
            "rejected":rejected,
            "descriptive_strata":samples,
            "forward_outcomes":None,"fees":None,"slippage":None,
            "predictive_probability":None,"approved_threshold":None,
            "notes":[
                "Development and strictly later holdout reported separately without tuning",
                "UP/DOWN rows are paired descriptions of the same candle, NOT independent observations",
                "Historical source publication/eligibility/real-time decision snapshots unavailable",
                "Sample is sparse and deliberately non-representative; no success-rate inference",
                "Historical re-fetch receipt is present-time only and cannot backfill past PIT",
                "Raw payload hash provides integrity checksum, not independent archiving or source timestamp",
            ]}
