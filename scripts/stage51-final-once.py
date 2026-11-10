"""Owner Windows foreground runner for the independently approved 003 session."""
import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import time

from zs_smart_gate.e2e51 import Stop, ms, public_get
from zs_smart_gate.stage05_bounded_interactive import bounded_interactive
from zs_smart_gate.stage05_contracts import digest
from zs_smart_gate.stage05_custody import LocalOutbox
from zs_smart_gate.stage05_telegram_http import BotSecrets, OwnerPermit, RuntimeFlags
from zs_smart_gate.stage51_live_chain import run_chain

PRIOR_ROOT = Path("D:/ZS-SMART-GATE/stage51-final-003")
ROOT = Path("D:/ZS-SMART-GATE/stage51-final-003-a")
SESSION = "ZS-00-05-ONE-ORDER-FINAL-CLOSURE-20261110-003"
SPEC = importlib.util.spec_from_file_location("shared", Path(__file__).with_name("e2e51-windows.py"))
shared = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shared)


def utc():
    return datetime.now(timezone.utc)


OWNER_AUTHORITY = "https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6767851362"
CONTRACT_SHA256 = "99b8428f61d77a922bd5be6cc7272b0bf701ae7fec1d8260121fe1b90ef53456"

def check_contract(raw):
    if digest(raw.replace(b"\r\n", b"\n")) != CONTRACT_SHA256:
        raise Stop("OWNER_SCOPE_CONTRACT_SHA_MISMATCH")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--account-a-ready-no-other-consumer", action="store_true")
    args = parser.parse_args()
    tree = shared.pins(args.head)
    check_contract((shared.REPO / "research/stage51/closure/LIVE_SESSION_CONTRACT.md").read_bytes())
    contract = CONTRACT_SHA256
    cfg = BotSecrets.from_environ()
    smoke = shared.smoke_transport()
    tokens = {"05A": cfg.signals_token, "05B": cfg.analytics_token, "05C": cfg.interactive_token}
    smoke.check_routes(cfg.signals_chat_a, cfg.signals_chat_b, cfg.analytics_chat,
                       (cfg.signals_chat_a, cfg.signals_chat_b), tokens)
    if len({t.split(":")[0] for t in tokens.values()}) != 3:
        raise Stop("BOT_IDENTITIES_NOT_DISTINCT")
    shared.guard(ROOT)
    if any((path / "session.claim.json").exists() for path in (ROOT, PRIOR_ROOT)):
        raise Stop("SESSION_ALREADY_CLAIMED")
    if not args.live:
        print(f"OFFLINE_PREFLIGHT_PASS HEAD={args.head} TREE={tree} CONTRACT_SHA256={contract} NETWORK=0")
        return 0
    if not args.account_a_ready_no_other_consumer:
        raise Stop("WAITING_FOR_OWNER_05C_HUMAN_ACTION")
    phase = time.time() % 300
    wait = 4.2 - phase if phase < 4 else (304.2 - phase if phase > 50 else 0)
    if wait:
        print("WAITING_FOR_CLOSED_5M_BOUNDARY", flush=True)
    wait_until = time.monotonic() + wait
    while time.monotonic() < wait_until:
        shared.guard(ROOT)
        time.sleep(min(1, max(0, wait_until - time.monotonic())))
    shared.guard(ROOT)
    if not 4 <= time.time() % 300 <= 50:
        raise Stop("CLOSED_5M_START_WINDOW_MISSED")
    shared.save(ROOT / "session.claim.json", {"session": SESSION, "head": args.head})
    deadline = time.monotonic() + 240
    receipts, calls = [], []
    state = {"api_calls": 0}
    report = {"status": "STOPPED_UNKNOWN"}
    code = 2

    def guard():
        shared.guard(ROOT)
        if time.monotonic() >= deadline:
            raise Stop("SESSION_TIME_LIMIT")

    def attempt(service, method):
        guard()
        limit = 6 if service == "BINANCE" else 20
        if sum((c["service"] == "BINANCE") == (service == "BINANCE") for c in calls) >= limit:
            raise Stop("API_BUDGET_STOP")
        if method.startswith("send") and sum(c["method"].startswith("send") for c in calls) >= 2:
            raise Stop("SEND_BUDGET_STOP")
        row = {"service": service, "method": method, "utc": utc().isoformat()}
        shared.save(ROOT / f"attempt-{len(calls)+1:02}.json", row)
        calls.append(row)

    def get(path, params):
        attempt("BINANCE", path)
        return public_get(path, params)

    def archive(manifest, document):
        token = tokens["05B"]
        attempt("05B", "getMe")
        smoke.identity(token, smoke.api(state, token, "getMe"), "05B")
        caption = ("ZS 05B TEST ONLY / NOT A TRADING SIGNAL\n" + document["caption"])
        shared.save(ROOT / "archive-intent.json", {"archive_sha256": manifest["archive_sha256"]})
        attempt("05B", "sendDocument")
        try:
            result = smoke.api(state, token, "sendDocument",
                               {"chat_id": cfg.analytics_chat, "caption": caption},
                               (document["manifest"]["file_name"], document["document"]))
        except smoke.StopSmoke:
            return "UNKNOWN_DELIVERY"
        chat = result.get("chat") if isinstance(result, dict) else None
        if (not isinstance(chat, dict) or chat.get("type") != "private"
                or str(chat.get("id")) != cfg.analytics_chat
                or type(result.get("message_id")) is not int or result["message_id"] <= 0
                or type(result.get("date")) is not int or result["date"] <= 0):
            return "UNKNOWN_DELIVERY"
        shared.save(ROOT / "archive-receipt.json",
                    {"archive_sha256": manifest["archive_sha256"], "status": "API_ACCEPTED",
                     "telegram_server_utc_s": result["date"]})
        return "API_ACCEPTED"

    def interactive(upstream, ref):
        now = utc()
        expires = now+timedelta(minutes=3)
        permit = OwnerPermit("OWNER-APPROVED-FINAL-003", args.head,
                             expires.isoformat().replace("+00:00", "Z"),
                             frozenset(("INTERACTIVE_POLL", "INTERACTIVE_REPLY")), True, True)
        return bounded_interactive(config=cfg, transport=None, store=LocalOutbox(ROOT/"outbox.sqlite"),
                                   upstream=upstream, source_ref=ref, started_at=int(now.timestamp()),
                                   session_id=SESSION, head_sha=args.head, permit=permit,
                                   flags=RuntimeFlags(send=True, interactive_poll=True, interactive_reply=True),
                                   ready=lambda: print("READY - SEND BTCUSDT FROM A NOW", flush=True),
                                   account_a_only=True,
                                   guard=guard, on_attempt=lambda method: attempt("05C", method))

    try:
        report = run_chain(ROOT, session=SESSION, get=get, decision_clock=ms,
                           archive=archive, interactive=interactive, receipts=receipts)
        if isinstance(report["stage05c"], dict) and report["stage05c"]["status"] == "ACCOUNT_A_API_ACCEPTED_REPLY":
            code = 0
        report["status"] = "BOUNDED_REJECTED_SOURCE_CHAIN_PASS" if code == 0 else "PARTIAL_STOP"
    finally:
        report.update(head=args.head, tree=tree, contract_sha256=contract, attempts=calls,
                      exit_code=code, owner_visual="NOT_ATTESTED", owner_authority=OWNER_AUTHORITY)
        shared.save(ROOT / "market-receipts.json", receipts)
        shared.save(ROOT / "final-manifest.json", report)
        print(json.dumps(report, sort_keys=True), flush=True)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt) as error:
        print(str(error) if type(error) is Stop else "FINAL003_STOP_" + type(error).__name__, file=sys.stderr)
        sys.exit(2)
