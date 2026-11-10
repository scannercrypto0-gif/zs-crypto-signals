"""Windows-only one-shot execution. No network in preflight/status/stop."""
import argparse
import getpass
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import warnings

from zs_smart_gate.e2e51 import SYMBOL, Stop, analyze, capture, ms, persist
from zs_smart_gate.stage05_contracts import canonical, digest, make_document
from zs_smart_gate.stage05_interactive import InteractiveService
from zs_smart_gate.stage05_telegram_http import BotSecrets

REPO = Path(__file__).resolve().parents[1]
ROOT = Path("D:/ZS-SMART-GATE/e2e-51-session")
ORDER = "ZS-00-05-LIVE-E2E-INTEGRATION-20261109-001"


def save(path, obj):
    with path.open("xb") as f:
        f.write(canonical(obj))
        f.flush()
        os.fsync(f.fileno())


def pins(head):
    if sys.platform != "win32" or len(head) != 40:
        raise Stop("WINDOWS_EXACT_SHA_REQUIRED")
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()
    if git("rev-parse", "HEAD") != head or git("status", "--porcelain", "--untracked-files=all"):
        raise Stop("CHECKOUT_NOT_CLEAN_OR_SHA_MISMATCH")
    return git("rev-parse", "HEAD^{tree}")


def guard(root):
    if (root / "stop.json").exists():
        raise Stop("KILL_SWITCH_SET")


def start_market(root, head, tree):
    preflight = json.loads((root / "preflight.json").read_bytes())
    if preflight != {"head": head, "tree": tree, "offline": "PASS"}:
        raise Stop("PREFLIGHT_PIN_MISMATCH")
    guard(root)
    save(root / "market.claim.json", {"order": ORDER, "head": head, "utc_ms": ms()})
    receipts = []
    report = {"head": head, "tree": tree, "market_attempts": 0, "websocket_connections": 0,
              "telegram_attempts": 0, "status": "BLOCKED_OR_FAILED"}
    from zs_smart_gate.e2e51 import public_get
    def get(path, params):
        guard(root)
        report["market_attempts"] += 1
        return public_get(path, params)
    try:
        capture(receipts, get=get)
        event = analyze(receipts, ms(), synthetic=False)
        stored, outcome = persist(root, receipts, event)
        save(root / "stage04-readback.json", stored)
        report.update(status="MARKET_TO_STAGE04_READBACK_PASS", readback=outcome,
                      evidence_sha256=digest(canonical(stored)))
    finally:
        save(root / "market-receipts.json", receipts)
        save(root / "market-report.json", report)


def smoke_transport():
    file = REPO / "research/stage05/zs05_three_bot_smoke_windows.py"
    spec = importlib.util.spec_from_file_location("zs05_pinned_transport", file)
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    return smoke


def deliver(event, cfg, api, note, confirm, clock=time.time, *, interactive=True):
    """One exact test plan. No qualified event or production coordinator."""
    if event["signal_id"] is not None or event["qualification_status"] != "REJECTED":
        raise Stop("NO_SIGNAL_SEND_PATH")
    a, b = cfg.signals_chat_a, cfg.signals_chat_b
    case = event["candidate_id"][-12:]
    prefix = "ZS E2E TEST ONLY / NOT A TRADING SIGNAL / " + case
    archive = make_document(event)
    def send(label, role, method, chat, fields, attachment=None):
        note(label, {"status": "UNKNOWN_DELIVERY", "attempted_ms": ms()})
        result = api(role, method, {"chat_id": chat, **fields}, attachment)
        returned_chat = result.get("chat") if isinstance(result, dict) else None
        if (not isinstance(returned_chat, dict) or returned_chat.get("type") != "private"
                or str(returned_chat.get("id")) != chat
                or type(result.get("message_id")) is not int or result["message_id"] <= 0
                or type(result.get("date")) is not int or result["date"] <= 0):
            raise Stop("DELIVERY_RECEIPT_UNKNOWN")
        note(label, {"status": "API_ACCEPTED", "telegram_server_utc_ms": result["date"] * 1000})
    for label, chat in (("A", a), ("B", b)):
        send("05A_" + label, "05A", "sendMessage", chat,
             {"text": prefix + "\nSYNTHETIC TEST ONLY / NOT A TRADING SIGNAL. No qualifying signal."})
    send("05B_C_SUMMARY", "05B", "sendMessage", a,
         {"text": prefix + "\nBTCUSDT / real bounded Spot snapshot / research-only rejection."})
    send("05B_C_JSON", "05B", "sendDocument", a,
         {"caption": prefix + "\n" + archive["caption"]},
         (archive["manifest"]["file_name"], archive["document"]))
    if not interactive:
        return
    earliest = int(clock())
    query = SYMBOL.lower() + " " + case
    confirm("From A and B, send exactly '" + query + "' privately to 05C, then press Enter. ")
    if clock() - earliest > 180:
        raise Stop("QUERY_WINDOW_EXPIRED")
    updates = api("05C", "getUpdates", {"offset": 0, "limit": 100, "timeout": 0,
                                        "allowed_updates": ["message"]}, None)
    if not isinstance(updates, list) or len(updates) > 100:
        raise Stop("UPDATES_INVALID")
    matched = {}
    for item in updates:
        m = item.get("message") if isinstance(item, dict) else None
        if not isinstance(m, dict):
            continue
        chat, user = m.get("chat"), m.get("from")
        if not isinstance(chat, dict) or not isinstance(user, dict):
            continue
        identity = chat.get("id")
        if (chat.get("type") == "private" and type(identity) is int and user.get("id") == identity
                and str(identity) in (a, b) and m.get("text") == query
                and type(m.get("date")) is int and earliest <= m["date"] <= clock() + 2
                and type(m.get("message_id")) is int and m["message_id"] > 0):
            matched.setdefault(str(identity), m["message_id"])
    if set(matched) != {a, b}:
        raise Stop("TWO_FRESH_PRIVATE_QUERIES_NOT_OBSERVED")
    snapshot = {"symbol": SYMBOL, "as_of": event["timestamps"]["decision_at"],
                "indicators": event["indicators"], "source_scope": event["source_scope"],
                "decision": "RESEARCH_ONLY_REJECTED", "score": None,
                "reason_codes": event["reject_reason_codes"]}
    service = InteractiveService(config=cfg, supported_symbols=[SYMBOL],
                                 lookup=lambda _: snapshot)
    for label, chat in (("A", a), ("B", b)):
        service.accept(text=SYMBOL, user_id=chat, chat_id=chat, message_id=matched[chat])
        analysis = service.process_one()
        if analysis["status"] != "READ_ONLY_ANALYSIS":
            raise Stop("INTERACTIVE_SNAPSHOT_UNAVAILABLE")
        reply = prefix + "\n" + service.format_reply(analysis)
        send("05C_" + label, "05C", "sendMessage", chat,
             {"text": reply, "reply_parameters": {"message_id": matched[chat],
                                                   "allow_sending_without_reply": False}})


