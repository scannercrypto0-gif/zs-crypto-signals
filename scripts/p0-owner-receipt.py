"""Offline check against an independent, owner-held SHA256+size receipt.

The supplied digest must have been secured outside the raw writer's control.
This script cannot prove who issued the digest or when it was recorded.
No network, accounts, market connection, or immutability guarantee.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


class OwnerReceiptBlocked(ValueError):
    pass


def compare(raw: bytes, *, expected_sha256: str, expected_size: int) -> dict:
    if not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
        raise OwnerReceiptBlocked("EXTERNAL_ANCHOR_DIGEST_INVALID")
    if expected_size < 0:
        raise OwnerReceiptBlocked("EXTERNAL_ANCHOR_SIZE_INVALID")
    actual = hashlib.sha256(raw).hexdigest()
    if len(raw) != expected_size or actual != expected_sha256.lower():
        raise OwnerReceiptBlocked("OWNER_ANCHOR_MISMATCH")
    return {
        "status": "MATCHES_EXTERNALLY_SUPPLIED_DIGEST_ONLY",
        "sha256": actual,
        "size_bytes": len(raw),
        "outside_writer_control_proven": False,
        "anchor_creation_time_proven": False,
        "market_pit": "NOT_ATTESTED",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--raw", type=Path, required=True)
    p.add_argument("--owner-sha256", required=True)
    p.add_argument("--owner-size", type=int, required=True)
    args = p.parse_args()
    print(json.dumps(compare(args.raw.read_bytes(),
                             expected_sha256=args.owner_sha256,
                             expected_size=args.owner_size), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
