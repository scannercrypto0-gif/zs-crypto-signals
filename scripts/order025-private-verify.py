"""ORDER-025 private, read-only verification of an EXISTING ORDER-022 run.

No network, new data acquisition, real-time feeds, execution, or parameter
changes. Independent price/volume event arithmetic is implemented here rather
than using the historical evaluator; archive CSV parsing is shared and this
fact is disclosed. Redacted output only; neither original ZIP nor SQLite
source bytes are included in its contents.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import sys

from zs_smart_gate.setup021 import CONFIG_SHA256
from zs_smart_gate.stage03_order022 import (
    MONTHS, PROTOCOL_PATH, SYMBOLS, ResearchBlocked, canonical, digest,
    evaluate_rows, file_sha, filename, phase_for, read_month_zip,
    read_protocol, sha_bytes,
)

EXPECTED_REPORT_SHA = "985abecf489ea23d1e46f9aace7152df8cf997cd94cce33dde440bdb34cea5ee"
PERIOD = 300000


def locally_computed_condition(window):
    """Separate expression and branch logic; 21 closed bars, no future."""
    if len(window) != 21:
        raise ResearchBlocked("AUDITOR_PREDICATE_NEEDS_21_BARS")
    earlier, this = window[:20], window[20]
    volume = sum((b.quote_volume for b in earlier), Decimal(0))
    if volume <= 0:
        raise ResearchBlocked("AUDITOR_VOLUME_BASELINE_UNKNOWN")
    return (this.close > max(b.high for b in earlier)
            and this.close > this.open
            and this.quote_volume * 20 >= Decimal("1.20") * volume)


def independent_count(bars, protocol):
    """Separate counter implementation; shares the existing checked CSV parser.

    Distinct counters per phase; no DEV bars enter OOS predicate or labels.
    """
    counts = {phase: Counter() for phase in ("DEV", "OOS")}
    embargo_index = {phase: -1 for phase in ("DEV", "OOS")}
    for i in range(21, len(bars)):
        phase = phase_for(bars[i].start, protocol)
        if phase is None:
            continue
        w = bars[i-21:i+1]
        if any(phase_for(b.start, protocol) != phase for b in w):
            continue
        if any(a.end != b.start for a, b in zip(w, w[1:])):
            continue
        try:
            before = locally_computed_condition(w[:21])
            after = locally_computed_condition(w[1:])
        except ResearchBlocked:
            continue
        if before or not after:
            continue
        outcome = counts[phase]
        outcome["raw"] += 1
        if i <= embargo_index[phase]:
            outcome["suppressed"] += 1
            continue
        embargo_index[phase] = i + 11
        outcome["admitted"] += 1
        if i + 12 >= len(bars):
            outcome["missing"] += 1
            continue
        following = bars[i:i+13]
        if (phase_for(bars[i+12].start, protocol) != phase or
                any(a.end != b.start for a, b in zip(following, following[1:]))):
            outcome["missing"] += 1
            continue
        if bars[i+12].close > bars[i].close:
            outcome["up"] += 1
        else:
            outcome["not_up"] += 1
    return counts


def read_existing_journal(path):
    if not path.is_file():
        raise ResearchBlocked("PRIVATE_JOURNAL_NOT_FOUND")
    uri = path.resolve().as_uri() + "?mode=ro"
    # sqlite3.Connection.__exit__ commits/rolls back; it does NOT close.
    # Explicit close is required to release the DB file on Windows.
    with closing(sqlite3.connect(uri, uri=True)) as con:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ResearchBlocked("PRIVATE_JOURNAL_INTEGRITY_FAILED")
        rows = con.execute("SELECT id, sha256, payload FROM reports ORDER BY id").fetchall()
    result = {}
    for key, sha, blob in rows:
        if sha_bytes(blob) != sha:
            raise ResearchBlocked("PRIVATE_JOURNAL_PAYLOAD_HASH_MISMATCH")
        result[key] = json.loads(blob)
    if len(rows) != len(result):
        raise ResearchBlocked("PRIVATE_JOURNAL_DUPLICATED_KEY")
    return result


def private_audit(root, expected_report_sha=EXPECTED_REPORT_SHA):
    root = Path(root).resolve(strict=True)
    required = [
        "private-run-receipt.json", "frozen-experiment.json",
        "historical-price-only-report.json", "research-results.sqlite",
        "verified-restore.sqlite",
    ]
    for name in required:
        if not (root/name).is_file():
            raise ResearchBlocked("REQUIRED_PRIVATE_INPUT_MISSING:" + name)

    report_bytes = (root/"historical-price-only-report.json").read_bytes()
    report_sha = sha_bytes(report_bytes)
    receipt = json.loads((root/"private-run-receipt.json").read_bytes())
    manifest_raw = (root/"frozen-experiment.json").read_bytes()
    manifest = json.loads(manifest_raw)
    report = json.loads(report_bytes)
    protocol, protocol_sha = read_protocol()
    if (report_sha != expected_report_sha or
            receipt.get("result_report_sha256") != report_sha):
        raise ResearchBlocked("PRIVATE_REPORT_SHA_MISMATCH")
    if (manifest.get("protocol_sha256") != protocol_sha or
            report.get("protocol_sha256") != protocol_sha):
        raise ResearchBlocked("FROZEN_PROTOCOL_SHA_MISMATCH")
    if (manifest.get("setup_contract_sha256") != CONFIG_SHA256 or
            report.get("setup_contract_sha256") != CONFIG_SHA256):
        raise ResearchBlocked("FROZEN_SETUP_VERSION_MISMATCH")
    if (manifest.get("source_kind") != "REAL_ARCHIVE_PRIVATE" or
            report.get("source_kind") != "REAL_ARCHIVE_PRIVATE"):
        raise ResearchBlocked("REAL_ARCHIVE_PROVENANCE_REQUIRED")
    if (sha_bytes(manifest_raw) != receipt.get("frozen_manifest_sha256") or
            sha_bytes(manifest_raw) != report.get("manifest_sha256")):
        raise ResearchBlocked("FROZEN_MANIFEST_SHA_MISMATCH")
    if (manifest.get("module_sha256") != file_sha(
            Path(__file__).resolve().parents[1]/"src/zs_smart_gate/stage03_order022.py") or
            manifest.get("setup_module_sha256") != file_sha(
            Path(__file__).resolve().parents[1]/"src/zs_smart_gate/setup021.py")):
        raise ResearchBlocked("ORIGINAL_ENGINE_OR_SETUP_SOURCE_CHANGED")
    if (report.get("publishable") is not False or
            report.get("stage05") != "FULL_HOLD" or
            report.get("historical_pit") != "HISTORICAL_REPLAY_PIT_UNVERIFIED" or
            report.get("market_requests") != 0):
        raise ResearchBlocked("PRIVATE_RESEARCH_ONLY_INVARIANT_FAILED")

    expected = {(s, m) for s in SYMBOLS for m in MONTHS}
    listing = manifest.get("archives")
    if not isinstance(listing, list) or len(listing) != 12:
        raise ResearchBlocked("FROZEN_SOURCE_COUNT_INVALID")
    actual_pairs = {(entry.get("symbol"), entry.get("month")) for entry in listing}
    if actual_pairs != expected:
        raise ResearchBlocked("FROZEN_SOURCE_SCOPE_INVALID")
    pinned = {(e["symbol"],e["month"]):e for e in listing}
    independent = {}
    list_shas = {}
    for symbol in SYMBOLS:
        all_bars = []
        for month in MONTHS:
            e = pinned[symbol,month]
            if e.get("name") != filename(symbol,month):
                raise ResearchBlocked("FROZEN_ARCHIVE_NAME_INVALID")
            source = root/"verified_5m_archives"/e["name"]
            if not source.is_file() or file_sha(source) != e.get("sha256"):
                raise ResearchBlocked("FROZEN_ZIP_NOT_REPRODUCIBLE:" + e["name"])
            bars, _ = read_month_zip(source,symbol,month)
            all_bars.extend(bars)
        if any(a.start >= b.start for a,b in zip(all_bars,all_bars[1:])):
            raise ResearchBlocked("FROZEN_ARCHIVES_TIME_NOT_STRICT")
        result = independent_count(all_bars, protocol)
        # Extra cross-check event list SHA using accepted existing evaluator;
        # independent counts themselves do NOT call evaluate_rows().
        _, accepted_events = evaluate_rows(all_bars,symbol,protocol,"REAL_ARCHIVE_PRIVATE")
        for phase in ("DEV","OOS"):
            key = f"{symbol}:{phase}"
            row = report["partition_results"].get(key)
            if not isinstance(row,dict):
                raise ResearchBlocked("PRIVATE_PARTITION_REPORT_MISSING:"+key)
            c = result[phase]
            checks = {
                "partial_price_volume_patterns": c["raw"],
                "outcome_overlap_suppressed": c["suppressed"],
                "partial_event_count": c["admitted"],
                "future_price_up_12": c["up"],
                "future_price_not_up_12": c["not_up"],
                "outcome_label_availability": c["up"]+c["not_up"],
            }
            for field, value in checks.items():
                recorded = row["counts"].get(field,0) if field in (
                    "partial_price_volume_patterns","outcome_overlap_suppressed"
                    ) else row.get(field)
                if recorded != value:
                    raise ResearchBlocked("INDEPENDENT_REPLAY_COUNT_MISMATCH:"+key+":"+field)
            if (c["raw"] != c["suppressed"]+c["admitted"] or
                    c["admitted"] != c["up"]+c["not_up"]+c["missing"]):
                raise ResearchBlocked("INDEPENDENT_ARITHMETIC_FAILED:"+key)
            stored_digest = report["event_list_sha256"].get(key)
            if stored_digest != digest(accepted_events[phase]):
                raise ResearchBlocked("FROZEN_EVENT_LIST_SHA_MISMATCH:"+key)
            independent[key] = {
                "raw_patterns":c["raw"],"overlap_suppressed":c["suppressed"],
                "admitted_partial_events":c["admitted"],
                "future_up":c["up"],"future_not_up":c["not_up"],
                "future_unavailable":c["missing"],
                "price_up_fraction": (
                    f"{Decimal(c['up']) / Decimal(c['up']+c['not_up']):.6f}"
                    if c["up"]+c["not_up"] else None),
                "statistical_status":"DESCRIPTIVE_ONLY_NOT_PIT_OR_EXECUTABLE",
            }
            list_shas[key] = stored_digest

    persisted = read_existing_journal(root/"research-results.sqlite")
    restored = read_existing_journal(root/"verified-restore.sqlite")
    if persisted != restored or set(persisted) != set(independent):
        raise ResearchBlocked("PRIVATE_SQLITE_RESTORE_NOT_EQUAL")
    for key, stored in persisted.items():
        if stored != report["partition_results"][key]:
            raise ResearchBlocked("PRIVATE_SQLITE_REPORT_MISMATCH:"+key)
    if (digest([persisted[k] for k in sorted(persisted)]) !=
            report["journal_readback_and_restore"]["rows_sha256"]):
        raise ResearchBlocked("PRIVATE_SQLITE_SET_DIGEST_MISMATCH")

    return {
        "order":"ORDER-025", "status":"PRIVATE_OFFLINE_ARITHMETIC_REPRODUCED",
        "report_sha256":report_sha,
        "frozen_manifest_sha256":sha_bytes(manifest_raw),
        "protocol_sha256":protocol_sha,
        "setup_contract_sha256":CONFIG_SHA256,
        "source_zip_sha256_verified":12,
        "reproduction_method":"SEPARATE_PRICE_VOLUME_COUNTER_SHARED_ARCHIVE_PARSER",
        "partition_counts":independent,"event_list_sha256":list_shas,
        "sqlite_report_restore":"MATCHES_ORIGINAL_PRIVATE_JOURNAL",
        "source_provenance":"PRIOR_PRIVATE_HASHES_NOT_PUBLICATION_RECEIPTS",
        "publisher_receipt":"UNVERIFIED",
        "historical_pit":"HISTORICAL_REPLAY_PIT_UNVERIFIED",
        "historical_bid_ask_24h":"NOT_AVAILABLE",
        "qualified_full_setup":"NOT_PROVABLE",
        "statistical_qualification":"BLOCKED",
        "market_requests":0,"publishable":False,"stage05":"FULL_HOLD",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-run-dir",required=True)
    parser.add_argument("--expected-report-sha",default=EXPECTED_REPORT_SHA)
    parser.add_argument("--output",required=True)
    opts = parser.parse_args()
    try:
        data = private_audit(opts.private_run_dir, opts.expected_report_sha)
        path = Path(opts.output)
        if path.exists():
            raise ResearchBlocked("REDACTED_AUDIT_OUTPUT_MUST_BE_FRESH")
        if any((x/".git").exists() for x in (path.parent, *path.parent.parents)):
            raise ResearchBlocked("REDACTED_OUTPUT_MUST_BE_OUTSIDE_GIT")
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("xb") as f:
            f.write(canonical(data)+b"\n")
        print(json.dumps({"status":data["status"],
                          "source_sha256_verified":12,
                          "report_sha256":data["report_sha256"],
                          "market_requests":0},sort_keys=True))
    except (ResearchBlocked,OSError,ValueError,KeyError,TypeError,sqlite3.Error) as exc:
        # Do not spill input content or path into logs.
        message = str(exc)
        code = message.split(":",1)[0]
        print(json.dumps({"status":"AUDIT_BLOCKED","reason":code,
                          "market_requests":0}),file=sys.stderr)
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
