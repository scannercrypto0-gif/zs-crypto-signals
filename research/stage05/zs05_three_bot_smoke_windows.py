#!/usr/bin/env python3
"""Stage05 isolated owner-only TEST-ONLY three-bot Telegram smoke (no scanner).

--dry-run is DEFAULT and uses no network, secrets, or writes.
--execute needs owner approval on exact script SHA, PR head/tree SHA and local Windows.
Do not run --execute until PM review and new explicit owner authorization.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

SOURCE_PATH = "research/stage05/zs05_three_bot_smoke_windows.py"
BRANCH = "refs/remotes/origin/stage05-real-telegram-transport-disabled-20261109"
DEFAULT_REPO = r"D:\ZS Crypto Signals Latest Version"
ROOT = Path(r"D:\ZS_STAGE05_LOCAL_TEMP")
EXPECTED_USERNAMES = {"05A": "zscryptosignalsbot", "05B": "cryptosignalsdatabot",
                      "05C": "cryptosignalsanalysisbot"}
BOT_TOKEN = re.compile(r"([0-9]{5,15}):[A-Za-z0-9_-]{20,80}\Z")
PRIVATE_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
SHA = re.compile(r"[0-9a-f]{40,64}\Z")
TIMEOUT = 8
MAX_UPDATES = 6
MAX_CALLS = 17
API_ROOT = "https://api.telegram.org/bot"


class StopSmoke(Exception):
    """Only constant sanitized reason codes may be emitted."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise StopSmoke("HTTP_REDIRECT_REFUSED")


# No environment proxy, no redirects. HTTPS endpoint is fixed in api().
OPENER = build_opener(ProxyHandler({}), NoRedirect())


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def check_routes(a, b, c, interactive_ids, tokens):
    if not all(isinstance(x, str) and PRIVATE_ID.fullmatch(x) for x in (a, b, c)):
        raise StopSmoke("PRIVATE_CHAT_IDS_REQUIRED")
    if a == b or c != a:
        raise StopSmoke("OWNER_ROUTING_A_NOT_B_C_EQUALS_A_REQUIRED")
    if set(interactive_ids) != {a, b} or len(interactive_ids) != 2:
        raise StopSmoke("EXACT_TWO_INTERACTIVE_ACCOUNTS_REQUIRED")
    if len(tokens) != 3 or len(set(tokens.values())) != 3 or not all(
            isinstance(x, str) and BOT_TOKEN.fullmatch(x) for x in tokens.values()):
        raise StopSmoke("THREE_DISTINCT_BOT_TOKENS_REQUIRED")


def fixtures(case):
    result = {}
    for label in ("TEST_ONLY_QUALIFIED_FIXTURE", "TEST_ONLY_REJECTED_FIXTURE"):
        payload = {"test_only": True, "test_case_id": case, "kind": label,
                   "candidate_id": "SYNTHETIC_TEST_CASE_ONLY", "signal_id": None,
                   "qualification_status": "TEST_ONLY_NOT_EVALUATED",
                   "market_data": "NOT_USED", "approved_live_snapshot": None,
                   "indicators": [], "trade_plan": None, "sql_import": "NOT_ATTEMPTED"}
        wrapper = {"schema_version": "zs05.test-smoke.v1", "test_case_id": case,
                   "payload_sha256": digest(encoded(payload)), "payload": payload}
        body = encoded(wrapper)
        result[label] = (label.lower() + ".json", body, digest(body))
    return result


def test_plan():
    fake = {"05A": "123456:" + "A" * 30,
            "05B": "234567:" + "B" * 30,
            "05C": "345678:" + "C" * 30}
    check_routes("1001", "1002", "1001", ("1001", "1002"), fake)
    case = "SYNTHETIC_DRY_RUN_ONLY"
    docs = fixtures(case)
    return {"mode": "DRY_RUN_NO_NETWORK", "routing": "A!=B,C=A,05C=A+B",
            "identities": EXPECTED_USERNAMES,
            "operations": [
                "05A getMe", "05B getMe", "05C getMe", "05C getWebhookInfo",
                "05A sendMessage A TEST ONLY", "05A sendMessage B TEST ONLY",
                "05B sendMessage C=A TEST ONLY",
                "05B sendDocument C=A qualified TEST ONLY JSON",
                "05B sendDocument C=A rejected TEST ONLY JSON",
                "05C getUpdates x<=6 no offset advancement",
                "05C sendMessage reply A TEST ONLY", "05C sendMessage reply B TEST ONLY"],
            "sample_message": "ZS05 TEST ONLY — NOT A TRADING SIGNAL",
            "sample_response": "TEST ONLY / NO_APPROVED_LIVE_SNAPSHOT / NOT_REALTIME_VERIFIED",
            "archive_documents": [{"kind": k, "bytes": len(v[1]), "sha256": v[2],
                                   "payload_sha256": json.loads(v[1])["payload_sha256"]}
                                  for k, v in docs.items()],
            "maximum_api_calls": MAX_CALLS, "real_http_calls": 0, "secrets_requested": False,
            "production": False}


