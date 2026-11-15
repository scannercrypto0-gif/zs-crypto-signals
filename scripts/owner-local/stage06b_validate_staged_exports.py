"""Stage06B owner-local contract validation of real staged Telegram exports.

No network, SQL connections, bots or trading; private files stay on D:.
Imports only the pinned existing Stage05 archive schema from the repository.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

from zs_smart_gate.stage05_contracts import ContractError, extract_desktop_export

SOURCE_MAIN = "8e323aa95871405f6227650753828f8781ed71d2"
BASE = Path(r"D:\ZS-LOCAL-CI")
PATH_OK = re.compile(r"[A-Za-z0-9_. /()@+\-]{1,240}\Z")
ROLES = {
    "ANALYTICS_C": "ANALYTICS_C",
    "SIGNALS_MAIN": "SIGNALS_UNASSIGNED",
}
MEDIA_FIELDS = ("file", "photo", "thumbnail", "video_file",
                "audio_file", "voice_file", "sticker_file")


class Stop(Exception):
    pass


def plain_file(path: Path, max_size: int) -> bytes:
    for part in (path, *path.parents):
        if not part.exists():
            continue
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise Stop("REPARSE_PATH_FORBIDDEN")
    if not path.is_file() or not 0 < path.stat().st_size <= max_size:
        raise Stop("STAGED_FILE_UNAVAILABLE_OR_TOO_LARGE")
    return path.read_bytes()


def safe_rel(name: str) -> Path:
    if (not isinstance(name, str) or not PATH_OK.fullmatch(name)
            or name.startswith(("/", ".")) or "\\" in name or
            ":" in name or "//" in name):
        raise Stop("MEDIA_PATH_UNSAFE")
    chunks = name.split("/")
    if any(c in ("", ".", "..") or c.endswith((".", " ")) for c in chunks):
        raise Stop("MEDIA_PATH_UNSAFE")
    return Path(*chunks)


def text_value(obj) -> str:
    val = obj.get("text", "")
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        out = []
        for piece in val:
            if isinstance(piece, str):
                out.append(piece)
            elif isinstance(piece, dict) and isinstance(piece.get("text"), str):
                out.append(piece["text"])
            else:
                raise Stop("MESSAGE_TEXT_SHAPE_UNSUPPORTED")
        return "".join(out)
    raise Stop("MESSAGE_TEXT_SHAPE_UNSUPPORTED")


def main(base: Path):
    custody = sorted((base / "stage06b-private").glob("PRIVATE-STAGING-CUSTODY-*.json"), reverse=True)
    if not custody:
        raise Stop("PRIVATE_CUSTODY_REPORT_MISSING")
    try:
        report = json.loads(plain_file(custody[0], 1024 * 1024))
    except (ValueError, UnicodeDecodeError):
        raise Stop("PRIVATE_CUSTODY_REPORT_INVALID") from None
    if (not isinstance(report, dict) or
            report.get("schema") != "zs.stage06b.local-private-custody.v1" or
            report.get("source_main_sha") != SOURCE_MAIN or
            report.get("role_assignment") != "SIGNALS_MAIN_UNASSIGNED_A_OR_B"):
        raise Stop("PRIVATE_CUSTODY_SCHEMA_OR_VERSION_INVALID")
    originals, attachments = report.get("export_inputs"), report.get("media")
    if (not isinstance(originals, list) or len(originals) != 2 or
            not isinstance(attachments, list) or len(attachments) != 5):
        raise Stop("PRIVATE_CUSTODY_COUNTS_INVALID")
    exports = {}
    staged_root = base / "stage06b-private" / "exports"
    for item in originals:
        if not isinstance(item, dict) or item.get("role") not in ROLES:
            raise Stop("EXPORT_ROLE_INVALID")
        role = item["role"]
        if role in exports:
            raise Stop("DUPLICATE_EXPORT_ROLE")
        file = staged_root / ROLES[role] / "result.json"
        if Path(item.get("staged_path", "")).resolve() != file.resolve():
            raise Stop("STAGED_EXPORT_PATH_DRIFT")
        raw = plain_file(file, 64 * 1024 * 1024)
        if (len(raw) != item.get("size_bytes") or
                hashlib.sha256(raw).hexdigest() != item.get("sha256")):
            raise Stop("STAGED_EXPORT_SHA_MISMATCH")
        try:
            parsed = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise Stop("STAGED_EXPORT_JSON_INVALID") from None
        if (not isinstance(parsed, dict) or parsed.get("type") != "bot_chat"
                or not isinstance(parsed.get("messages"), list)
                or len(parsed["messages"]) > 150000):
            raise Stop("EXPORT_NOT_BOT_CHAT")
        exports[role] = parsed

    content = {}
    caption_count = 0
    unattested_count = 0
    for entry in attachments:
        if not isinstance(entry, dict) or entry.get("role") not in ROLES:
            raise Stop("MEDIA_ROLE_INVALID")
        rel = safe_rel(entry.get("relative_path"))
        file = staged_root / ROLES[entry["role"]] / rel
        blob = plain_file(file, 16 * 1024 * 1024)
        if (len(blob) != entry.get("size_bytes") or
                hashlib.sha256(blob).hexdigest() != entry.get("sha256")):
            raise Stop("STAGED_MEDIA_SHA_MISMATCH")
        trust = entry.get("trust")
        if trust == "CAPTION_HASH_MATCH":
            caption_count += 1
        elif trust == "MULTIPLE_COPIES_SAME_BYTES_NO_CAPTION_HASH":
            unattested_count += 1
        else:
            raise Stop("MEDIA_TRUST_LABEL_INVALID")
        item_key = (entry["role"], rel.as_posix())
        if item_key in content and content[item_key] != blob:
            raise Stop("DUPLICATE_MEDIA_CONFLICT")
        content[item_key] = blob

    if caption_count != 3 or unattested_count != 2:
        raise Stop("MEDIA_PROVENANCE_COUNTS_DRIFT")
    media_ref_count = 0
    message_count = 0
    signal_text_count = 0
    for role, exp in exports.items():
        seen_ids = set()
        for msg in exp["messages"]:
            if not isinstance(msg, dict):
                raise Stop("MESSAGE_SHAPE_INVALID")
            mid = msg.get("id")
            if isinstance(mid, bool) or not isinstance(mid, int) or mid <= 0:
                raise Stop("MESSAGE_ID_INVALID")
            if mid in seen_ids:
                raise Stop("DUPLICATE_MESSAGE_ID")
            seen_ids.add(mid)
            message_count += 1
            if role == "SIGNALS_MAIN" and text_value(msg).startswith("ZS05 SIGNAL | "):
                signal_text_count += 1
            for field in MEDIA_FIELDS:
                p = msg.get(field)
                if p in (None, ""):
                    continue
                rel = safe_rel(p).as_posix()
                if (role, rel) not in content:
                    raise Stop("MESSAGE_MEDIA_NOT_IN_PRIVATE_CUSTODY")
                media_ref_count += 1
    if media_ref_count != len(attachments):
        raise Stop("MEDIA_REFERENCE_COUNT_DRIFT")
    documents = {
        relative: blob
        for (role, relative), blob in content.items()
        if role == "ANALYTICS_C"
    }
    try:
        validated = extract_desktop_export(exports["ANALYTICS_C"], documents)
    except ContractError as exc:
        raise Stop("ARCHIVE_CONTRACT_" + str(exc).split(":")[0]) from None
    if validated["archive_count"] > caption_count:
        raise Stop("ARCHIVE_COUNT_EXCEEDS_SIGNED_CAPTIONS")
    # This is archival contract verification only, not independently authenticated
    # Telegram identity, SQL import or a qualified signal/filled trade.
    return {
        "schema": "zs.stage06b.owner-local-real-archive-validation.v1",
        "source_main_sha": SOURCE_MAIN,
        "exports_validated": len(exports),
        "messages_validated": message_count,
        "media_references_verified_against_private_custody": media_ref_count,
        "caption_sha_matched": caption_count,
        "media_identical_bytes_not_origin_attested": unattested_count,
        "canonical_stage05_archives_verified": validated["archive_count"],
        "signals_text_marker_count_unqualified": signal_text_count,
        "signals_account_assignment_verified": False,
        "bot_identity_verified": False,
        "local_sql_connection_attempts": 0,
        "sql_writes": 0,
        "production_or_trading_enabled": False,
        "real_sql_roundtrip_verified": False,
        "contract_validation_pass": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=BASE)
    args = parser.parse_args()
    try:
        result = main(args.base)
        folder = args.base / "stage06b-readiness"
        folder.mkdir(exist_ok=True)
        path = folder / ("REAL-ARCHIVE-VALIDATION-" +
                         datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + ".json")
        path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        for key, value in result.items():
            if key not in ("schema", "source_main_sha"):
                print(f"{key.upper()}={str(value).upper() if isinstance(value, bool) else value}")
        print("REAL_ARCHIVE_VALIDATION=PASS_NO_SQL")
        print("SAFE_REPORT=" + str(path))
        print("PRIVATE_IDENTIFIERS_AND_SOURCE_CONTENT_NOT_PRINTED")
    except Stop as exc:
        print("REAL_ARCHIVE_VALIDATION=STOP")
        print("STOP_REASON=" + str(exc))
        sys.exit(2)
    except Exception:
        print("REAL_ARCHIVE_VALIDATION=STOP")
        print("STOP_REASON=UNEXPECTED_SOURCE_EXCEPTION")
        sys.exit(2)
