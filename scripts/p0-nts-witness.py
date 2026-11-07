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
import ipaddress
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



def _only_field(raw: str, name: str) -> str:
    matches = re.findall(r"(?im)^\s*" + re.escape(name) + r"\s*:\s*(.*?)\s*$", raw)
    if len(matches) != 1:
        raise WitnessBlocked("IDENTITY_FIELD_MISSING_OR_DUPLICATE:" + name)
    return matches[0]


def verified_selected_peer(tracking: str, auth: str, ntp: str,
                           sources: str) -> str:
    """Fail closed unless all four chronyc outputs match ONE selected NTS peer.

    This P0 diagnostic authorizes one IPv4 NTS source, not generic chrony
    multiple-source operation. Switching identities between readouts BLOCKS.
    """
    source_rows = re.findall(r"(?m)^\s*([\^=#][*+\-x~?])\s+(\S+)", sources)
    if len(source_rows) != 1:
        raise WitnessBlocked("SOURCE_INVENTORY_NOT_SINGLETON")
    state, source_ip = source_rows[0]
    if state != "^*":
        raise WitnessBlocked("SOURCE_NOT_SELECTED")
    try:
        address = ipaddress.IPv4Address(source_ip)
    except ipaddress.AddressValueError as ex:
        raise WitnessBlocked("SOURCE_IPV4_IDENTITY_UNVERIFIABLE") from ex
    canonical_ip = str(address)
    ref_hex = address.packed.hex().upper()

    auth_rows = [line.split() for line in auth.splitlines()
                 if re.match(r"^\s*\d{1,3}(?:\.\d{1,3}){3}\s+", line)]
    if len(auth_rows) != 1:
        raise WitnessBlocked("AUTH_INVENTORY_NOT_SINGLETON")
    row = auth_rows[0]
    if row[0] != canonical_ip:
        raise WitnessBlocked("SELECTED_SOURCE_AUTH_IDENTITY_MISMATCH")
    try:
        key_ok = (len(row) >= 5 and row[1] == "NTS"
                  and int(row[2]) > 0 and int(row[4]) > 0)
    except (ValueError, IndexError):
        key_ok = False
    if not key_ok:
        raise WitnessBlocked("NTS_AUTH_KEY_NOT_ESTABLISHED")

    remote = re.fullmatch(r"(\S+)\s+\(([0-9A-Fa-f]{8})\)",
                          _only_field(ntp, "Remote address"))
    if not remote or remote.group(1) != canonical_ip or remote.group(2).upper() != ref_hex:
        raise WitnessBlocked("NTP_REMOTE_IDENTITY_MISMATCH")
    reference = re.fullmatch(r"([0-9A-Fa-f]{8})\s+\((\S+)\)",
                             _only_field(tracking, "Reference ID"))
    if not reference or reference.group(1).upper() != ref_hex or reference.group(2) != canonical_ip:
        raise WitnessBlocked("TRACKING_REFERENCE_IDENTITY_MISMATCH")
    if _only_field(ntp, "Authenticated") != "Yes":
        raise WitnessBlocked("NTP_PACKET_NOT_AUTHENTICATED")
    if _only_field(ntp, "NTP tests") != "111 111 1111":
        raise WitnessBlocked("NTP_CHECKS_NOT_ALL_PASS")
    return canonical_ip


def judge(tracking: str, auth: str, ntp: str, *, sources: str,
          now: datetime, drift_measurement: float) -> dict:
    if field(tracking, "Leap status") != "Normal":
        raise WitnessBlocked("LEAP_NOT_NORMAL")
    selected_peer = verified_selected_peer(tracking, auth, ntp, sources)
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
        "selected_authenticated_source_ip": selected_peer,
        "protocol": "NTS_AUTHENTICATED_NTP",
        "host": "GITHUB_ACTIONS_UBUNTU_EPHEMERAL_DEV",
        "sample_ref_utc": stamp.isoformat(),
        "readout_utc": now.isoformat(),
        "sample_age_seconds": round(age, 6),
        "conservative_assumed_uncertainty_seconds": round(time_budget, 6),
        "uncertainty_rule": "ABS_SYSTEM_OFFSET_PLUS_FULL_ROOT_DELAY_PLUS_DISPERSION_PLUS_100MS_PLUS_MEASURED_MONO_DRIFT",
        "stamp_margin_seconds": 0.100,
        "stamp_margin_evidence": "UNVERIFIED_OPERATIONAL_ASSUMPTION",
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
    }
    try:
        evidence.update(judge(text["tracking"], text["auth"], text["ntp"],
                              sources=text["sources"], now=u1,
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
