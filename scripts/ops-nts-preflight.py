"""Bounded Windows NTS preflight. Requires an independently issued operator permit."""
import argparse
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import os
from pathlib import Path
import subprocess

from zs_smart_gate.ops_nts_client import run
from zs_smart_gate.stage05_contracts import SHA, digest, parse_utc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--permit-sha256")
    parser.add_argument("--ca-bundle", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.live:
        return 2
    if not all((args.permit, args.permit_sha256, args.ca_bundle, args.output)):
        parser.error("permit, independent permit pin, trust bundle and output are required")
    if os.name != "nt" or any(p.resolve().drive.upper() != "D:" for p in
                             (args.permit, args.ca_bundle, args.output)):
        parser.error("Windows and D: paths are required")
    raw = args.permit.read_bytes()
    if not SHA.fullmatch(args.permit_sha256) or digest(raw) != args.permit_sha256:
        parser.error("permit pin mismatch")
    permit = json.loads(raw)
    # A matching permit digest checks custody, not its issuer's authority.
    def git(*a):
        return subprocess.check_output(["git", *a], text=True).strip()
    if (permit["schema"] != "zs.ops.nts-operator-permit.v1"
            or git("rev-parse","HEAD") != permit["head"]
            or git("rev-parse","HEAD^{tree}") != permit["tree"]
            or git("status","--porcelain") or permit["windows_profile"] != os.environ.get("USERNAME")):
        parser.error("wrong code or Windows profile")
    timestamp_ip = ipaddress.IPv4Address(permit["timestamp_ip"])
    if not timestamp_ip.is_global or not SHA.fullmatch(permit["ca_sha256"]):
        parser.error("public timestamp IP and CA bundle pin required")
    now = datetime.now(timezone.utc)

    def end(scope):
        start, finish = (parse_utc(scope[k]) for k in ("start_utc","end_utc"))
        if not start <= now or now+timedelta(seconds=120) > finish or finish-start > timedelta(minutes=15):
            parser.error("scope must have 120 seconds remaining in its approved UTC window")
        return finish

    time_end = end(permit["time"])
    spot_end = None if permit.get("spot") is None else end(permit["spot"])
    args.output.mkdir(exist_ok=False)
    (args.output/"permit-sha256.txt").write_text(args.permit_sha256, encoding="ascii")
    result = run(args.output, ca_file=args.ca_bundle, ca_pin=permit["ca_sha256"],
                 approved_ip=str(timestamp_ip), time_end=time_end, spot_end=spot_end)
    print(json.dumps({k:result[k] for k in ("status","clock_absolute","ke_attempts","udp_attempts")}))
    return 0 if result["status"] == "AUTHENTICATED_CONDITIONAL_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
