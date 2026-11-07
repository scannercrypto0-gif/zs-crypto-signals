"""Synthetic-only local callback timestamp/scheduler-window observation.

No network, NTS probe, system clock adjustment, market access or authorization.
Finite samples cannot establish a worst-case time bound for future arrivals.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from queue import Queue
import statistics
import sys
from threading import Thread
import time


class CalibrationBlocked(ValueError):
    pass


def assess(observed_ns: list[int], *, margin_ns: int) -> dict:
    if not observed_ns or not isinstance(margin_ns, int) or margin_ns <= 0:
        raise CalibrationBlocked("INVALID_SAMPLE_OR_MARGIN")
    if any(type(v) is not int or v < 0 for v in observed_ns):
        raise CalibrationBlocked("INVALID_MONOTONIC_DELAY")
    high = max(observed_ns)
    if high >= margin_ns:
        raise CalibrationBlocked("OBSERVED_DELAY_AT_OR_ABOVE_ASSUMED_MARGIN")
    ordered = sorted(observed_ns)
    p99 = ordered[(99 * (len(ordered) - 1) + 99) // 100]
    return {
        "observed_samples": len(ordered),
        "min_observed_ns": ordered[0],
        "median_observed_ns": int(statistics.median(ordered)),
        "p99_nearest_rank_observed_ns": p99,
        "max_observed_ns": high,
        "assumed_margin_ns": margin_ns,
        "status": "OBSERVED_SYNTHETIC_WINDOW_BELOW_MARGIN_NOT_A_PROVEN_UPPER_BOUND",
        "independent_utc": False,
        "future_event_pit": "NOT_ATTESTED",
    }


def measure(samples: int, *, margin_ns: int) -> dict:
    if not 16 <= samples <= 10000:
        raise CalibrationBlocked("SAMPLE_COUNT_OUTSIDE_LIMIT")
    q: Queue[int | None] = Queue(maxsize=1)
    ack: Queue[int] = Queue(maxsize=1)
    def worker() -> None:
        for _ in range(samples):
            event_ns = q.get()
            if event_ns is None:
                return
            _wall_utc_ns = time.time_ns()  # untrusted runner UTC stamp
            stamped_ns = time.monotonic_ns()
            ack.put(stamped_ns - event_ns)
    thread = Thread(target=worker, name="synthetic-receiver", daemon=True)
    start_utc_ns = time.time_ns()
    start_mono_ns = time.monotonic_ns()
    thread.start()
    observed = []
    for _ in range(samples):
        # Synthetic callback handoff only. No actual exchange packets or socket receive.
        t0 = time.monotonic_ns()
        q.put(t0)
        observed.append(ack.get())
    thread.join(timeout=5)
    if thread.is_alive():
        raise CalibrationBlocked("SYNTHETIC_CALLBACK_WORKER_STUCK")
    end_mono_ns = time.monotonic_ns()
    end_utc_ns = time.time_ns()
    evaluation = assess(observed, margin_ns=margin_ns)
    return {
        "schema": "zs03.p0.synthetic-runner-stamp-observation.v1",
        "host_kind": "GITHUB_ACTIONS_EPHEMERAL_UBUNTU_DEVELOPMENT",
        "run_id": os.environ.get("GITHUB_RUN_ID", "NOT_GITHUB_ACTIONS"),
        "head_sha": os.environ.get("GITHUB_SHA", "UNKNOWN"),
        "observed_utc_start": datetime.fromtimestamp(
            start_utc_ns / 1e9, timezone.utc).isoformat(),
        "observed_utc_end": datetime.fromtimestamp(
            end_utc_ns / 1e9, timezone.utc).isoformat(),
        "elapsed_monotonic_ns": end_mono_ns - start_mono_ns,
        "wall_clock_minus_monotonic_elapsed_ns": (
            (end_utc_ns - start_utc_ns) - (end_mono_ns - start_mono_ns)),
        "method": "TWO_THREAD_SYNTHETIC_QUEUE_CALLBACK_TIME_TIME_NS_THEN_MONOTONIC_NS",
        "scope": "OBSERVED_SCHEDULING_PLUS_UTC_STAMP_CALL_ON_THIS_RUN_ONLY",
        "not_measured": [
            "KERNEL_NETWORK_INGRESS_AND_SOCKET_READ",
            "BINANCE_PATH_AND_PUBLISHER_EVENT_TIME",
            "SEPARATE_INDEPENDENT_NTS_TIME_AUTHENTICATION",
            "LONG_TAIL_PAUSE_UNDER_OTHER_HOST_LOAD",
            "FUTURE_EVENT_RECEPTION_DECISION_PIT",
        ],
        **evaluation,
    }


def _self_test() -> None:
    assert assess([0, 1_000_000, 50_000_000], margin_ns=100_000_000)["max_observed_ns"] == 50_000_000
    for samples, margin in (([100_000_000], 100_000_000),
                            ([100_000_001], 100_000_000),
                            ([], 100_000_000), ([-1], 100_000_000)):
        try:
            assess(samples, margin_ns=margin)
        except CalibrationBlocked:
            pass
        else:
            raise AssertionError("FAIL_CLOSED_NEGATIVE_SELF_TEST_FAILED")
    print("SYNTHETIC_STAMP_SELF_TEST_PASS_NO_NETWORK")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--samples", type=int, default=2048)
    p.add_argument("--margin-ms", type=int, default=100)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    try:
        if args.self_test:
            _self_test()
            return 0
        _self_test()
        report = measure(args.samples, margin_ns=args.margin_ms * 1_000_000)
        data = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("xb") as handle:
                handle.write(data)
        print(json.dumps({
            "status": report["status"],
            "p99_observed_ns": report["p99_nearest_rank_observed_ns"],
            "max_observed_ns": report["max_observed_ns"],
            "samples": report["observed_samples"],
            "report_sha256": hashlib.sha256(data).hexdigest(),
            "clock_gate": "FUTURE_EVENT_INDEPENDENT_UTC_AND_FULL_STAMP_BOUND_STILL_BLOCKED",
            "market_get": 0, "market_ws": 0,
        }, sort_keys=True))
        return 0
    except (CalibrationBlocked, OSError, AssertionError) as e:
        print(json.dumps({"status": "STAMP_CALIBRATION_BLOCKED",
                          "reason": str(e)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
