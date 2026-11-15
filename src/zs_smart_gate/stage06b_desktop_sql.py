"""Stage06B offline Telegram Desktop export verification and SQL staging.

Pure source inspection plus explicit file readback. No credentials, network, auto-
connecting SQL, Bot API, polling or live transport. Chat/bot mapping is locally
declared; Telegram Desktop JSON cannot independently certify the Bot API bot ID.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re

from .stage05_contracts import (ARCHIVE_SCHEMA, ContractError, SHA, canonical,
                                digest, ensure_event, extract_desktop_export,
                                sql_projection)

SCHEMA = "zs.stage06b.desktop-sql-staging.v1"
MANIFEST = "zs.stage06b.owner-local-export-manifest.v1"
ROLE_BOTS = {
    "SIGNALS_A": "SIGNALS", "SIGNALS_B": "SIGNALS",
    "ANALYTICS_C": "ANALYTICS", "INTERACTIVE_A": "INTERACTIVE",
    "INTERACTIVE_B": "INTERACTIVE",
}
MAX_EXPORT = 64 * 1024 * 1024
MAX_ATTACH = 16 * 1024 * 1024
MAX_MESSAGES = 150000
PATH_PATTERN = re.compile(r"[A-Za-z0-9_. /()@+\-]{1,240}\Z")
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


def _id(x):
    if not isinstance(x, str) or not ID_PATTERN.fullmatch(x):
        raise ContractError("STAGE06B_ID_INVALID")
    return x


def _sha(x):
    if not isinstance(x, str) or not SHA.fullmatch(x):
        raise ContractError("STAGE06B_SHA_INVALID")
    return x


def _int(x):
    if isinstance(x, bool) or not isinstance(x, (int, str)):
        raise ContractError("STAGE06B_INTEGER_INVALID")
    if isinstance(x, str) and not re.fullmatch(r"[1-9][0-9]{0,17}", x):
        raise ContractError("STAGE06B_INTEGER_INVALID")
    try:
        n = int(x)
    except ValueError:
        raise ContractError("STAGE06B_INTEGER_INVALID") from None
    if not 0 < n < 2**63:
        raise ContractError("STAGE06B_INTEGER_INVALID")
    return n


def _relative(name):
    if (not isinstance(name, str) or not PATH_PATTERN.fullmatch(name)
            or name.startswith("/") or name.startswith(".")
            or "\\" in name or ":" in name or "//" in name):
        raise ContractError("STAGE06B_ATTACHMENT_PATH_UNSAFE")
    parts = name.split("/")
    if any(p in ("", ".", "..") or p.endswith(".") or p.endswith(" ") for p in parts):
        raise ContractError("STAGE06B_ATTACHMENT_PATH_UNSAFE")
    return name


def _read(root: Path, name: str, size: int, expected: str):
    _relative(name)
    _sha(expected)
    if type(size) is not int or not 0 <= size <= MAX_ATTACH:
        raise ContractError("STAGE06B_ATTACHMENT_SIZE_INVALID")
    if root.is_symlink():
        raise ContractError("STAGE06B_ATTACHMENT_REPARSE_FORBIDDEN")
    base = root.resolve(strict=True)
    path = base.joinpath(*name.split("/"))
    # Forbid symlinks/junctions on every component, including the root.
    cursor = base
    if base.is_symlink():
        raise ContractError("STAGE06B_ATTACHMENT_REPARSE_FORBIDDEN")
    for part in name.split("/"):
        cursor = cursor / part
        if cursor.is_symlink() or (os.name == "nt" and
            cursor.exists() and cursor.stat(follow_symlinks=False).st_file_attributes & 0x400):
            raise ContractError("STAGE06B_ATTACHMENT_REPARSE_FORBIDDEN")
    if not path.is_file() or path.resolve(strict=True).parent == path.resolve(strict=True):
        raise ContractError("STAGE06B_ATTACHMENT_MISSING")
    if os.path.commonpath((str(base), str(path.resolve()))) != str(base):
        raise ContractError("STAGE06B_ATTACHMENT_ESCAPE")
    if path.stat().st_size != size:
        raise ContractError("STAGE06B_ATTACHMENT_SIZE_MISMATCH")
    raw = path.read_bytes()
    if len(raw) != size or digest(raw) != expected:
        raise ContractError("STAGE06B_ATTACHMENT_SHA_MISMATCH")
    return raw


def _when(row):
    # Telegram Desktop date string is typically local/naive. The Unix integer
    # seconds is the unambiguous UTC value; never fabricate milliseconds.
    val = row.get("date_unixtime")
    if isinstance(val, bool) or not isinstance(val, (int, str)):
        raise ContractError("STAGE06B_UNIX_TIME_REQUIRED")
    if not re.fullmatch(r"[1-9][0-9]{8,11}", str(val)):
        raise ContractError("STAGE06B_UNIX_TIME_INVALID")
    try:
        t = datetime.fromtimestamp(int(val), tz=timezone.utc)
    except (OSError, ValueError, OverflowError):
        raise ContractError("STAGE06B_UNIX_TIME_INVALID") from None
    return t.isoformat(timespec="seconds").replace("+00:00", "Z")


def _text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                out.append(item["text"])
            else:
                raise ContractError("STAGE06B_MESSAGE_TEXT_INVALID")
        return "".join(out)
    raise ContractError("STAGE06B_MESSAGE_TEXT_INVALID")


def _manifest(row):
    fields = {"schema", "role", "bot_family", "bot_id", "chat_id",
              "export_chat_id", "export_sha256", "attachments", "manifest_sha256"}
    if not isinstance(row, dict) or set(row) != fields or row["schema"] != MANIFEST:
        raise ContractError("STAGE06B_MANIFEST_SCHEMA_INVALID")
    role = row["role"]
    if role not in ROLE_BOTS or ROLE_BOTS[role] != row["bot_family"]:
        raise ContractError("STAGE06B_ROLE_BOT_MISMATCH")
    for k in ("bot_id", "chat_id", "export_chat_id"):
        _int(row[k])
    _sha(row["export_sha256"])
    _sha(row["manifest_sha256"])
    if (not isinstance(row["attachments"], list)
            or len(row["attachments"]) > 10000):
        raise ContractError("STAGE06B_ATTACHMENT_MANIFEST_INVALID")
    names = set()
    for a in row["attachments"]:
        if not isinstance(a, dict) or set(a) != {"path", "sha256", "size_bytes"}:
            raise ContractError("STAGE06B_ATTACHMENT_ROW_INVALID")
        name = _relative(a["path"])
        if name in names:
            raise ContractError("STAGE06B_ATTACHMENT_DUPLICATE")
        names.add(name)
        _sha(a["sha256"])
        if type(a["size_bytes"]) is not int or not 0 <= a["size_bytes"] <= MAX_ATTACH:
            raise ContractError("STAGE06B_ATTACHMENT_SIZE_INVALID")
    unsigned = {k: v for k, v in row.items() if k != "manifest_sha256"}
    if digest(canonical(unsigned)) != row["manifest_sha256"]:
        raise ContractError("STAGE06B_MANIFEST_SHA_MISMATCH")


def build_sql_staging(sources: list[dict]) -> dict:
    """Each source: {manifest, raw_export: bytes, root: Path}; no implicit I/O elsewhere.

    Result stores only validated metadata and SHA-256, never private text or
    attachment bytes. Actual SQL commit requires separately supplied connection.
    """
    if not isinstance(sources, list) or not 1 <= len(sources) <= 5:
        raise ContractError("STAGE06B_EXPORT_COUNT_INVALID")
    seen_sources, seen_roles, messages, candidates, signals = set(), set(), {}, {}, {}
    decisions, indicators = {}, {}
    pending_signals = {}
    attachments = {}
    family_ids = {}
    for src in sources:
        if not isinstance(src, dict) or set(src) != {"manifest", "raw_export", "root"}:
            raise ContractError("STAGE06B_SOURCE_FIELDS_INVALID")
        m, raw, root = src["manifest"], src["raw_export"], src["root"]
        _manifest(m)
        if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_EXPORT:
            raise ContractError("STAGE06B_EXPORT_SIZE_INVALID")
        if digest(raw) != m["export_sha256"]:
            raise ContractError("STAGE06B_EXPORT_SHA_MISMATCH")
        try:
            export = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise ContractError("STAGE06B_EXPORT_JSON_INVALID") from None
        if (not isinstance(export, dict) or not isinstance(export.get("messages"), list)
                or len(export["messages"]) > MAX_MESSAGES
                or _int(export.get("id")) != _int(m["export_chat_id"])):
            raise ContractError("STAGE06B_EXPORT_CHAT_IDENTITY_MISMATCH")
        bot, chat = _int(m["bot_id"]), _int(m["chat_id"])
        family = m["bot_family"]
        if family in family_ids and family_ids[family] != bot:
            raise ContractError("STAGE06B_BOT_FAMILY_CONFLICT")
        if any(other != family and ident == bot for other, ident in family_ids.items()):
            raise ContractError("STAGE06B_BOT_ID_REUSED_ACROSS_FAMILIES")
        family_ids[family] = bot
        key = (m["role"], bot, chat)
        if key in seen_sources or m["role"] in seen_roles:
            raise ContractError("STAGE06B_SOURCE_DUPLICATE")
        seen_sources.add(key)
        seen_roles.add(m["role"])
        declared = {a["path"]: a for a in m["attachments"]}
        documents = {name: _read(Path(root), name, a["size_bytes"], a["sha256"])
                     for name, a in declared.items()}
        used = set()
        if m["role"] != "ANALYTICS_C":
            for msg in export["messages"]:
                if not isinstance(msg, dict):
                    raise ContractError("STAGE06B_MESSAGE_INVALID")
                if "ZS05_ARCHIVE_V1" in _text(msg.get("text", "")):
                    raise ContractError("STAGE06B_ANALYTICS_WRONG_CHANNEL")
        extracted = (extract_desktop_export(export, documents)
                     if m["role"] == "ANALYTICS_C" else None)
        archived = {}
        if extracted:
            for raw_event in extracted["events_ndjson"].splitlines():
                doc = json.loads(raw_event)
                event = doc["event"]
                ensure_event(event)
                archived[event["candidate_id"]] = (raw_event, event)
        for msg in export["messages"]:
            if not isinstance(msg, dict):
                raise ContractError("STAGE06B_MESSAGE_INVALID")
            number = _int(msg.get("id"))
            date = _when(msg)
            content = _text(msg.get("text", ""))
            if msg.get("type") not in ("message", "service"):
                raise ContractError("STAGE06B_MESSAGE_TYPE_INVALID")
            filepaths = []
            for field in ("file", "photo"):
                value = msg.get(field)
                if value not in (None, ""):
                    name = _relative(value)
                    if name not in documents:
                        raise ContractError("STAGE06B_ATTACHMENT_NOT_MANIFESTED")
                    filepaths.append(name)
                    used.add(name)
            if len(filepaths) > 1:
                raise ContractError("STAGE06B_MULTIPLE_MEDIA_PATHS_UNSUPPORTED")
            archive_sha, candidate_id, signal_id = None, None, None
            if "ZS05_ARCHIVE_V1" in content:
                if m["role"] != "ANALYTICS_C" or len(filepaths) != 1:
                    raise ContractError("STAGE06B_ANALYTICS_ATTACHMENT_REQUIRED")
                match = re.fullmatch(
                    r"ZS05_ARCHIVE_V1 sha256=([a-f0-9]{64}) candidate_id=([A-Za-z0-9._:-]+)"
                    r" state=(QUALIFIED|REJECTED) reject_reasons=.*", content, flags=re.DOTALL)
                if not match or match[1] != digest(documents[filepaths[0]]):
                    raise ContractError("STAGE06B_ANALYTICS_CAPTION_INVALID")
                archive_sha, candidate_id = match[1], _id(match[2])
                if candidate_id not in archived:
                    raise ContractError("STAGE06B_ARCHIVE_DOCUMENT_MISSING")
                archive_raw, ev = archived[candidate_id]
                if archive_raw != documents[filepaths[0]] or ev["qualification_status"] != match[3]:
                    raise ContractError("STAGE06B_ARCHIVE_IDENTITY_CONFLICT")
                signal_id = ev["signal_id"]
                projection = sql_projection(ev)
                for c in projection["candidates"]:
                    c_row = {
                        "candidate_id": _id(c["candidate_id"]),
                        "event_sha256": digest(canonical(ev)),
                        "asset_symbol": ev["symbol"],
                        "source_manifest_sha256": _sha(ev["source_manifest_sha256"]),
                        "qualification_status": ev["qualification_status"],
                    }
                    old = candidates.setdefault(candidate_id, c_row)
                    if old != c_row:
                        raise ContractError("STAGE06B_CANDIDATE_CONTENT_CONFLICT")
                for s in projection["signals"]:
                    skey = _id(s["signal_id"])
                    srow = {"signal_id": skey, "candidate_id": _id(s["candidate_id"])}
                    if signals.setdefault(skey, srow) != srow:
                        raise ContractError("STAGE06B_SIGNAL_CONFLICT")
                for gate in projection["candidate_decisions"]:
                    gkey = (_id(gate["candidate_id"]), _id(gate["gate_id"]))
                    packed = canonical(gate)
                    grow = {"candidate_id": gkey[0], "gate_id": gkey[1],
                            "payload_sha256": digest(packed), "payload_json": packed.decode("utf-8")}
                    if decisions.setdefault(gkey, grow) != grow:
                        raise ContractError("STAGE06B_GATE_CONFLICT")
                for feature in projection["indicator_values"]:
                    fkey = (_id(feature["candidate_id"]), _id(feature["indicator_id"]))
                    packed = canonical(feature)
                    frow = {"candidate_id": fkey[0], "indicator_id": fkey[1],
                            "payload_sha256": digest(packed), "payload_json": packed.decode("utf-8")}
                    if indicators.setdefault(fkey, frow) != frow:
                        raise ContractError("STAGE06B_INDICATOR_CONFLICT")
            msgkey = (bot, chat, number)
            if m["role"] in ("SIGNALS_A", "SIGNALS_B") and content.startswith("ZS05 SIGNAL | "):
                signal_match = re.match(
                    r"\AZS05 SIGNAL \| ([A-Za-z0-9._:-]{1,128})\n"
                    r"Candidate: ([A-Za-z0-9._:-]{1,128})\n"
                    r"Source scope: [^\n]+\nSymbol: ([A-Z0-9]+USDT)\n",
                    content)
                if not signal_match:
                    raise ContractError("STAGE06B_SIGNAL_TEXT_INVALID")
                pending_signals[msgkey] = (_id(signal_match[1]), _id(signal_match[2]),
                                           signal_match[3])
            row = {"bot_id": bot, "chat_id": chat, "message_id": number,
                   "role": m["role"], "telegram_date_utc": date,
                   "message_type": msg["type"],
                   "text_sha256": digest(content.encode("utf-8")),
                   "attachment_sha256": declared[filepaths[0]]["sha256"] if filepaths else None,
                   "archive_sha256": archive_sha, "candidate_id": candidate_id,
                   "signal_id": signal_id}
            if msgkey in messages and messages[msgkey] != row:
                raise ContractError("STAGE06B_MESSAGE_IDENTITY_CONFLICT")
            messages[msgkey] = row
        if used != set(declared):
            raise ContractError("STAGE06B_ORPHAN_ATTACHMENT_MANIFEST")
        for name in sorted(used):
            keya = (bot, chat, name)
            sha = declared[name]["sha256"]
            if keya in attachments and attachments[keya] != sha:
                raise ContractError("STAGE06B_ATTACHMENT_CONFLICT")
            attachments[keya] = sha
    # Cross-check A/B text identities against independently verified 05B
    # canonical documents before attaching any signal/candidate key.
    for msgkey, (signal_id, candidate_id, symbol) in pending_signals.items():
        verified = signals.get(signal_id)
        documented = candidates.get(candidate_id)
        if (verified is None or documented is None
                or verified["candidate_id"] != candidate_id
                or documented["asset_symbol"] != symbol):
            raise ContractError("STAGE06B_UNVERIFIED_SIGNAL_CROSS_CHAT")
        row = messages[msgkey]
        row["signal_id"] = signal_id
        row["candidate_id"] = candidate_id
    result = {
        "schema": SCHEMA,
        "trust": "OFFLINE_EXPORT_SHA_AND_LOCAL_MANIFEST_ONLY_BOT_MAPPING_DECLARED",
        "sql_executed": False,
        "sources_count": len(sources),
        "candidates": sorted(candidates.values(), key=lambda x: x["candidate_id"]),
        "signals": sorted(signals.values(), key=lambda x: x["signal_id"]),
        "candidate_decisions": [decisions[k] for k in sorted(decisions)],
        "indicator_values": [indicators[k] for k in sorted(indicators)],
        "messages": [messages[k] for k in sorted(messages)],
        "attachments": [
            {"bot_id": k[0], "chat_id": k[1], "path_sha256": digest(k[2].encode()),
             "attachment_sha256": value} for k, value in sorted(attachments.items())],
    }
    result["batch_sha256"] = digest(canonical(result))
    return result


def apply_sql_server(connection, packet: dict):
    """Opt-in DB-API SQL Server connection provided by caller; transactional.

    Never creates a connection and never logs private source text. Requires
    migration 006b before first use. Verify every row on readback before COMMIT.
    """
    if not isinstance(packet, dict) or packet.get("schema") != SCHEMA:
        raise ContractError("STAGE06B_PACKET_SCHEMA_INVALID")
    if digest(canonical({k: v for k, v in packet.items() if k != "batch_sha256"})) != packet.get("batch_sha256"):
        raise ContractError("STAGE06B_PACKET_SHA_INVALID")
    if getattr(connection, "autocommit", False) is not False:
        raise ContractError("STAGE06B_TRANSACTIONAL_CONNECTION_REQUIRED")
    cursor = connection.cursor()
    try:
        cursor.execute("SET XACT_ABORT ON")
        # Strict idempotence: existing identical rows are fine, divergent rows STOP.
        tables = [
            ("zs06b_candidates", ("candidate_id",), ("event_sha256", "asset_symbol", "source_manifest_sha256", "qualification_status"), packet["candidates"]),
            ("zs06b_signals", ("signal_id",), ("candidate_id",), packet["signals"]),
            ("zs06b_candidate_decisions", ("candidate_id", "gate_id"),
             ("payload_sha256", "payload_json"), packet["candidate_decisions"]),
            ("zs06b_indicator_values", ("candidate_id", "indicator_id"),
             ("payload_sha256", "payload_json"), packet["indicator_values"]),
            ("zs06b_messages", ("bot_id", "chat_id", "message_id"),
             ("role", "telegram_date_utc", "message_type", "text_sha256",
              "attachment_sha256", "archive_sha256", "candidate_id", "signal_id"), packet["messages"]),
            ("zs06b_attachments", ("bot_id", "chat_id", "path_sha256"),
             ("attachment_sha256",), packet["attachments"]),
        ]
        count = 0
        for table, pk, fields, rows in tables:
            for row in rows:
                keys = tuple(row[k] for k in pk)
                columns = pk + fields
                where = " AND ".join(k + "=?" for k in pk)
                previous = cursor.execute(
                    "SELECT " + ",".join(fields) + " FROM dbo." + table +
                    " WITH (UPDLOCK, HOLDLOCK) WHERE " + where, *keys).fetchone()
                current = tuple(row[k] for k in fields)
                if previous is not None:
                    # datetime2 readback may be Python datetime; compare UTC-second
                    # representation explicitly, not localized display strings.
                    old = tuple(
                        x.strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(x, datetime) else x
                        for x in previous)
                    if old != current:
                        raise ContractError("STAGE06B_SQL_EXISTING_ROW_CONFLICT")
                else:
                    stmt = ("INSERT INTO dbo." + table + " (" + ",".join(columns) +
                            ") VALUES (" + ",".join("?" for _ in columns) + ")")
                    values = [datetime.fromisoformat(row[k].replace("Z", "+00:00")).replace(tzinfo=None)
                              if k == "telegram_date_utc" else row[k] for k in columns]
                    cursor.execute(stmt, *values)
                reread = cursor.execute(
                    "SELECT " + ",".join(fields) + " FROM dbo." + table +
                    " WHERE " + where, *keys).fetchone()
                if reread is None:
                    raise ContractError("STAGE06B_SQL_READBACK_MISSING")
                reread = tuple(
                    x.strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(x, datetime) else x
                    for x in reread)
                if reread != current:
                    raise ContractError("STAGE06B_SQL_READBACK_CONFLICT")
                count += 1
        connection.commit()
        return {"schema": "zs.stage06b.sql-readback.v1",
                "batch_sha256": packet["batch_sha256"],
                "rows_verified": count, "transaction_committed": True}
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
