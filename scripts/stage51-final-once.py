"""Owner Windows foreground runner for the independently approved 003 session."""
import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys
import time

from zs_smart_gate.e2e51 import Stop, ms, public_get
from zs_smart_gate.stage05_bounded_interactive import bounded_interactive
from zs_smart_gate.stage05_contracts import digest, parse_utc
from zs_smart_gate.stage05_custody import LocalOutbox
from zs_smart_gate.stage05_telegram_http import BotSecrets, OwnerPermit, RuntimeFlags
from zs_smart_gate.stage51_live_chain import run_chain

ROOT = Path("D:/ZS-SMART-GATE/stage51-final-003")
SESSION = "ZS-00-05-ONE-ORDER-FINAL-CLOSURE-20261110-003"
SPEC = importlib.util.spec_from_file_location("shared", Path(__file__).with_name("e2e51-windows.py"))
shared = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shared)


def utc():
    return datetime.now(timezone.utc)


def approval(path, head, tree, contract):
    data = json.loads(path.read_bytes())
    expected = {"head": head, "tree": tree, "contract_sha256": contract,
                "session": SESSION, "pm_status": "EXACT_SHA_GO", "owner_status": "SESSION_APPROVED"}
    if any(data.get(k) != v for k, v in expected.items()):
        raise Stop("EXACT_SHA_PM_AND_OWNER_APPROVAL_REQUIRED")
    refs = [data.get(k, "") for k in ("pm_ref", "owner_ref")]
    pattern = r"https://github\.com/scannercrypto0-gif/zs-crypto-signals/(?:issues|pull)/\d+#issuecomment-\d+"
    if len(set(refs)) != 2 or not all(re.fullmatch(pattern, ref) for ref in refs):
        raise Stop("DISTINCT_APPROVAL_REFERENCES_REQUIRED")
    if parse_utc(data["expires_at"]) <= utc():
        raise Stop("APPROVAL_EXPIRED")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", required=True)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--both-accounts-ready-no-other-consumer", action="store_true")
    args = parser.parse_args()
    tree = shared.pins(args.head)
    contract = digest((shared.REPO / "research/stage51/closure/LIVE_SESSION_CONTRACT.md").read_bytes().replace(b"\r\n", b"\n"))
    cfg = BotSecrets.from_environ()
    smoke = shared.smoke_transport()
    tokens = {"05A": cfg.signals_token, "05B": cfg.analytics_token, "05C": cfg.interactive_token}
    smoke.check_routes(cfg.signals_chat_a, cfg.signals_chat_b, cfg.analytics_chat,
                       (cfg.signals_chat_a, cfg.signals_chat_b), tokens)
    if len({t.split(":")[0] for t in tokens.values()}) != 3:
        raise Stop("BOT_IDENTITIES_NOT_DISTINCT")
    shared.guard(ROOT)
    if not args.approval:
        print(f"OFFLINE_PREFLIGHT_PASS HEAD={args.head} TREE={tree} CONTRACT_SHA256={contract} NETWORK=0")
        return 0
    if not args.both_accounts_ready_no_other_consumer:
        raise Stop("WAITING_FOR_OWNER_05C_HUMAN_ACTION")
    data = approval(args.approval, args.head, tree, contract)
    # Approval file is an operator handoff of independently reviewed GitHub
    # decisions, not a mechanism for self-approving the run.
    if not 4 <= time.time() % 300 <= 50:
        raise Stop("WAIT_FOR_NEXT_5M_CLOSE_WITHOUT_CLAIM")
    shared.save(ROOT / "session.claim.json", {"session": SESSION, "head": args.head})
    deadline = time.monotonic() + 240
    receipts, calls = [], []
    state = {"api_calls": 0}
    report = {"status": "STOPPED_UNKNOWN"}
    code = 2

    def guard():
        shared.guard(ROOT)
        if time.monotonic() >= deadline or utc() >= parse_utc(data["expires_at"]):
            raise Stop("SESSION_TIME_LIMIT")

    def attempt(service, method):
        guard()
        limit = 6 if service == "BINANCE" else 20
        if sum((c["service"] == "BINANCE") == (service == "BINANCE") for c in calls) >= limit:
            raise Stop("API_BUDGET_STOP")
        if method.startswith("send") and sum(c["method"].startswith("send") for c in calls) >= 3:
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
        expires = min(now+timedelta(minutes=3), parse_utc(data["expires_at"]))
        permit = OwnerPermit("OWNER-APPROVED-FINAL-003", args.head,
                             expires.isoformat().replace("+00:00", "Z"),
                             frozenset(("INTERACTIVE_POLL", "INTERACTIVE_REPLY")), True, True)
        return bounded_interactive(config=cfg, transport=None, store=LocalOutbox(ROOT/"outbox.sqlite"),
                                   upstream=upstream, source_ref=ref, started_at=int(now.timestamp()),
                                   session_id=SESSION, head_sha=args.head, permit=permit,
                                   flags=RuntimeFlags(send=True, interactive_poll=True, interactive_reply=True),
                                   ready=lambda: print("READY â€” SEND BTCUSDT NOW", flush=True),
                                   guard=guard, on_attempt=lambda method: attempt("05C", method))

    try:
        report = run_chain(ROOT, session=SESSION, get=get, decision_clock=ms,
                           archive=archive, interactive=interactive, receipts=receipts)
        if isinstance(report["stage05c"], dict) and report["stage05c"]["status"] == "TWO_API_ACCEPTED_REPLIES":
            code = 0
        report["status"] = "BOUNDED_REJECTED_SOURCE_CHAIN_PASS" if code == 0 else "PARTIAL_STOP"
    finally:
        report.update(head=args.head, tree=tree, contract_sha256=contract, attempts=calls,
                      exit_code=code, owner_visual="NOT_ATTESTED", pm_ref=data["pm_ref"], owner_ref=data["owner_ref"])
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
