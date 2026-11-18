"""ORDER007 local real-source science intake; no OOS/forward claims.

Reads original operator-captured D: packets, verifies hashes/identity,
builds reproducible DEV-only feasibility counts and rejects promotion.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import re
import hashlib

from .marketwide_research import evaluate
from .stage05_contracts import canonical, digest

VERSION = "zs.order007.up-down-source-intake.v1"
MAX_MANIFESTS = 2000
MAX_PRIVATE_BYTES = 2 * 1024 * 1024


def _read_json(path: Path) -> dict:
    if path.stat().st_size > MAX_PRIVATE_BYTES:
        raise ValueError("SCIENCE_FILE_SIZE_LIMIT")
    result = json.loads(path.read_bytes())
    if not isinstance(result, dict):
        raise ValueError("SCIENCE_SOURCE_OBJECT_REQUIRED")
    return result


def _verify_original_bodies(manifest: dict, directory: Path) -> None:
    rows = manifest.get("raw_body_receipts")
    if not isinstance(rows, list) or not rows or len(rows) > 11:
        raise ValueError("ORIGINAL_RESPONSE_HASH_MANIFEST_REQUIRED")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("SOURCE_BODY_RECORD_INVALID")
        name, sha = row.get("file"), row.get("sha256")
        if (not isinstance(name, str) or not re.fullmatch(
                r"response-[1-9][0-9]*\\.private", name)
                or name in seen or not isinstance(sha, str)
                or not re.fullmatch(r"[a-f0-9]{64}", sha)):
            raise ValueError("SOURCE_BODY_PATH_OR_SHA_INVALID")
        seen.add(name)
        path = directory/name
        if not path.is_file() or path.stat().st_size > 16*1024*1024:
            raise ValueError("SOURCE_BODY_FILE_MISSING_OR_OVERSIZE")
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b""):
                h.update(chunk)
        if h.hexdigest() != sha:
            raise ValueError("ORIGINAL_RESPONSE_BYTES_HASH_MISMATCH")


def source_intake(root: Path) -> dict:
    """Strict local-only D: data admission, never real policy acceptance."""
    root = Path(root)
    if not root.is_dir():
        raise ValueError("SCIENCE_DIRECTORY_NOT_FOUND")
    entries = sorted(root.glob("shadow-*/sanitized-source-manifest.json"))
    entries += sorted(root.glob("original-*/sanitized-source-manifest.json"))
    if len(entries) > MAX_MANIFESTS:
        raise ValueError("SCIENCE_MANIFEST_LIMIT")
    counts = {d: Counter() for d in ("UP", "DOWN")}
    symbols = set()
    unique = {}
    errors = []
    manifest_hashes = []
    for mfile in sorted(entries):
        try:
            manifest = _read_json(mfile)
            if manifest.get("schema") != "zs.order007.original-public-spot-source.v1":
                raise ValueError("MANIFEST_SCHEMA_UNVERIFIED")
            manifest_hashes.append(digest(mfile.read_bytes()))
            _verify_original_bodies(manifest, mfile.parent)
            for row in manifest.get("coverage", []):
                if not isinstance(row, dict) or "packet_sha256" not in row:
                    continue
                symbol = row.get("symbol")
                if not isinstance(symbol, str) or not symbol.isascii() or not symbol.isalnum():
                    raise ValueError("SYMBOL_INVALID")
                packet_path = mfile.parent/(symbol + "-source.private.json")
                packet = _read_json(packet_path)
                if digest(canonical(packet)) != row["packet_sha256"]:
                    raise ValueError("PRIVATE_PACKET_HASH_MISMATCH")
                if packet_path.stat().st_size and digest(packet_path.read_bytes()) != row.get(
                        "private_packet_sha256"):
                    raise ValueError("PRIVATE_PACKET_BYTE_HASH_MISMATCH")
                if packet.get("symbol") != symbol or packet.get("source_scope") != (
                        "PUBLIC_SPOT_CONDITIONAL_RESEARCH"):
                    raise ValueError("SOURCE_SCOPE_SYMBOL_MISMATCH")
                body_files = row.get("private_body_files")
                if not isinstance(body_files, dict) or set(body_files) != (
                        {"5m", "30m", "1h", "4h"}):
                    raise ValueError("FRAME_ORIGINAL_BODIES_REQUIRED")
                verified = {x["file"]: x["sha256"] for x in
                            manifest["raw_body_receipts"]}
                for frame, record in body_files.items():
                    if (not isinstance(record, dict)
                            or verified.get(record.get("file")) != record.get("sha256")
                            or row.get("input_payload_sha256", {}).get(frame) != (
                                record.get("sha256"))):
                        raise ValueError("FRAME_TO_ORIGINAL_BYTES_MISMATCH")
                if any(r.get("signal_id") for r in evaluate(packet)):
                    raise ValueError("PRODUCTION_SIGNAL_FORBIDDEN")
                key = (symbol, packet.get("boundary_ms"))
                if key in unique:
                    if unique[key] != row["packet_sha256"]:
                        raise ValueError("CONFLICTING_SOURCE_SNAPSHOT")
                    continue
                unique[key] = row["packet_sha256"]
                symbols.add(symbol)
                statuses = evaluate(packet)
                for rec in statuses:
                    direction = rec["direction"]
                    if direction not in counts:
                        raise ValueError("UNSUPPORTED_DIRECTION")
                    counts[direction][rec["status"]] += 1
        except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError) as exc:
            # No silent source drops or raw payload in the public report.
            errors.append({"manifest_sha256": digest(mfile.read_bytes()),
                           "reason": type(exc).__name__,
                           "state": "REJECTED"})
    ordered = sorted(unique)
    result = {
        "schema": VERSION,
        "status": "SCIENCE_NOT_APPROVED",
        "source_authenticity": "PUBLIC_SOURCE_CAPTURE_SELF_ATTESTED_REVIEW_REQUIRED",
        "dataset_id_sha256": digest(canonical([
            [symbol, boundary, unique[(symbol, boundary)]] for symbol, boundary in ordered])),
        "manifests": len(entries),
        "manifest_chain_sha256": digest(canonical(manifest_hashes)),
        "symbol_count": len(symbols),
        "event_count": len(ordered),
        "candidate_counts_by_direction": {d: dict(c) for d, c in counts.items()},
        "rejected_manifests": errors,
        "frozen_hypotheses": "DEVELOPMENT_HYPOTHESES_ONLY_NOT_SCIENTIFICALLY_REGISTERED",
        "pit_d1_d5": "UNREVIEWED",
        "normalizers_12": "UNREVIEWED",
        "eligible_cost_model": "NOT_ADOPTED",
        "n_required": None,
        "dev": "SOURCE_INTAKE_ONLY",
        "oos": "NOT_OPENED_NO_PREREGISTRATION",
        "forward": "NOT_OBSERVED",
        "precision": None, "recall": None, "calibration": None,
        "return_after_costs": None,
        "up_real_science_decision": "NOT_QUALIFIED",
        "down_real_science_decision": "NOT_QUALIFIED",
        "qualification_registry_modified": False,
        "signals_created": 0,
        "scientific_blockers": [
            "INDEPENDENT_SOURCE_AND_CLOCK_WITNESS_PENDING",
            "D1_D5_PIT_AND_12_NORMALIZERS_NOT_APPROVED",
            "FROZEN_SCIENTIFIC_N_REQUIRED_AND_THRESHOLDS_ABSENT",
            "UNCHANGED_HOLDOUT_OOS_AND_FORWARD_OUTCOMES_ABSENT",
        ],
    }
    result["receipt_sha256"] = digest(canonical(result))
    return result