def git_value(repo, *args):
    try:
        done = subprocess.run(["git", "-C", str(repo), *args], timeout=8,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise StopSmoke("PINNED_GIT_CHECK_UNAVAILABLE") from None
    if done.returncode != 0:
        raise StopSmoke("PINNED_GIT_CHECK_FAILED")
    return done.stdout


def verify_pins(repo, head, tree, script_sha):
    if os.name != "nt" or not Path(repo).is_dir() or Path(repo).resolve().drive.upper() != "D:":
        raise StopSmoke("OWNER_WINDOWS_D_DRIVE_REQUIRED")
    if not (re.fullmatch(r"[0-9a-f]{40}", head) and
            re.fullmatch(r"[0-9a-f]{40}", tree) and
            re.fullmatch(r"[0-9a-f]{64}", script_sha)):
        raise StopSmoke("EXACT_SHA_ARGUMENTS_REQUIRED")
    if git_value(repo, "rev-parse", "--verify", BRANCH).decode("ascii").strip() != head:
        raise StopSmoke("PR_BRANCH_HEAD_MOVED_OR_NOT_FETCHED")
    if git_value(repo, "rev-parse", head + "^{tree}").decode("ascii").strip() != tree:
        raise StopSmoke("GIT_TREE_SHA_MISMATCH")
    raw_script = Path(__file__).read_bytes()
    if digest(raw_script) != script_sha:
        raise StopSmoke("LOCAL_SCRIPT_SHA_MISMATCH")
    if git_value(repo, "show", head + ":" + SOURCE_PATH) != raw_script:
        raise StopSmoke("SCRIPT_BYTES_DIFFER_FROM_PINNED_TREE")
    return digest(raw_script)


def hidden_token(label):
    value = getpass.getpass(label + " token (hidden): ").strip()
    if not BOT_TOKEN.fullmatch(value):
        raise StopSmoke("TOKEN_FORMAT_INVALID")
    return value


def hidden_id(label):
    value = getpass.getpass(label + " private ID (hidden): ").strip()
    if not PRIVATE_ID.fullmatch(value):
        raise StopSmoke("PRIVATE_CHAT_ID_FORMAT_INVALID")
    return value


def identity(token, obj, role):
    match = BOT_TOKEN.fullmatch(token)
    if not (isinstance(obj, dict) and obj.get("is_bot") is True and
            isinstance(obj.get("id"), int) and not isinstance(obj["id"], bool) and
            str(obj["id"]) == match.group(1) and
            str(obj.get("username", "")).casefold() == EXPECTED_USERNAMES[role]):
        raise StopSmoke("GETME_BOT_ROLE_IDENTITY_MISMATCH")
    return obj["id"]


def limit_counter(state):
    state["api_calls"] += 1
    if state["api_calls"] > MAX_CALLS:
        raise StopSmoke("API_CALL_LIMIT_17_EXCEEDED")


def api(state, token, method, data=None, document=None):
    if method not in {"getMe", "getWebhookInfo", "getUpdates", "sendMessage", "sendDocument"}:
        raise StopSmoke("API_METHOD_FORBIDDEN")
    if document is not None and method != "sendDocument":
        raise StopSmoke("DOCUMENT_METHOD_MISMATCH")
    limit_counter(state)  # Counts ATTEMPTS, including timeouts and errors.
    url = API_ROOT + token + "/" + method  # fixed api.telegram.org, never log URL
    if document is None:
        payload = encoded(data or {})
        headers = {"Content-Type": "application/json"}
    else:
        filename, blob = document
        if not re.fullmatch(r"[a-z0-9_-]{1,100}\.json", filename) or len(blob) > 16384:
            raise StopSmoke("TEST_DOCUMENT_CONTRACT_INVALID")
        boundary = "ZS05" + secrets.token_hex(12)
        fields = b""
        for name in ("chat_id", "caption"):
            fields += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
                       + str(data[name]).encode() + b"\r\n")
        payload = (fields + f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{filename}"\r\nContent-Type: application/json\r\n\r\n'.encode()
                   + blob + f'\r\n--{boundary}--\r\n'.encode())
        headers = {"Content-Type": "multipart/form-data; boundary=" + boundary}
    try:
        with OPENER.open(Request(url, data=payload, method="POST", headers=headers),
                         timeout=TIMEOUT) as response:
            if response.status != 200:
                raise StopSmoke("HTTP_NON_200_STOP_UNKNOWN")
            raw = response.read(65537)
    except HTTPError as e:
        # HTTPError contains a token-bearing URL: never stringify or chain.
        raise StopSmoke("HTTP_ERROR_STOP_UNKNOWN") from None
    except StopSmoke:
        raise
    except (URLError, TimeoutError, OSError, ConnectionError):
        raise StopSmoke("NETWORK_TIMEOUT_STOP_UNKNOWN") from None
    if len(raw) > 65536:
        raise StopSmoke("API_RESPONSE_TOO_LARGE_UNKNOWN")
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeError):
        raise StopSmoke("API_RESPONSE_INVALID_UNKNOWN") from None
    if not isinstance(obj, dict) or obj.get("ok") is not True:
        raise StopSmoke("API_REJECTED_STOP_UNKNOWN")
    return obj.get("result")


