"""Stage06B local bot/chat identity evidence inventory. Offline, no SQL, no APIs.

Never displays raw IDs, names, messages, usernames, credentials, or paths.
A private local file contains potential ID observations, not trusted/approved mapping.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(r"D:\ZS-LOCAL-CI")
ROLE_PATHS = {
    "ANALYTICS_C": Path("ANALYTICS_C/result.json"),
    "SIGNALS_UNASSIGNED": Path("SIGNALS_UNASSIGNED/result.json"),
}
FROM_ID = re.compile(r"user([1-9][0-9]{0,17})\Z")
MAX_BYTES = 64 * 1024 * 1024


class Stop(Exception):
    pass


def read_regular_file(path, max_bytes):
    for p in (path, *path.parents):
        if p.exists() and (p.is_symlink() or (
            hasattr(p, "is_junction") and p.is_junction()
        )):
            raise Stop("REPARSE_PATH_FORBIDDEN")
    if not path.is_file() or not 0 < path.stat().st_size <= max_bytes:
        raise Stop("STAGED_FILE_NOT_PLAIN_OR_SIZE_INVALID")
    return path.read_bytes()


def numeric(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    if isinstance(value, str) and not re.fullmatch(r"[1-9][0-9]{0,17}", value):
        return None
    try:
        number = int(value)
    except ValueError:
        return None
    return number if 0 < number < 2**63 else None


def main(base):
    reports = sorted((base / "stage06b-private").glob(
        "PRIVATE-STAGING-CUSTODY-*.json"), reverse=True)
    if not reports:
        raise Stop("CUSTODY_REPORT_NOT_FOUND")
    try:
        custody = json.loads(read_regular_file(reports[0], 1024 * 1024))
    except (ValueError, UnicodeDecodeError):
        raise Stop("CUSTODY_REPORT_INVALID") from None
    if (custody.get("schema") != "zs.stage06b.local-private-custody.v1"
            or custody.get("role_assignment") != "SIGNALS_MAIN_UNASSIGNED_A_OR_B"):
        raise Stop("CUSTODY_VERSION_OR_MAPPING_INVALID")
    hashes = {}
    items = custody.get("export_inputs")
    if not isinstance(items, list) or len(items) != 2:
        raise Stop("CUSTODY_EXPORT_COUNT_INVALID")
    for item in items:
        if item.get("role") == "ANALYTICS_C":
            hashes["ANALYTICS_C"] = item["sha256"]
        elif item.get("role") == "SIGNALS_MAIN":
            hashes["SIGNALS_UNASSIGNED"] = item["sha256"]
        else:
            raise Stop("CUSTODY_ROLE_UNEXPECTED")
    if len(hashes) != 2:
        raise Stop("CUSTODY_ROLE_DUPLICATE")
    observations = {}
    for role, relative in ROLE_PATHS.items():
        full = base / "stage06b-private" / "exports" / relative
        blob = read_regular_file(full, MAX_BYTES)
        if hashlib.sha256(blob).hexdigest() != hashes[role]:
            raise Stop("EXPORT_SHA_MISMATCH")
        try:
            archive = json.loads(blob)
        except (ValueError, UnicodeDecodeError):
            raise Stop("EXPORT_JSON_INVALID") from None
        if (not isinstance(archive, dict) or
                archive.get("type") != "bot_chat" or
                not isinstance(archive.get("messages"), list)):
            raise Stop("EXPORT_SHAPE_UNEXPECTED")
        export_id = numeric(archive.get("id"))
        if export_id is None:
            raise Stop("EXPORT_PEER_ID_NOT_POSITIVE_INTEGER")
        senders = set()
        inbound = 0
        for msg in archive["messages"]:
            if not isinstance(msg, dict):
                raise Stop("MESSAGE_SHAPE_INVALID")
            sender = msg.get("from_id")
            if not isinstance(sender, str):
                continue
            match = FROM_ID.fullmatch(sender)
            if match:
                senders.add(int(match.group(1)))
                if int(match.group(1)) == export_id:
                    inbound += 1
        if not senders:
            raise Stop("NO_SENDER_ID_EVIDENCE")
        human_candidates = sorted(senders - {export_id})
        observations[role] = {
            "role": role,
            "export_peer_id_OBSERVED_NOT_VERIFIED_BOT_ID": export_id,
            "telegram_sender_ids_OBSERVED_NOT_VERIFIED": sorted(senders),
            "non_peer_sender_ids_POSSIBLE_ACCOUNT_IDS_NOT_VERIFIED": human_candidates,
            "peer_id_seen_as_sender": export_id in senders,
            "peer_sender_message_count": inbound,
            "export_sha256": hashlib.sha256(blob).hexdigest(),
            "message_count": len(archive["messages"]),
        }
    archive_non_peer = set(observations["ANALYTICS_C"][
        "non_peer_sender_ids_POSSIBLE_ACCOUNT_IDS_NOT_VERIFIED"])
    signals_non_peer = set(observations["SIGNALS_UNASSIGNED"][
        "non_peer_sender_ids_POSSIBLE_ACCOUNT_IDS_NOT_VERIFIED"])
    common_non_peer = sorted(archive_non_peer.intersection(signals_non_peer))
    # Shared sender ID is a metadata hint, not proof of Bot API chat_id
    # or proof that the signals chat belongs to authorized account A/B.
    status = {
        "schema": "zs.stage06b.local-identity-metadata-scan.v1",
        "mode": "READ_ONLY_METADATA",
        "export_files_verified": len(observations),
        "messages_total": sum(o["message_count"] for o in observations.values()),
        "bot_peer_id_numeric_fields_present": len(observations),
        "peer_as_sender_seen_in_both_exports": all(
            o["peer_id_seen_as_sender"] for o in observations.values()),
        "analytics_non_peer_sender_id_count": len(archive_non_peer),
        "signals_non_peer_sender_id_count": len(signals_non_peer),
        "shared_non_peer_sender_id_count": len(common_non_peer),
        "signal_account_A_or_B_confirmed": False,
        "bot_identity_independently_authenticated": False,
        "bot_api_chat_id_independently_authenticated": False,
        "owner_mapping_manifest_approved": False,
        "sql_connection_attempts": 0,
        "sql_writes": 0,
        "telegram_api_calls": 0,
    }
    now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    private = base / "stage06b-private"
    private_file = private / f"LOCAL-ID-MAPPING-REVIEW-{now}.json"
    private_data = {
        "schema": "zs.stage06b.owner-local-mapping-review.v1",
        "status": "OWNER_REVIEW_REQUIRED_NOT_AUTHORIZED_FOR_SQL_IMPORT",
        "evidence": observations,
        "overlap_hint_OBSERVED_NOT_APPROVED": common_non_peer,
        "requires_owner_confirmation": [
            "ANALYTICS_C_bot_identity", "ANALYTICS_C_authorized_Chat_C",
            "SIGNALS_export_is_A_or_B", "SIGNALS_bot_identity",
            "SIGNALS_authorized_chat", "target_SQL_is_nonproduction"
        ],
        "do_not_infer_from_export": ["bot_token", "bot_api_chat_id", "account_A_or_B"],
    }
    private_file.write_text(json.dumps(private_data, indent=2, sort_keys=True),
                            encoding="utf-8")
    safe_dir = base / "stage06b-readiness"
    safe_dir.mkdir(exist_ok=True)
    safe_path = safe_dir / f"IDENTITY-READINESS-{now}.json"
    safe_path.write_text(json.dumps(status, indent=2, sort_keys=True),
                         encoding="utf-8")
    for k, v in status.items():
        if k not in ("schema", "mode"):
            print(f"{k.upper()}={str(v).upper() if isinstance(v, bool) else v}")
    print("IDENTITY_PREFLIGHT=COMPLETE_LOCAL_REVIEW_REQUIRED")
    print("SAFE_REPORT=" + str(safe_path))
    print("PRIVATE_REVIEW=LOCAL_ONLY_DO_NOT_UPLOAD")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        main(args.base)
    except Stop as exc:
        print("IDENTITY_PREFLIGHT=BLOCKED")
        print("STOP_REASON=" + str(exc))
        sys.exit(2)
    except Exception:
        print("IDENTITY_PREFLIGHT=BLOCKED")
        print("STOP_REASON=UNEXPECTED_LOCAL_ERROR")
        sys.exit(2)
