"""Owner-local Stage06B export reconstruction (NO NETWORK/SQL/BOT/TRADING).

Uses the private media report created by ZS_Stage06B_Disambiguate_Media.ps1.
Copies verified source bytes to NEW private staging folders only after all
referenced media are accounted for and a coherent export root is found.
Does not invent bot IDs, Chat IDs, signal authority, or SQL evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys

MAX_FILE = 16 * 1024 * 1024
MAX_EXPORT = 64 * 1024 * 1024
MEDIA_KEYS = ("file", "photo", "thumbnail", "video_file",
              "audio_file", "voice_file", "sticker_file")
VALID_PATH = re.compile(r"[A-Za-z0-9_. /()@+\-]{1,240}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
CAPTION = re.compile(r"ZS05_ARCHIVE_V1 sha256=([a-f0-9]{64})")
ROLES = {
    "ANALYTICS_C": "bot data and archive.json",
    "SIGNALS_MAIN": "bot signals main.json",
}
STAGED_ROLES = {"ANALYTICS_C": "ANALYTICS_C",
                "SIGNALS_MAIN": "SIGNALS_UNASSIGNED"}


class Hold(Exception):
    """Fail closed; expose only a fixed reason code on stdout."""


def sha(path: Path, limit: int) -> tuple[str, int]:
    if not path.is_file() or path.is_symlink() or (
        hasattr(path, "is_junction") and path.is_junction()
    ):
        raise Hold("SOURCE_NOT_PLAIN_FILE")
    size = path.stat().st_size
    if not 0 < size <= limit:
        raise Hold("SOURCE_FILE_SIZE_INVALID")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while part := stream.read(1024 * 1024):
            digest.update(part)
    if path.stat().st_size != size:
        raise Hold("SOURCE_FILE_CHANGED")
    return digest.hexdigest(), size


def safe_rel(value: str) -> Path:
    if not isinstance(value, str) or not VALID_PATH.fullmatch(value):
        raise Hold("MEDIA_RELATIVE_PATH_UNSUPPORTED")
    pure = PurePosixPath(value.replace("\\", "/"))
    if (pure.is_absolute() or not pure.parts or
            any(part in (".", "..") for part in pure.parts)):
        raise Hold("MEDIA_RELATIVE_PATH_UNSAFE")
    return Path(*pure.parts)


def text_of(row: dict) -> str:
    t = row.get("text", "")
    if isinstance(t, str):
        return t
    if isinstance(t, list):
        parts = []
        for v in t:
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, dict) and isinstance(v.get("text"), str):
                parts.append(v["text"])
            else:
                raise Hold("MESSAGE_TEXT_SHAPE_INVALID")
        return "".join(parts)
    raise Hold("MESSAGE_TEXT_SHAPE_INVALID")


def read_export(path: Path) -> tuple[str, list[dict], str, int]:
    original, size = sha(path, MAX_EXPORT)
    try:
        doc = json.loads(path.read_bytes())
    except (UnicodeDecodeError, ValueError):
        raise Hold("SOURCE_JSON_INVALID") from None
    if (not isinstance(doc, dict) or doc.get("type") not in
            ("bot_chat", "personal_chat") or
            not isinstance(doc.get("messages"), list) or
            len(doc["messages"]) > 150000 or
            not isinstance(doc.get("name"), str) or not doc["name"]):
        raise Hold("SOURCE_EXPORT_SHAPE_INVALID")
    return original, doc["messages"], doc["type"], size


def all_refs(base: Path):
    specs, exports = [], {}
    for role, filename in ROLES.items():
        src = base / filename
        digest, messages, kind, size = read_export(src)
        exports[role] = {"path": src, "sha256": digest,
                         "size": size, "count": len(messages), "type": kind}
        for msg in messages:
            if not isinstance(msg, dict):
                raise Hold("MESSAGE_INVALID")
            caption = CAPTION.search(text_of(msg))
            for field in MEDIA_KEYS:
                relative = msg.get(field)
                if relative in (None, ""):
                    continue
                rel = safe_rel(relative)
                expected = caption.group(1) if caption and field == "file" else None
                specs.append({"role": role, "field": field,
                              "relative_path": rel.as_posix(),
                              "expected_sha256": expected})
    return specs, exports


def candidates_report(base: Path) -> list[dict]:
    reports = sorted((base / "stage06b-private").glob(
        "LOCAL-MEDIA-CANDIDATES-*.json"), reverse=True)
    if not reports:
        raise Hold("PRIVATE_DISAMBIGUATION_REPORT_MISSING")
    try:
        rows = json.loads(reports[0].read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        raise Hold("PRIVATE_REPORT_INVALID") from None
    if not isinstance(rows, list):
        raise Hold("PRIVATE_REPORT_ROWS_INVALID")
    return rows


def prepare(base: Path):
    specs, exports = all_refs(base)
    rows = candidates_report(base)
    identity = lambda x: (x["role"], x["field"],
                          x["relative_path"].replace("\\", "/"),
                          x.get("expected_sha256"))
    if Counter(identity(x) for x in specs) != Counter(identity(x) for x in rows):
        raise Hold("PRIVATE_REPORT_EXPORT_REFERENCE_DRIFT")
    if len(specs) != 5:
        raise Hold("UNEXPECTED_MEDIA_REFERENCE_COUNT")
    verified, unverified, roots = 0, 0, set()
    selected = []
    for row in rows:
        role, field, relative, expected = identity(row)
        rel = safe_rel(relative)
        possible = row.get("candidates")
        if not isinstance(possible, list) or not possible:
            raise Hold("MEDIA_CANDIDATE_MISSING")
        observed = []
        for item in possible:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise Hold("PRIVATE_CANDIDATE_SHAPE_INVALID")
            path = Path(item["path"])
            if not path.is_absolute():
                raise Hold("PRIVATE_CANDIDATE_PATH_NOT_ABSOLUTE")
            got, size = sha(path, MAX_FILE)
            if got != item.get("sha256") or size != item.get("size_bytes"):
                raise Hold("MEDIA_CANDIDATE_CHANGED_SINCE_REPORT")
            # Exact relative path required, not merely a filename match.
            path_parts = tuple(p.casefold() for p in path.parts)
            rel_parts = tuple(p.casefold() for p in rel.parts)
            if len(path_parts) > len(rel_parts) and path_parts[-len(rel_parts):] == rel_parts:
                root = path.parents[len(rel_parts) - 1]
                observed.append((path, root, got, size))
        if not observed:
            raise Hold("MEDIA_RELATIVE_PATH_NOT_FOUND")
        hashes = {v[2] for v in observed}
        if expected:
            if not isinstance(expected, str) or not HEX64.fullmatch(expected):
                raise Hold("CAPTION_SHA_INVALID")
            observed = [v for v in observed if v[2] == expected]
            if not observed:
                raise Hold("CAPTION_SHA_NOT_FOUND")
            verified += 1
            roots.update(v[1] for v in observed)
        else:
            if len(hashes) != 1:
                raise Hold("UNATTESTED_MEDIA_CONTENT_CONFLICT")
            unverified += 1
        selected.append({"role": role, "relative": rel,
                         "expected": expected, "candidates": observed,
                         "sha256": observed[0][2], "size": observed[0][3]})
    if verified != 3 or unverified != 2:
        raise Hold("EXPECTED_ARCHIVE_PROOF_COUNT_CHANGED")
    # Each source role can use a different coherent root; never mix roots
    # for a single archive source or select by filename alone.
    selections = {}
    for role in ROLES:
        refs = [x for x in selected if x["role"] == role]
        if not refs:
            continue
        eligible = set(x[1] for x in refs[0]["candidates"])
        for ref in refs[1:]:
            eligible.intersection_update(x[1] for x in ref["candidates"])
        if not eligible:
            raise Hold("NO_COHERENT_EXPORT_MEDIA_ROOT")
        if role == "ANALYTICS_C":
            eligible.intersection_update(roots)
            if not eligible:
                raise Hold("NO_CAPTION_VERIFIED_EXPORT_ROOT")
        selections[role] = sorted(eligible, key=lambda v: str(v).casefold())[0]
    return exports, selected, selections, verified, unverified


def stage(base: Path, verified: bool = True):
    exports, refs, roots, matched, untrusted = prepare(base)
    target_root = base / "stage06b-private" / "exports"
    tasks = []
    for role, src in exports.items():
        dest = target_root / STAGED_ROLES[role] / "result.json"
        tasks.append((src["path"], dest, src["sha256"], src["size"]))
    for ref in refs:
        root = roots[ref["role"]]
        present = [c for c in ref["candidates"] if c[1] == root]
        if len(present) != 1:
            raise Hold("COHERENT_ROOT_DUPLICATE_PATH")
        source, _, hash_value, size = present[0]
        dest = target_root / STAGED_ROLES[ref["role"]] / ref["relative"]
        tasks.append((source, dest, hash_value, size))
    seen = {}
    for _, dst, expected, _ in tasks:
        key = str(dst).casefold()
        if key in seen and seen[key] != expected:
            raise Hold("STAGED_DESTINATION_CONTENT_CONFLICT")
        seen[key] = expected
    staged = 0
    for source, target, expected, size in tasks:
        got, length = sha(source, MAX_EXPORT if target.name == "result.json" else MAX_FILE)
        if got != expected or length != size:
            raise Hold("SOURCE_CHANGED_BEFORE_STAGING")
        if target.exists():
            old_hash, old_size = sha(target, MAX_EXPORT if target.name == "result.json" else MAX_FILE)
            if old_hash != expected or old_size != size:
                raise Hold("DESTINATION_ALREADY_EXISTS_DIFFERENT_CONTENT")
            continue
        if verified:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copy_hash, copy_size = sha(target, MAX_EXPORT if target.name == "result.json" else MAX_FILE)
            if copy_hash != expected or copy_size != size:
                target.unlink(missing_ok=True)
                raise Hold("STAGED_COPY_READBACK_FAILED")
            staged += 1
    evidence_dir = base / "stage06b-readiness"
    evidence_dir.mkdir(exist_ok=True)
    output = {
        "schema": "zs.stage06b.private-stage-custody.v1",
        "mode": "LOCAL_COPY_VERIFIED" if verified else "READ_ONLY",
        "source_export_count": len(exports),
        "message_count": sum(e["count"] for e in exports.values()),
        "media_references": len(refs),
        "caption_sha_matched": matched,
        "other_media_identical_bytes_not_independently_attested": untrusted,
        "coherent_source_roots": len(roots),
        "new_files_copied": staged,
        "sql_attempts": 0,
        "telegram_api_attempts": 0,
        "bot_identity_verified": False,
        "signals_account_assignment_verified": False,
        "real_sql_roundtrip_verified": False,
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe = evidence_dir / f"STAGING-{stamp}.json"
    safe.write_text(json.dumps(output, indent=2), encoding="utf-8")
    for key, value in output.items():
        if key not in ("schema", "mode"):
            print(f"{key.upper()}={str(value).upper() if isinstance(value, bool) else value}")
    print("STAGING=COMPLETED_LOCAL_ONLY")
    print(f"SAFE_REPORT={safe}")
    print("PRIVATE_PATHS_AND_EXPORT_BYTES_REMAIN_ON_D")
    return output


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=Path(r"D:\ZS-LOCAL-CI"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        stage(args.base, verified=not args.dry_run)
    except Hold as exc:
        print("STAGING=BLOCKED")
        print("STOP_REASON=" + str(exc))
        sys.exit(2)
    except Exception:
        # Do not reveal local filenames or private identifiers in errors.
        print("STAGING=BLOCKED")
        print("STOP_REASON=UNEXPECTED_LOCAL_SOURCE_ERROR")
        sys.exit(2)


if __name__ == "__main__":
    main()
