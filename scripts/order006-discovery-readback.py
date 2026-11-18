"""Derive public listing metadata from a pinned owner-local response, with no HTTP."""
import argparse
import json
from pathlib import Path

from zs_smart_gate.marketwide_capture import MAX_BODY, discovery_only
from zs_smart_gate.stage05_contracts import canonical, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if any(path.resolve().drive.upper() != "D:" for path in (args.capture, args.output)):
        parser.error("owner-local input/output must be on D:")
    if args.output.exists():
        parser.error("fresh output file required")
    receipts = [json.loads(row) for row in (args.capture/"requests.jsonl").read_bytes().splitlines()]
    received = next(row for row in receipts if row["path"] == "exchangeInfo" and row["state"] == "RECEIVED")
    body = args.capture/("response-" + str(received["attempt"]) + ".private")
    if not 0 < body.stat().st_size <= MAX_BODY:
        raise ValueError("BODY_SIZE_INVALID")
    raw = body.read_bytes()
    if digest(raw) != received["body_sha256"] or received["http_status"] != 200:
        raise ValueError("BODY_RECEIPT_MISMATCH")
    result = discovery_only(dict(path=received["path"], params=received["params"],
        received_at=received["received_at"], body_sha256=received["body_sha256"], payload=json.loads(raw)))
    args.output.write_bytes(canonical(result))
    print(canonical({k: v for k, v in result.items() if k != "rows"}).decode())


if __name__ == "__main__":
    main()
