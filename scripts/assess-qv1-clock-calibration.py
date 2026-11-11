"""Conservative audit of a bounded authenticated Windows clock calibration."""
import argparse
from itertools import pairwise
import json
from pathlib import Path


def assess(rows):
    if len(rows) < 3:
        raise ValueError("CLOCK_CALIBRATION_TOO_FEW_SAMPLES")
    steps = []
    for (before, bhost), (after, ahost) in pairwise(rows):
        dt = after["sample_local_received"] - before["sample_local_received"]
        if dt <= 0 or ahost["frequency"] != bhost["frequency"]:
            raise ValueError("CLOCK_CALIBRATION_NONMONOTONIC")
        # A difference between wall and monotonic elapsed detects a net
        # correction. Two endpoint readings cannot exclude intermediate steps.
        wall_delta = (ahost["start_wall_ms"] - bhost["start_wall_ms"]) / 1000
        mono_delta = (ahost["start_mono_ticks"] - bhost["start_mono_ticks"]) / ahost["frequency"]
        offset_delta = abs(after["offset_seconds"] - before["offset_seconds"])
        radius = before["conditional_radius_seconds"] + after["conditional_radius_seconds"]
        steps.append({"elapsed_seconds":dt, "net_wall_minus_monotonic_seconds":wall_delta-mono_delta,
                      "offset_delta_seconds":offset_delta,
                      "observed_average_rate_upper_ppm":(offset_delta+radius)/dt*1000000})
    rate = max(s["observed_average_rate_upper_ppm"] for s in steps)
    initial = max(sample["conditional_local_error_bound_seconds"] for sample,_ in rows)
    return {"samples":len(rows),"observed_span_seconds":sum(s["elapsed_seconds"] for s in steps),
            "pairs":steps,"max_observed_average_rate_upper_ppm":rate,
            "conditional_30s_projection_seconds":initial + 30*rate/1000000,
            "approved_future_drift_bound_ppm":None,"certified_max_age_seconds":None,
            "limitation":"Projection assumes observed average rate applies. Endpoint evidence does not bound unobserved oscillator rate or intermediate clock steps, and provider UTC error is not separately attested."}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("root",type=Path)
    args=parser.parse_args()
    rows=[]
    for folder in sorted(args.root.glob("sample-*")):
        report=json.loads((folder/"report.json").read_bytes())
        if report["status"] != "NTS_AUTHENTICATED_CLOCK_PARTIAL":
            raise ValueError("CLOCK_AUTHENTICATED_SAMPLE_MISSING")
        rows.append((report["sample"],json.loads((folder/"host-timing.json").read_bytes())))
    print(json.dumps(assess(rows),sort_keys=True))


if __name__=="__main__":
    main()