def accepted_message(obj):
    if not isinstance(obj, dict) or type(obj.get("message_id")) is not int or obj["message_id"] < 1:
        raise StopSmoke("SEND_RECEIPT_UNKNOWN")
    stamp = obj.get("date")
    return {"status": "API_ACCEPTED", "owner_seen": "UNKNOWN",
            "telegram_message_id_LOCAL_ONLY": obj["message_id"],
            "telegram_server_utc": (datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                                    if type(stamp) is int else None)}


def private_folder(root, name):
    if os.name != "nt" or root.drive.upper() != "D:":
        raise StopSmoke("PRIVATE_WINDOWS_EVIDENCE_REQUIRED")
    root.mkdir(parents=True, exist_ok=True)
    folder = root / name
    try:
        folder.mkdir(exist_ok=False)
        me = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], timeout=8,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
        row = next(csv.reader(io.StringIO(me.stdout.decode("utf-8-sig", errors="replace"))))
        sid = row[-1].strip()
        if not re.fullmatch(r"S-1-[0-9-]+", sid):
            raise StopSmoke("WINDOWS_USER_SID_UNAVAILABLE")
        acls = subprocess.run(["icacls", str(folder), "/inheritance:r", "/grant:r",
                               "*" + sid + ":(OI)(CI)F"], timeout=8,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              check=False)
        if acls.returncode != 0:
            raise StopSmoke("PRIVATE_ACL_SETUP_FAILED")
    except (OSError, ValueError, StopIteration, subprocess.CalledProcessError,
            subprocess.TimeoutExpired):
        raise StopSmoke("PRIVATE_ACL_SETUP_FAILED") from None
    return folder


def write_report(folder, result):
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"
    with (folder / "local_evidence.json").open("xb") as stream:
        stream.write(payload)
    # Separate SHAREABLE sanitized log: no token, URL, user/chat/message IDs.
    summary = {
        "test_only": True, "script_sha256": result["script_sha256"],
        "source_head": result["source_head"], "source_tree": result["source_tree"],
        "python_version": result["python_version"],
        "finished_utc": result["finished_utc"],
        "routing_verified": result["routing_verified"],
        "identity": result["identity"], "webhook": result["webhook"],
        "api_calls": result["api_calls"], "max_api_calls": MAX_CALLS,
        "sends": {key: {"status": value["status"], "owner_seen": value["owner_seen"]}
                  for key, value in result["sends"].items()},
        "updates": result["updates"], "authorized_query_roles": result["authorized_queries"],
        "documents": result["documents"], "status": result["status"],
        "exit_code": result["exit_code"], "retry_count": 0,
        "local_evidence_sha256": digest(payload),
    }
    log_bytes = encoded(summary) + b"\n"
    with (folder / "sanitized_log.json").open("xb") as stream:
        stream.write(log_bytes)
    return digest(payload), digest(log_bytes)


