"""Windows-only foreground 05C test, with no market or 05A/05B calls."""
import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import msvcrt
from pathlib import Path
import sys

from zs_smart_gate.e2e51 import persist, Stop
from zs_smart_gate.pre05_offline_chain import LocalChainJournal
from zs_smart_gate.stage05_bounded_interactive import bounded_interactive
from zs_smart_gate.stage05_contracts import canonical, digest
from zs_smart_gate.stage05_custody import LocalOutbox, VerifiedUpstream
from zs_smart_gate.stage05_telegram_http import BotSecrets, OwnerPermit, RuntimeFlags

PIN = "a580da9fe08cf44e36d775cfc239704a50014b5d4edc86412f33bf4dcee5da11"
SESSION = "ISSUE51-6762796319-05C-ONCE"
ROOT = Path("D:/ZS-SMART-GATE/stage51-05c-once")
SPEC = importlib.util.spec_from_file_location("pins", Path(__file__).with_name("e2e51-windows.py"))
shared = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shared)


def utc():
    return datetime.now(timezone.utc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--both-accounts-ready-no-other-consumer", action="store_true")
    args = parser.parse_args()
    tree = shared.pins(args.head)
    cfg = BotSecrets.from_environ()
    if len({t.split(":")[0] for t in (cfg.signals_token, cfg.interactive_token, cfg.analytics_token)}) != 3:
        raise Stop("LOCAL_BOT_IDENTITIES_NOT_DISTINCT")
    shared.guard(ROOT)
    store = LocalOutbox(ROOT / "outbox.sqlite")
    key = "interactive-session/" + digest(canonical(SESSION))
    if store.read(key) is not None:
        raise Stop("INTERACTIVE_SESSION_ALREADY_CONSUMED")
    evidence = shared.REPO / "research/stage51/live-followup-6761924797"
    stored_bytes = (evidence / "stage04-readback.json").read_bytes()
    if digest(stored_bytes) != PIN:
        raise Stop("HISTORICAL_SNAPSHOT_PIN_MISMATCH")
    row = json.loads(stored_bytes)
    source = json.loads((evidence / "market-receipts.json").read_bytes())
    restored, _ = persist(ROOT, source, row["stage05_event"])
    if digest(canonical(restored)) != PIN:
        raise Stop("HISTORICAL_SNAPSHOT_RESTORE_MISMATCH")
    journal = LocalChainJournal(ROOT / "journal.sqlite")
    identity, _ = journal.append_readback(restored)
    upstream = VerifiedUpstream(journal, {identity: PIN})
    upstream.read(identity, PIN)
    if not args.live:
        print("PREFLIGHT_PASS DPAPI=8/8 ROUTES=PASS HISTORICAL_SNAPSHOT=PASS API_CALLS=0 CLAIM=NONE")
        shared.save(ROOT / ("preflight-" + args.head + ".json"), {"head": args.head, "tree": tree}) if not (
            ROOT / ("preflight-" + args.head + ".json")).exists() else None
        return 0
    if not args.both_accounts_ready_no_other_consumer:
        raise Stop("WAITING_FOR_OWNER_05C_HUMAN_ACTION")
    if not (ROOT / ("preflight-" + args.head + ".json")).exists():
        raise Stop("EXACT_SHA_PREFLIGHT_REQUIRED")
    lock = ROOT / "poll.lock"
    with lock.open("a+b") as f:
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise Stop("LOCAL_POLL_OWNER_ALREADY_ACTIVE") from None
        try:
            return run_live(args.head, tree, cfg, store, upstream, identity)
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def run_live(head, tree, cfg, store, upstream, identity):
    start = utc()
    stamp = start.strftime("%Y%m%dT%H%M%S%fZ")
    folder = ROOT / stamp
    folder.mkdir()
    calls = []
    report = {"status": "STOPPED_UNKNOWN", "replies": {}}
    def attempt(method):
        shared.guard(ROOT)
        if (len(calls) >= 12 or (method == "sendMessage" and calls.count(method) >= 2)
                or method not in ("getMe", "getWebhookInfo", "getUpdates", "sendMessage")):
            raise Stop("05C_API_BUDGET_STOP")
        shared.save(folder / f"attempt-{len(calls)+1:02}.json",
                    {"method": method, "utc": utc().isoformat()})
        calls.append(method)
    actions = frozenset(("INTERACTIVE_POLL", "INTERACTIVE_REPLY"))
    permit = OwnerPermit("OWNER-APPROVED-ISSUE51-6762796319-PR55-6763240448", head,
                         (start + timedelta(minutes=4)).isoformat().replace("+00:00", "Z"),
                         actions, True, True)
    code = 2
    try:
        report = bounded_interactive(config=cfg, transport=None, store=store, upstream=upstream,
                                     source_ref=(identity, PIN), started_at=int(start.timestamp()),
                                     session_id=SESSION, head_sha=head, permit=permit,
                                     flags=RuntimeFlags(send=True, interactive_poll=True, interactive_reply=True),
                                     ready=lambda: print("READY — SEND BTCUSDT NOW", flush=True),
                                     guard=lambda: shared.guard(ROOT), on_attempt=attempt)
        if report["status"] == "TWO_API_ACCEPTED_REPLIES":
            code = 0
    finally:
        report.update(head=head, tree=tree, utc_started=start.isoformat(), utc_finished=utc().isoformat(),
                      market_calls=0, api_attempts=len(calls), send_attempts=calls.count("sendMessage"),
                      owner_visual="NOT_ATTESTED", exit_code=code, historical_snapshot_sha256=PIN)
        shared.save(folder / "report.json", report)
        print(json.dumps(report, sort_keys=True), flush=True)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt) as error:
        print(str(error) if type(error) is Stop else "05C_STOP_" + type(error).__name__, file=sys.stderr)
        sys.exit(2)
