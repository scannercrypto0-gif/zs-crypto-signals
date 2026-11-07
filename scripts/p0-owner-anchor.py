"""Offline, synthetic-only owner receipt emitter/readback for Option A.

Never makes network calls. Never establishes independent custody or authenticated time.
The writer emits a portable receipt; owner must separately acquire and keep it
outside writer control and acknowledge that independently.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import re
import sys

SCHEMA = "zs03.owner-option-a-synthetic-receipt.v1"
MAX_RAW_BYTES = 1_048_576
MAX_RECEIPT_BYTES = 16_384
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
CODE_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}\Z")
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
PATH_RE = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\Z")
TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


class AnchorBlocked(ValueError):
    """Hard-fail for receipt, raw, or manifest inconsistencies."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise AnchorBlocked(reason)


def _utc_time(value: str) -> str:
    _require(isinstance(value, str) and TIMESTAMP_RE.fullmatch(value) is not None,
             "RECEIPT_TIME_NOT_EXPLICIT_UTC")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise AnchorBlocked("RECEIPT_TIME_INVALID") from exc
    _require(parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value,
             "RECEIPT_TIME_INVALID")
    return value


def _validate_ids(study_id: str, event_id: str, code_sha: str,
                  repository: str, raw_path: str, manifest_path: str,
                  creator: str) -> None:
    _require(isinstance(study_id, str) and ID_RE.fullmatch(study_id) is not None,
             "STUDY_ID_INVALID")
    _require(isinstance(event_id, str) and ID_RE.fullmatch(event_id) is not None,
             "EVENT_ID_INVALID")
    _require(isinstance(code_sha, str) and CODE_SHA_RE.fullmatch(code_sha) is not None,
             "CODE_SHA_INVALID")
    _require(isinstance(repository, str) and REPO_RE.fullmatch(repository) is not None,
             "REPOSITORY_INVALID")
    _require(isinstance(raw_path, str) and PATH_RE.fullmatch(raw_path) is not None,
             "RAW_PATH_INVALID")
    _require(isinstance(manifest_path, str) and PATH_RE.fullmatch(manifest_path) is not None,
             "MANIFEST_PATH_INVALID")
    _require(isinstance(creator, str) and
             re.fullmatch(r"[A-Za-z0-9_.:-]{3,64}", creator) is not None,
             "CREATOR_DECLARATION_INVALID")


def _synthetic(raw: bytes) -> None:
    _require(len(raw) <= MAX_RAW_BYTES, "SYNTHETIC_RAW_TOO_LARGE")
    _require(b"origin=SYNTHETIC_ONLY\n" in raw and
             b"market_requests=0\n" in raw and
             raw.count(b"payload=") == 1, "SYNTHETIC_SOURCE_NOT_VERIFIED")


def make_receipt(raw: bytes, manifest: bytes, *, study_id: str, event_id: str,
                 code_sha: str, repository: str, raw_path: str,
                 manifest_path: str, creator: str,
                 generated_at_utc: str | None = None) -> dict:
    """Create a *writer-issued* receipt, never an independent owner anchor."""
    _synthetic(raw)
    _validate_ids(study_id, event_id, code_sha, repository, raw_path,
                  manifest_path, creator)
    _require(len(manifest) > 0, "MANIFEST_EMPTY")
    created = generated_at_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _utc_time(created)
    prefix = f"https://github.com/{repository}/blob/{code_sha}/"
    body = {
        "schema": SCHEMA,
        "study_id": study_id,
        "event_id": event_id,
        "mode": "SYNTHETIC_ONLY",
        "code_sha": code_sha,
        "raw_sha256": sha256(raw),
        "raw_size_bytes": len(raw),
        "raw_ref": prefix + raw_path,
        "manifest_sha256": sha256(manifest),
        "manifest_ref": prefix + manifest_path,
        "receipt_generated_at_utc": created,
        "receipt_creator_declared": creator,
        "market_source_received_at_utc": None,
        "market_decision_at_utc": None,
        "clock_witness_ref": None,
        "rights_status": "NOT_APPLICABLE_SYNTHETIC",
        "time_status": "SELF_REPORTED_RUNNER_UTC_NOT_INDEPENDENT",
        "external_owner_custody": "ACK_PENDING",
    }
    return {"receipt": body, "receipt_body_sha256": sha256(canonical(body))}


