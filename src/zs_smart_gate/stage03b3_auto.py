"""03B3 finite scheduled coordinator for SAME frozen prospective PIT experiment.

Four exact UTC cron anchors on 2026-10-28 only, at most one sequential batch
of three fixed symbols per slot. NOT a recurrent market scanner, not an
exactly-once ledger across separate GitHub Actions runs. Outside a declared
600-second grace window ALL THREE sealed records have 0 actual HTTP attempts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Callable

from .binance_live import get_json
from .core import utc
from .stage03a_contracts import Horizon
from .stage03b2_research import seal_record
from .stage03b3_capture import STAGE, capture_once
from .stage03b3_manifest import MANIFEST
from .stage03b3_terminal import terminal_report

# Exact GitHub Actions cron expressions, all in UTC; fixed to original manifest.
# No additional date/window may be scheduled by runtime heuristics.
SCHEDULE = (
    ("1 14 28 10 *", "I1", Horizon.INTRADAY),
    ("31 14 28 10 *", "I2", Horizon.INTRADAY),
    ("1 16 28 10 *", "S1", Horizon.SWING),
    ("1 20 28 10 *", "S2", Horizon.SWING),
)
DAY = (2026, 10, 28)
PER_BATCH_MAX = 3 * MANIFEST.physical_attempts_per_slot


def resolve_schedule(cron: str) -> tuple[str, Horizon]:
    """Fail closed for unknown/altered event schedules; never guess the slot."""
    if not isinstance(cron, str):
        raise ValueError("UNKNOWN_SCHEDULE_EXPRESSION")
    mapping = {x[0]: (x[1], x[2]) for x in SCHEDULE}
    if cron not in mapping:
        raise ValueError("UNKNOWN_SCHEDULE_EXPRESSION")
    label, horizon = mapping[cron]
    slot = MANIFEST.slot(MANIFEST.assets[0], horizon, label)
    assert slot.label == label
    return label, horizon


def _rejected(symbol: str, horizon: Horizon, label: str, state: str,
              reason: str, *, attempted_paths: tuple[str, ...] = ()) -> dict:
    """A sealed honest missing/late study record; never impersonates a GET."""
    slot = MANIFEST.slot(symbol, horizon, label)
    record = {
        "stage": STAGE,
        "study_id": MANIFEST.study_id,
        "symbol": symbol, "horizon": horizon.value, "slot": label,
        "parent_close_at": slot.close_at.isoformat(),
        "capture_start_at": MANIFEST.start_at.isoformat(),
        "study_stop_at": MANIFEST.stop_at.isoformat(),
        "source_id": MANIFEST.source, "source_publication_at": None,
        "clock_true_uncertainty_ms": None,
        "original_http_wire_bytes_available": False,
        "signal_id": None, "score": None,
        "score_status": "SCORE_UNAVAILABLE",
        "trade_plan_status": "RESEARCH_ONLY", "qualified_signal": False,
        "forward_outcome": None, "historical_eligibility": None,
        "status": state, "reason": reason,
        "telemetry": {
            "physical_http_attempts": len(attempted_paths),
            "http_attempt_budget": MANIFEST.physical_attempts_per_slot,
            "total_study_slot_attempt_ceiling": MANIFEST.total_slot_attempt_ceiling,
            "logical_calls_succeeded": 0,
            "attempt_paths": list(attempted_paths), "http": [],
            "true_clock_uncertainty_ms": None,
        },
    }
    return seal_record(record)


def run_batch(*, cron: str, now: datetime | None = None,
              getter: Callable = get_json,
              clock_ms: Callable[[], float] = lambda: time.time() * 1000,
              monotonic: Callable[[], float] = time.perf_counter) -> dict:
    """Execute only a matching one-time declared batch, with 3 sealed rows.

    Date/time guard runs BEFORE the first call to capture_once/get_json. Each
    actual transport attempt is additionally gated by existing 03B3 capture.
    Injected clock/transport are for deterministic network-free fixtures only.
    """
    label, horizon = resolve_schedule(cron)
    slot = MANIFEST.slot(MANIFEST.assets[0], horizon, label)
    now = utc(now if now is not None else datetime.now(timezone.utc))
    if (now.year, now.month, now.day) != DAY:
        state = "NOT_ATTEMPTED" if now < slot.close_at else "LATE"
        reason = "WRONG_STUDY_UTC_DATE_ZERO_HTTP"
    elif now < slot.close_at:
        state, reason = "NOT_ATTEMPTED", "SCHEDULE_TRIGGERED_BEFORE_PARENT_CLOSE_ZERO_HTTP"
    elif now > slot.close_at + timedelta(seconds=MANIFEST.receipt_grace_seconds) or now >= MANIFEST.stop_at:
        state, reason = "LATE", "SCHEDULE_DELAYED_PAST_FROZEN_GRACE_ZERO_HTTP"
    else:
        state, reason = None, None

    rows = []
    seen = set()
    for symbol in MANIFEST.assets:
        if symbol in seen:
            raise ValueError("DUPLICATE_SYMBOL_IN_FROZEN_BATCH")
        seen.add(symbol)
        if state is not None:
            record = _rejected(symbol, horizon, label, state, reason)
        else:
            # Count accepted outbound attempts independently of capture's own
            # telemetry; if transport unexpectedly throws, do not falsify 0 GET.
            physical_paths = []

            def tracked_getter(path, params=None, *, on_attempt):
                def counted(path_arg):
                    on_attempt(path_arg)  # may reject BEFORE outbound transport
                    physical_paths.append(path_arg)
                return getter(path, params, on_attempt=counted)

            try:
                record = capture_once(
                    symbol=symbol, horizon=horizon, slot_label=label,
                    getter=tracked_getter, local_ms=clock_ms, monotonic=monotonic,
                )
                if record["telemetry"]["physical_http_attempts"] != len(physical_paths):
                    raise ValueError("PHYSICAL_ATTEMPT_ACCOUNTING_MISMATCH")
            except Exception as exc:
                record = _rejected(
                    symbol, horizon, label, "FAILED",
                    "UNEXPECTED_CAPTURE_ERROR_" + type(exc).__name__,
                    attempted_paths=tuple(physical_paths))
        rows.append(record)

    if tuple(r["symbol"] for r in rows) != MANIFEST.assets or len(rows) != 3:
        raise ValueError("NOT_EXACTLY_THREE_FROZEN_ASSETS")
    attempts = sum(r["telemetry"]["physical_http_attempts"] for r in rows)
    if attempts > PER_BATCH_MAX:
        raise ValueError("BATCH_PHYSICAL_ATTEMPT_LIMIT_EXCEEDED")
    audit = terminal_report(rows, as_of=now)
    return {
        "stage": "03B3_FINITE_AUTO_CAPTURE_BATCH",
        "study_id": MANIFEST.study_id,
        "cron": cron, "slot": label, "horizon": horizon.value,
        "invocation_at": now.isoformat(),
        "symbols": list(MANIFEST.assets),
        "states": {r["symbol"]: r["status"] for r in rows},
        "http_attempts": attempts,
        "batch_http_limit": PER_BATCH_MAX,
        "full_study_http_limit": MANIFEST.total_slot_attempt_ceiling,
        "source_inference": "PIT_ONLY_IF_ORIGINAL_POSTCLOSE_RECEIPTS_PROVEN",
        "scientific_conclusion": "INSUFFICIENT_EVIDENCE",
        "audit": audit, "rows": rows,
    }


def emit_artifacts(batch: dict, directory: str) -> None:
    """Exclusive file creation; fail rather than silently overwriting prior rows."""
    dest = Path(directory)
    dest.mkdir(parents=True, exist_ok=False)
    for row in batch["rows"]:
        path = dest / (row["symbol"] + "_" + batch["slot"] + ".json")
        with path.open("x", encoding="utf-8") as stream:
            json.dump(row, stream, sort_keys=True, ensure_ascii=True)
            stream.write("\n")
    with (dest / "batch-summary.txt").open("x", encoding="utf-8") as stream:
        json.dump({k:v for k,v in batch.items() if k!="rows"}, stream,
                  sort_keys=True, ensure_ascii=True)
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="03B3 one-shot GitHub scheduled capture; no manual replay")
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument("--cron", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    if not args.scheduled:
        parser.error("EXPLICIT_SCHEDULED_MODE_REQUIRED")
    if (os.environ.get("GITHUB_EVENT_NAME") != "schedule"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"):
        parser.error("ORIGINAL_MAIN_SCHEDULE_EVENT_ONLY_NO_RERUN")
    result = run_batch(cron=args.cron)
    emit_artifacts(result, args.output_dir)
    print(json.dumps({k:v for k,v in result.items() if k not in ("rows","audit")},
                     sort_keys=True))
    # A blocked/missing data sample is not a programming failure. Keep all
    # evidence rows and report actual per-symbol status even when non-PIT.
    return 0


if __name__ == "__main__":
    sys.exit(main())