def start_telegram(root, head, tree):
    guard(root)
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise Stop("OWNER_INTERACTIVE_WINDOWS_CONSOLE_REQUIRED")
    report = json.loads((root / "market-report.json").read_bytes())
    raw = (root / "stage04-readback.json").read_bytes()
    if (report.get("head") != head or report.get("tree") != tree
            or report.get("status") != "MARKET_TO_STAGE04_READBACK_PASS"
            or report.get("evidence_sha256") != digest(raw)):
        raise Stop("MARKET_READBACK_NOT_PINNED")
    event = json.loads(raw)["stage05_event"]
    if ms() - report_path_time(root) > 900000:
        raise Stop("MARKET_SESSION_EXPIRED")
    ack = "AUTHORIZE E2E TEST ONLY " + head
    if input("Owner: type " + ack + " to permit this one Telegram session: ") != ack:
        raise Stop("OWNER_SEND_CONFIRMATION_MISSING")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        tokens = {role: getpass.getpass(role + " bot token (hidden): ")
                  for role in ("05A", "05B", "05C")}
        a = getpass.getpass("Private account A (hidden): ")
        b = getpass.getpass("Private account B (hidden): ")
    cfg = BotSecrets(tokens["05A"], a, b, tokens["05C"], frozenset((a,b)),
                     frozenset((a,b)), tokens["05B"], a)
    cfg.validate()
    if ms() - report_path_time(root) > 900000:
        raise Stop("MARKET_SESSION_EXPIRED")
    save(root / "telegram.claim.json", {"order": ORDER, "head": head, "utc_ms": ms()})
    state = {"api_calls": 0, "sends": 0, "owner_visual": "NOT_VERIFIED",
             "status": "PARTIAL_OR_UNKNOWN_STOP_NO_RETRY"}
    smoke = smoke_transport()
    deadline = time.monotonic() + 240
    def api(role, method, payload=None, document=None):
        guard(root)
        if (time.monotonic() > deadline or state["api_calls"] >= 11
                or state["sends"] >= 6):
            raise Stop("TELEGRAM_BUDGET_STOP")
        if method.startswith("send"):
            state["sends"] += 1
        save(root / f"api-{state['api_calls']+1:02}.json",
             {"role": role, "method": method, "utc_ms": ms()})
        return smoke.api(state, tokens[role], method, payload, document)
    def note(label, receipt):
        save(root / (label + "-" + receipt["status"] + ".json"), receipt)
    try:
        for role in tokens:
            smoke.identity(tokens[role], api(role, "getMe"), role)
        hook = api("05C", "getWebhookInfo")
        if not isinstance(hook, dict) or hook.get("url") != "":
            raise Stop("INTERACTIVE_WEBHOOK_PRESENT_OR_UNKNOWN")
        deliver(event, cfg, api, note, input)
        if input("Owner: after visually verifying all six outputs, type SEEN E2E 6: ") != "SEEN E2E 6":
            raise Stop("OWNER_VISUAL_NOT_VERIFIED")
        state.update(status="THREE_BOT_E2E_TEST_ONLY_VISUALLY_VERIFIED", owner_visual="SEEN_E2E_6")
    finally:
        save(root / "telegram-report.json", state)


def report_path_time(root):
    return json.loads((root / "market.claim.json").read_bytes())["utc_ms"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preflight", "market", "telegram", "status", "stop"))
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    tree = pins(args.head)
    ROOT.mkdir(exist_ok=True)
    if args.mode == "preflight":
        subprocess.run([sys.executable, "-B", "-m", "unittest", "discover",
                        "-s", "tests", "-p", "test_e2e51.py"], cwd=REPO, check=True)
        save(ROOT / "preflight.json", {"head": args.head, "tree": tree, "offline": "PASS"})
    elif args.mode == "market":
        start_market(ROOT, args.head, tree)
    elif args.mode == "telegram":
        start_telegram(ROOT, args.head, tree)
    elif args.mode == "stop":
        save(ROOT / "stop.json", {"utc_ms": ms()})
    else:
        print(json.dumps({p.stem: True for p in ROOT.glob("*.claim.json")}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print("E2E_STOP_NO_RETRY " + (str(error) if type(error) is Stop else type(error).__name__),
              file=sys.stderr)
        sys.exit(2)
