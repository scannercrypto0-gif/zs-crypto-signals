"""Two independently operated NTP servers: bounded but UNAUTHENTICATED UTC witness.

One UDP NTP request per server; no retries, host clock edits, or background work.
NTPv4 per RFC5905. A conservative error budget is NOT a cryptographic
attestation and never proves Binance publisher/event creation timestamps.
"""
from __future__ import annotations

import math
import socket
import struct
import time

NTP_EPOCH = 2208988800
SERVERS = ("time.cloudflare.com", "time.google.com")
MAX_U_SECONDS = 1.5
MAX_DISAGREEMENT_SECONDS = 0.25

class ClockGateError(ValueError):
    pass

def ntp_seconds(raw: bytes) -> float:
    sec, frac = struct.unpack("!II", raw)
    return sec - NTP_EPOCH + frac / 4294967296.0

def as_ntp(seconds: float) -> bytes:
    whole = math.floor(seconds + NTP_EPOCH)
    frac = round((seconds + NTP_EPOCH - whole) * 4294967296) % 4294967296
    return struct.pack("!II", whole, frac)

def probe(host: str, timeout: float = 2.0) -> dict:
    if host not in SERVERS:
        raise ClockGateError("NTP_HOST_NOT_ALLOWLISTED")
    try:
        addr = socket.getaddrinfo(host, 123, type=socket.SOCK_DGRAM,
                                  proto=socket.IPPROTO_UDP)[0]
        family, socktype, proto, _, remote = addr
        with socket.socket(family, socktype, proto) as sock:
            sock.settimeout(timeout)
            payload = bytearray(48)
            payload[0] = 0x23  # NTPv4 client request
            t1 = time.time_ns() / 1e9
            tx = as_ntp(t1)
            payload[40:48] = tx
            m1 = time.perf_counter_ns()
            sock.sendto(payload, remote)
            reply, sender = sock.recvfrom(512)
            m4 = time.perf_counter_ns()
            t4 = time.time_ns() / 1e9
    except (OSError, TimeoutError) as exc:
        raise ClockGateError("NTP_UNAVAILABLE_" + host.replace(".", "_")) from exc
    if len(reply) < 48 or reply[24:32] != tx:
        raise ClockGateError("NTP_ORIGIN_MISMATCH")
    li, ver, mode = reply[0] >> 6, (reply[0] >> 3) & 7, reply[0] & 7
    stratum = reply[1]
    if li != 0 or ver not in (3, 4) or mode != 4 or not 1 <= stratum <= 15:
        raise ClockGateError("NTP_UNSYNCHRONIZED_OR_INVALID")
    t2, t3 = ntp_seconds(reply[32:40]), ntp_seconds(reply[40:48])
    root_delay = struct.unpack("!i", reply[4:8])[0] / 65536.0
    root_disp = struct.unpack("!I", reply[8:12])[0] / 65536.0
    rtt = (m4 - m1) / 1e9
    wall_elapsed = t4 - t1
    if (not all(math.isfinite(v) for v in (t1,t2,t3,t4,rtt,root_delay,root_disp))
            or root_delay < 0 or root_disp < 0 or rtt <= 0 or rtt > 1.5
            or t3 < t2 or abs(wall_elapsed - rtt) > 0.1):
        raise ClockGateError("NTP_IMPOSSIBLE_TIMING")
    offset = ((t2-t1) + (t3-t4))/2
    # Deliberately conservative local-UTC absolute error estimate. Includes
    # *absolute* measured offset; never report offset alone as uncertainty.
    bound = (abs(offset) + rtt/2 + root_delay/2 + root_disp
             + 0.025 + 0.000015 * 10)
    if not math.isfinite(bound) or bound >= MAX_U_SECONDS:
        raise ClockGateError("NTP_ERROR_BUDGET_GE_1_5S")
    return {
        "host": host, "ntp_version": ver, "stratum": stratum,
        "roundtrip_seconds": round(rtt, 6),
        "offset_seconds": round(offset, 6),
        "root_delay_seconds": round(root_delay, 6),
        "root_dispersion_seconds": round(root_disp, 6),
        "conservative_absolute_utc_error_seconds": round(bound, 6),
        "captured_wall_unattested_unix_seconds": round(t4, 6),
        "captured_monotonic_ns": m4,
        "server_authentication": "UNAUTHENTICATED_PUBLIC_NTP",
    }

def witness_pair() -> dict:
    """Two independent names, one probe each; hard fail on loss/disagreement."""
    a, b = [probe(host) for host in SERVERS]
    d = abs(a["offset_seconds"] - b["offset_seconds"])
    if d > MAX_DISAGREEMENT_SECONDS:
        raise ClockGateError("INDEPENDENT_NTP_SOURCES_DISAGREE")
    bound = max(a["conservative_absolute_utc_error_seconds"],
                b["conservative_absolute_utc_error_seconds"]) + 0.005
    if bound >= MAX_U_SECONDS:
        raise ClockGateError("UTC_BOUND_GE_1_5S")
    return {
        "schema": "ZS03_NTP_DUAL_WITNESS_V1",
        "probes": [a, b],
        "inter_source_offset_disagreement_seconds": round(d, 6),
        "conservative_absolute_utc_error_seconds": round(bound, 6),
        "authenticated": False,
        "scientific_note": "Two independent unauthenticated NTP paths; not NTS or Binance publisher clock",
    }

def bracketed_receive(before: dict, after: dict, *, start_wall: float,
                      received_wall: float, request_duration_s: float) -> dict:
    """Fail closed if local clock steps or before/after peers disagree."""
    if (not 0 <= request_duration_s <= 8.5
            or not start_wall <= received_wall
            or abs((received_wall - start_wall) - request_duration_s) > 0.1):
        raise ClockGateError("MARKET_REQUEST_WALL_MONOTONIC_MISMATCH")
    offsets = [x["offset_seconds"] for w in (before, after) for x in w["probes"]]
    if max(offsets) - min(offsets) > MAX_DISAGREEMENT_SECONDS:
        raise ClockGateError("NTP_PRE_POST_OFFSET_DIVERGENCE")
    u = max(before["conservative_absolute_utc_error_seconds"],
            after["conservative_absolute_utc_error_seconds"]) + 0.015
    if u >= MAX_U_SECONDS:
        raise ClockGateError("RECEIPT_UNCERTAINTY_GE_1_5S")
    # UTC time interval, not invented exchange-publisher time.
    return {
        "method": "DUAL_NTP_PRE_POST_UNAUTHENTICATED",
        "utc_error_bound_seconds": round(u, 6),
        "received_local_unix_seconds": round(received_wall, 6),
        "utc_received_earliest_unix_seconds": round(received_wall - u, 6),
        "utc_received_latest_unix_seconds": round(received_wall + u, 6),
        "source_clock_authenticated": False,
        "publisher_timestamp": None,
        "before": before, "after": after,
    }


def main(argv=None):
    import json
    import sys
    try:
        w = witness_pair()
    except ClockGateError as exc:
        print("CLOCK_PRECHECK_BLOCKED:" + str(exc), file=sys.stderr)
        return 2
    print(json.dumps({
        "schema":w["schema"],
        "hosts":[p["host"] for p in w["probes"]],
        "conservative_absolute_utc_error_seconds":
            w["conservative_absolute_utc_error_seconds"],
        "independent_clock_authenticated": False,
        "status":"NTP_MEASURED_NETWORK_ONLY_NOT_BINANCE_EVENT_ATTESTED",
    },indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
