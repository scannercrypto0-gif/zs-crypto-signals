"""P0 one-shot, fail-closed validation of an independent authenticated NTS source.

Runs only on disposable GitHub Actions Ubuntu development host.
No market endpoint, no scheduler, no system clock adjustment, no state write.
The numerical error bound is conservative and applies ONLY to this sampled host
and time; it must never be used as a later market decision's PIT witness.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time


class WitnessBlocked(Exception):
    pass


def field(text: str, name: str) -> str:
    match = re.search(r"(?im)^\s*" + re.escape(name) + r"\s*:\s*(.*?)\s*$", text)
    if not match:
        raise WitnessBlocked("FIELD_MISSING:" + name)
    return match.group(1)


def seconds(text: str, name: str) -> float:
    raw = field(text, name)
    match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s+seconds?\b", raw)
    if not match:
        raise WitnessBlocked("SECONDS_PARSE_ERROR:" + name)
    x = float(match.group(1))
    if not math.isfinite(x):
        raise WitnessBlocked("NONFINITE:" + name)
    return x


def judge(tracking: str, auth: str, ntp: str, *, now: datetime,
          drift_measurement: float) -> dict:
    if field(tracking, "Leap status") != "Normal":
        raise WitnessBlocked("LEAP_NOT_NORMAL")
    if not re.search(r"(?m)^\s*\^\*\s", tracking.replace("\r", "")):
        # Tracking does not normally contain sources; selection is validated
        # from the caller's separate chronyc sources output.
        pass
    if not re.search(r"(?m)^\s*\S+\s+NTS\s+([1-9]\d*)\s+([1-9]\d*)\s+([1-9]\d*)\s", auth):
        raise WitnessBlocked("NTS_AUTH_KEY_NOT_ESTABLISHED")
    if field(ntp, "Authenticated") != "Yes":
        raise WitnessBlocked("NTP_PACKET_NOT_AUTHENTICATED")
    if field(ntp, "Leap status") != "Normal":
        raise WitnessBlocked("NTP_LEAP_NOT_NORMAL")
    ref = field(tracking, "Ref time (UTC)")
    try:
        stamp = datetime.strptime(ref, "%a %b %d %H:%M:%S %Y").replace(tzinfo=timezone.utc)
    except ValueError as ex:
        raise WitnessBlocked("UNPARSEABLE_REF_TIME") from ex
    age = (now - stamp).total_seconds()
    if age < -2 or age > 30:
        raise WitnessBlocked("NTS_SAMPLE_STALE_OR_FUTURE")
    sys_offset = abs(seconds(tracking, "System time"))
    root_delay = seconds(tracking, "Root delay")
    root_disp = seconds(tracking, "Root dispersion")
    if root_delay < 0 or root_disp < 0 or drift_measurement < 0:
        raise WitnessBlocked("NEGATIVE_UNCERTAINTY_COMPONENT")
    # Full root delay, not half RTT: conservatively count unknown forward/reverse
    # path asymmetry. Add explicit local scheduling/stamping margin and measured
    # UTC-to-monotonic interval drift. Single-source trust is not cross-source proof.
    time_budget = sys_offset + root_delay + root_disp + 0.100 + drift_measurement
    if not math.isfinite(time_budget):
        raise WitnessBlocked("BAD_UNCERTAINTY")
    if time_budget >= 1.5:
        raise WitnessBlocked("UNCERTAINTY_NOT_STRICTLY_BELOW_1_5S")
    return {
        "schema": "ZS03_P0_SINGLE_NTS_WITNESS_ATTEMPT_V1",
        "source": "time.cloudflare.com",
        "protocol": "NTS_AUTHENTICATED_NTP",
        "host": "GITHUB_ACTIONS_UBUNTU_EPHEMERAL_DEV",
        "sample_ref_utc": stamp.isoformat(),
        "readout_utc": now.isoformat(),
        "sample_age_seconds": round(age, 6),
        "conservative_assumed_uncertainty_seconds": round(time_budget, 6),
        "uncertainty_rule": "ABS_SYSTEM_OFFSET_PLUS_FULL_ROOT_DELAY_PLUS_DISPERSION_PLUS_100MS_PLUS_MEASURED_MONO_DRIFT",
        "status": "UTC_WITNESS_PLAUSIBLE_THIS_HOST_THIS_INSTANT_ONLY",
        "market_pit": "NOT_ATTESTED",
        "future_clock_drift": "NOT_ATTESTED",
        "second_independent_time_source": "NOT_ATTESTED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("tracking", "auth", "ntp", "sources"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    raw = {n: getattr(args, n).read_bytes() for n in ("tracking", "auth", "ntp", "sources")}
    text = {k: v.decode("utf-8", errors="strict") for k, v in raw.items()}
    t0 = time.monotonic_ns()
    u0 = datetime.now(timezone.utc)
    time.sleep(0.3)
    t1 = time.monotonic_ns()
    u1 = datetime.now(timezone.utc)
    drift = abs((u1 - u0).total_seconds() - (t1-t0)/1e9)
    evidence = {
        "raw_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in raw.items()},
        "monotonic_ns_start": t0, "monotonic_ns_end": t1,
        "utc_at_start": u0.isoformat(), "utc_at_end": u1.isoformat(),
        "utc_monotonic_drift_seconds": round(drift, 9),
        "source_selected": bool(re.search(r"(?m)^\s*\^\*\s+\S+", text["sources"])),
    }
    try:
        if not evidence["source_selected"]:
            raise WitnessBlocked("NO_SELECTED_AUTHENTICATED_SOURCE")
        evidence.update(judge(text["tracking"], text["auth"], text["ntp"], now=u1,
                              drift_measurement=drift))
    except WitnessBlocked as ex:
        evidence["status"] = "CLOCK_BLOCKED"
        evidence["reason"] = str(ex)
        print(json.dumps(evidence, sort_keys=True))
        return 1
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