def receipt_bytes(envelope: dict) -> bytes:
    return (json.dumps(envelope, sort_keys=True, indent=2,
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for k, v in pairs:
        _require(k not in result, "DUPLICATE_RECEIPT_JSON_KEY")
        result[k] = v
    return result


def parse_receipt(data: bytes) -> dict:
    _require(0 < len(data) <= MAX_RECEIPT_BYTES, "RECEIPT_FILE_SIZE_INVALID")
    try:
        envelope = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AnchorBlocked("RECEIPT_JSON_INVALID") from exc
    _require(type(envelope) is dict and
             set(envelope) == {"receipt", "receipt_body_sha256"},
             "RECEIPT_ENVELOPE_INVALID")
    body = envelope["receipt"]
    _require(type(body) is dict and
             set(body) == {
                 "schema", "study_id", "event_id", "mode", "code_sha",
                 "raw_sha256", "raw_size_bytes", "raw_ref",
                 "manifest_sha256", "manifest_ref", "receipt_generated_at_utc",
                 "receipt_creator_declared", "market_source_received_at_utc",
                 "market_decision_at_utc", "clock_witness_ref", "rights_status",
                 "time_status", "external_owner_custody",
             }, "RECEIPT_BODY_FIELDS_INVALID")
    expected = envelope["receipt_body_sha256"]
    _require(isinstance(expected, str) and SHA256_RE.fullmatch(expected) is not None,
             "RECEIPT_BODY_DIGEST_INVALID")
    _require(hmac.compare_digest(sha256(canonical(body)), expected),
             "RECEIPT_BODY_MISMATCH")
    return body


def verify(raw: bytes, manifest: bytes, receipt_file: bytes, *,
           expected_owner_file_sha256: str, expected_code_sha: str,
           expected_event_id: str) -> dict:
    """Matches owner-supplied receipt bytes; cannot prove who held its digest."""
    _require(isinstance(expected_owner_file_sha256, str) and
             SHA256_RE.fullmatch(expected_owner_file_sha256) is not None,
             "EXPECTED_OWNER_RECEIPT_SHA_INVALID")
    _require(hmac.compare_digest(sha256(receipt_file), expected_owner_file_sha256),
             "OWNER_RECEIPT_FILE_MISMATCH")
    body = parse_receipt(receipt_file)
    _require(body["schema"] == SCHEMA and body["mode"] == "SYNTHETIC_ONLY",
             "RECEIPT_SCHEMA_OR_MODE_INVALID")
    _require(body["rights_status"] == "NOT_APPLICABLE_SYNTHETIC" and
             body["time_status"] == "SELF_REPORTED_RUNNER_UTC_NOT_INDEPENDENT" and
             body["external_owner_custody"] == "ACK_PENDING",
             "RECEIPT_CUSTODY_CLAIM_INVALID")
    _require(body["market_source_received_at_utc"] is None and
             body["market_decision_at_utc"] is None and
             body["clock_witness_ref"] is None, "SYNTHETIC_EVENT_CLAIM_INVALID")
    _require(isinstance(body["code_sha"], str) and
             CODE_SHA_RE.fullmatch(body["code_sha"]) is not None and
             body["code_sha"] == expected_code_sha, "CODE_SHA_MISMATCH")
    _require(body["event_id"] == expected_event_id, "EVENT_ID_MISMATCH")
    _require(isinstance(body["study_id"], str) and
             ID_RE.fullmatch(body["study_id"]) is not None and
             isinstance(body["event_id"], str) and
             ID_RE.fullmatch(body["event_id"]) is not None,
             "RECEIPT_ID_INVALID")
    _require(isinstance(body["receipt_creator_declared"], str) and
             re.fullmatch(r"[A-Za-z0-9_.:-]{3,64}",
                          body["receipt_creator_declared"]) is not None,
             "RECEIPT_CREATOR_INVALID")
    _utc_time(body["receipt_generated_at_utc"])
    _require(isinstance(body["raw_ref"], str) and
             f"/blob/{expected_code_sha}/" in body["raw_ref"] and
             body["raw_ref"].startswith("https://github.com/"),
             "RAW_REF_NOT_PINNED")
    _require(isinstance(body["manifest_ref"], str) and
             f"/blob/{expected_code_sha}/" in body["manifest_ref"] and
             body["manifest_ref"].startswith("https://github.com/"),
             "MANIFEST_REF_NOT_PINNED")
    _require(isinstance(body["manifest_sha256"], str) and
             SHA256_RE.fullmatch(body["manifest_sha256"]) is not None and
             hmac.compare_digest(sha256(manifest), body["manifest_sha256"]),
             "MANIFEST_SHA_MISMATCH")
    _require(type(body["raw_size_bytes"]) is int and
             0 <= body["raw_size_bytes"] <= MAX_RAW_BYTES,
             "RAW_SIZE_INVALID")
    _require(isinstance(body["raw_sha256"], str) and
             SHA256_RE.fullmatch(body["raw_sha256"]) is not None,
             "RAW_SHA_INVALID")
    _synthetic(raw)
    # Delegate the byte/length check to the earlier approved owner receipt verifier.
    spec = importlib.util.spec_from_file_location(
        "p0_owner_receipt_prior", Path(__file__).with_name("p0-owner-receipt.py"))
    _require(spec is not None and spec.loader is not None, "PRIOR_VERIFIER_MISSING")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        result = module.compare(raw, expected_sha256=body["raw_sha256"],
                                expected_size=body["raw_size_bytes"])
    except module.OwnerReceiptBlocked as exc:
        raise AnchorBlocked(str(exc)) from exc
    return {
        "status": "SYNTHETIC_RECEIPT_AND_RESTORED_RAW_MATCH_ONLY",
        "event_id": body["event_id"],
        "code_sha": body["code_sha"],
        "raw_sha256": result["sha256"],
        "raw_size_bytes": result["size_bytes"],
        "manifest_sha256": body["manifest_sha256"],
        "owner_receipt_file_sha256": sha256(receipt_file),
        "custody_gate": "OWNER_CUSTODY_ACK_PENDING",
        "outside_writer_control_proven": False,
        "owner_receipt_time_proven": False,
        "market_pit": "NOT_ATTESTED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    emit = sub.add_parser("emit", help="writer-side synthetic-only receipt")
    emit.add_argument("--raw", type=Path, required=True)
    emit.add_argument("--manifest", type=Path, required=True)
    emit.add_argument("--study-id", required=True)
    emit.add_argument("--event-id", required=True)
    emit.add_argument("--code-sha", required=True)
    emit.add_argument("--repository", required=True)
    emit.add_argument("--raw-path", required=True)
    emit.add_argument("--manifest-path", required=True)
    emit.add_argument("--creator", required=True)
    emit.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("verify", help="strict offline raw+receipt+manifest comparison")
    check.add_argument("--raw", type=Path, required=True)
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--receipt", type=Path, required=True)
    check.add_argument("--expected-owner-file-sha256", required=True)
    check.add_argument("--expected-code-sha", required=True)
    check.add_argument("--expected-event-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation == "emit":
            receipt = make_receipt(
                args.raw.read_bytes(), args.manifest.read_bytes(),
                study_id=args.study_id, event_id=args.event_id,
                code_sha=args.code_sha, repository=args.repository,
                raw_path=args.raw_path, manifest_path=args.manifest_path,
                creator=args.creator)
            data = receipt_bytes(receipt)
            _require(len(data) <= MAX_RECEIPT_BYTES, "RECEIPT_TOO_LARGE")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("xb") as handle:
                handle.write(data)
            print(json.dumps({
                "status": "SYNTHETIC_WRITER_RECEIPT_CREATED_OWNER_ACK_PENDING",
                "receipt_file_sha256": sha256(data),
                "raw_sha256": receipt["receipt"]["raw_sha256"],
                "raw_size_bytes": receipt["receipt"]["raw_size_bytes"],
                "event_id": receipt["receipt"]["event_id"],
                "custody_gate": "OWNER_CUSTODY_ACK_PENDING",
            }, sort_keys=True))
        else:
            print(json.dumps(verify(
                args.raw.read_bytes(), args.manifest.read_bytes(),
                args.receipt.read_bytes(),
                expected_owner_file_sha256=args.expected_owner_file_sha256,
                expected_code_sha=args.expected_code_sha,
                expected_event_id=args.expected_event_id), sort_keys=True))
    except (AnchorBlocked, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)[:160]},
                         sort_keys=True), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