def run_execute(args):
    # FIRST verify local Windows, exact code/tree and script before any secrets.
    script_sha = verify_pins(args.repo, args.head_sha, args.tree_sha, args.script_sha256)
    tokens = {role: hidden_token(role) for role in ("05A", "05B", "05C")}
    a, b, c = hidden_id("Account A"), hidden_id("Account B"), hidden_id("Archive C")
    check_routes(a, b, c, (a, b), tokens)
    if input("Type exact owner acknowledgement ZS05 TEST ONLY: ").strip() != "ZS05 TEST ONLY":
        raise StopSmoke("OWNER_ACK_NOT_GRANTED")
    # No second attempt with same approved code/tree. Reserve BEFORE network.
    key = digest((script_sha + args.tree_sha).encode())[:18]
    folder = private_folder(ROOT, "three-bot-smoke-" + key)
    state = {"schema_version": "zs05.owner-test-evidence.v1", "test_only": True,
             "source_head": args.head_sha, "source_tree": args.tree_sha,
             "script_sha256": script_sha, "started_utc": utc(), "api_calls": 0,
             "routing_verified": "A_DISTINCT_B__C_EQUALS_A", "identity": "PENDING",
             "webhook": "NOT_CHECKED", "sends": {}, "updates": "NOT_ATTEMPTED",
             "authorized_queries": [], "owner_confirmation": "NOT_VERIFIED",
             "live_market": False, "scanner": False, "sql_server": False,
             "production": False, "retry_count": 0, "status": "UNKNOWN"}
    case = "ZS05-TEST-" + secrets.token_hex(8)
    docs = fixtures(case)
    state["documents"] = {k: {"document_sha256": blob[2],
                              "payload_sha256": json.loads(blob[1])["payload_sha256"]}
                          for k, blob in docs.items()}

    def send(label, role, method, data, document=None):
        if label in state["sends"]:
            raise StopSmoke("DUPLICATE_SEND_BLOCKED")
        # Persist intent in memory before one, and only one, HTTP attempt.
        state["sends"][label] = {"status": "UNKNOWN", "owner_seen": "UNKNOWN"}
        result = api(state, tokens[role], method, data, document)
        state["sends"][label] = accepted_message(result)
        print(label + "=API_ACCEPTED")  # No IDs or private message content.

    try:
        found = {}
        for role in ("05A", "05B", "05C"):
            found[role] = identity(tokens[role], api(state, tokens[role], "getMe"), role)
        if len(set(found.values())) != 3:
            raise StopSmoke("GETME_THREE_DISTINCT_IDENTITIES_REQUIRED")
        state["identity"] = "THREE_APPROVED_BOT_IDS_MATCHED"
        hook = api(state, tokens["05C"], "getWebhookInfo")
        if not isinstance(hook, dict) or hook.get("url"):
            raise StopSmoke("INTERACTIVE_WEBHOOK_PRESENT_OR_UNKNOWN")
        state["webhook"] = "INTERACTIVE_NO_WEBHOOK"
        template = "ZS05 TEST ONLY — NOT A TRADING SIGNAL\nSynthetic connectivity fixture. No market data.\nCase " + case
        send("05A_A", "05A", "sendMessage", {"chat_id": a, "text": template + "\nRoute 05A/A"})
        send("05A_B", "05A", "sendMessage", {"chat_id": b, "text": template + "\nRoute 05A/B"})
        send("05B_C_SUMMARY", "05B", "sendMessage", {"chat_id": c, "text": template + "\nArchive C=A / TEST ONLY"})
        for label, document_label in (("05B_C_QUALIFIED_DOC", "TEST_ONLY_QUALIFIED_FIXTURE"),
                                      ("05B_C_REJECTED_DOC", "TEST_ONLY_REJECTED_FIXTURE")):
            filename, blob, file_sha = docs[document_label]
            send(label, "05B", "sendDocument",
                 {"chat_id": c, "caption": "ZS05 TEST ONLY JSON SHA256=" + file_sha},
                 (filename, blob))
        print("Owner: check 05A A/B messages, 05B A summary + two documents.")
        print("Owner: NOW send btcusdt separately from both A and B to 05C, then press Enter.")
        earliest = int(time.time())
        input("After both messages are sent, press Enter to check up to 6 read-only polls: ")
        matched = {}
        for attempt in range(MAX_UPDATES):
            update_list = api(state, tokens["05C"], "getUpdates",
                              {"offset": 0, "limit": 100, "timeout": 0,
                               "allowed_updates": ["message"]})
            if not isinstance(update_list, list) or len(update_list) > 100:
                raise StopSmoke("UPDATES_UNKNOWN_FORMAT")
            for item in update_list:
                if not isinstance(item, dict) or not isinstance(item.get("message"), dict):
                    continue
                m = item["message"]
                who, chat = m.get("from"), m.get("chat")
                if not isinstance(who, dict) or not isinstance(chat, dict):
                    continue
                user_id, chat_id = who.get("id"), chat.get("id")
                if (type(user_id) is not int or type(chat_id) is not int or
                        chat.get("type") != "private" or user_id != chat_id or
                        str(user_id) not in (a, b) or not isinstance(m.get("text"), str) or
                        m["text"].strip().casefold() != "btcusdt" or
                        type(m.get("date")) is not int or m["date"] < earliest or
                        type(m.get("message_id")) is not int):
                    continue
                label = "A" if str(user_id) == a else "B"
                matched.setdefault(label, m["message_id"])
            if set(matched) == {"A", "B"}:
                break
            if attempt != MAX_UPDATES - 1:
                time.sleep(1)
        state["updates"] = "TWO_AUTHORIZED_FRESH_QUERIES" if len(matched) == 2 else "PARTIAL_OR_NOT_OBSERVED"
        state["authorized_queries"] = sorted(matched)
        if len(matched) != 2:
            raise StopSmoke("BOTH_INTERACTIVE_QUERIES_NOT_OBSERVED")
        for label, recipient in (("A", a), ("B", b)):
            send("05C_REPLY_" + label, "05C", "sendMessage",
                 {"chat_id": recipient,
                  "reply_parameters": {"message_id": matched[label], "allow_sending_without_reply": False},
                  "text": "ZS05 TEST ONLY / NO_APPROVED_LIVE_SNAPSHOT / NOT_REALTIME_VERIFIED\n"
                          "btcusdt receipt confirmed. No indicators, signal or advice. Case " + case})
        confirmed = input("After visually verifying ALL 7 test messages/documents, type exact SEEN ALL 7: ").strip()
        if confirmed != "SEEN ALL 7":
            raise StopSmoke("OWNER_VISUAL_RECEIPT_NOT_CONFIRMED")
        for receipt in state["sends"].values():
            receipt["owner_seen"] = "OWNER_SEEN"
        state["owner_confirmation"] = "ALL_SEVEN_SEEN"
        state["status"] = "THREE_BOT_TEST_ONLY_REAL_CONNECTIVITY_VERIFIED"
    except (StopSmoke, KeyboardInterrupt):
        state["status"] = "PARTIAL_OR_UNKNOWN_STOP_NO_RETRY"
        print("STOP_PARTIAL_OR_UNKNOWN_NO_RETRY")
    finally:
        state["finished_utc"] = utc()
        state["python_version"] = sys.version.split()[0]
        state["exit_code"] = 0 if state["status"] == "THREE_BOT_TEST_ONLY_REAL_CONNECTIVITY_VERIFIED" else 4
        report_sha, log_sha = write_report(folder, state)
        print("TEST_STATUS=" + state["status"])
        print("API_CALLS=" + str(state["api_calls"]))
        print("LOCAL_REPORT_SHA256=" + report_sha)
        print("SANITIZED_LOG_SHA256=" + log_sha)
        print("LOCAL_REPORT_FILE_CREATED=true")
        print("NO_SCANNER_NO_MARKET_NO_SQL_NO_PRODUCTION=true")
    return state["exit_code"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stage05 TEST-ONLY three-bot smoke (default dry-run)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--head-sha")
    parser.add_argument("--tree-sha")
    parser.add_argument("--script-sha256")
    args = parser.parse_args(argv)
    try:
        if not args.execute:
            print(json.dumps(test_plan(), ensure_ascii=False, indent=2))
            print("DRY_RUN_PASS_NO_NETWORK_NO_SECRETS")
            return 0
        return run_execute(args)
    except (StopSmoke, KeyboardInterrupt):
        print("SAFE_ABORT_BEFORE_LIVE_OR_OUTSIDE_SESSION")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())