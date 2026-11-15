"""Bound a local marker with two authenticated external time samples."""
import argparse
import importlib.util
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.drive.upper() != "D:":
        raise SystemExit("PRIVATE_D_REQUIRED")
    root.mkdir(exist_ok=False)
    spec = importlib.util.spec_from_file_location("nts_probe", args.probe)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    before = probe.run(root / "before")
    if before["status"] != "NTS_AUTHENTICATED_CLOCK_PARTIAL":
        raise SystemExit("BEFORE_SAMPLE_FAILED")
    marker = time.monotonic_ns()
    after = probe.run(root / "after")
    if after["status"] != "NTS_AUTHENTICATED_CLOCK_PARTIAL":
        raise SystemExit("AFTER_SAMPLE_FAILED")
    lo, hi = (record["sample"] for record in (before, after))
    lower = lo["sample_local_received"] + lo["offset_seconds"] - lo["conditional_radius_seconds"]
    upper = hi["sample_local_received"] + hi["offset_seconds"] + hi["conditional_radius_seconds"]
    if upper < lower:
        raise SystemExit("AUTHENTICATED_BRACKET_INCONSISTENT")
    result = {"marker_monotonic_ns": marker, "conditional_utc_lower_epoch_s": lower,
              "conditional_utc_upper_epoch_s": upper, "interval_width_s": upper-lower,
              "within_1_5s_width": upper-lower < 1.5, "scope": "LOCAL_TEST_MARKER_ONLY",
              "historical_pit": False, "absolute_utc_certified": False,
              "request_sha256": [before["request_sha256"],after["request_sha256"]],
              "response_sha256": [before["response_sha256"],after["response_sha256"]],
              "method": "Marker after first authenticated receipt and before second request. UTC interval bounded by the external receive-time estimates. No clock-rate extrapolation.",
              "assumption": "Both provider responses bound true UTC under their authenticated root metadata; independent absolute error remains unattested."}
    (root / "marker-report.json").write_text(json.dumps(result,sort_keys=True),encoding="utf-8")
    print(json.dumps(result,sort_keys=True))


if __name__ == "__main__":
    main()
