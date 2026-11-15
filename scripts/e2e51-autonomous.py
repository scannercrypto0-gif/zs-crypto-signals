"""One bounded autonomous continuation of PR54, with secure local configuration."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from zs_smart_gate.e2e51 import Stop, ms
from zs_smart_gate.stage05_contracts import digest
from zs_smart_gate.stage05_telegram_http import BotSecrets

SOURCE = Path(__file__).with_name("e2e51-windows.py")
SPEC = importlib.util.spec_from_file_location("e2e51_windows", SOURCE)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
ROOT = Path("D:/ZS-SMART-GATE/e2e-51-6761924797")
TTL_MS = 900000
WINDOW_S = 45


def credentials():
    cfg = BotSecrets.from_environ()
    tokens = {"05A": cfg.signals_token, "05B": cfg.analytics_token, "05C": cfg.interactive_token}
    smoke = runner.smoke_transport()
    smoke.check_routes(cfg.signals_chat_a, cfg.signals_chat_b, cfg.analytics_chat,
                       (cfg.signals_chat_a, cfg.signals_chat_b), tokens)
    if len({token.split(":", 1)[0] for token in tokens.values()}) != 3:
        raise Stop("LOCAL_BOT_IDENTITIES_NOT_DISTINCT")
    return cfg, tokens, smoke


def session(root, head, tree, *, check=credentials, market=runner.start_market):
    runner.guard(root)
    if any((root / name).exists() for name in ("session.claim.json", "market.claim.json", "telegram.claim.json")):
        raise Stop("FOLLOWUP_ALREADY_CLAIMED")
    try:
        cfg, tokens, smoke = check()
    except Exception:
        raise Stop("BLOCKED_MISSING_LOCAL_CONFIGURATION") from None
    # Foreground only. Begin shortly after the next closed 5m boundary.
    phase = time.time() % 300
    wait = 4 - phase if phase < 4 else (304 - phase if phase > WINDOW_S else 0)
    until = time.monotonic() + wait
    while time.monotonic() < until:
        runner.guard(root)
        time.sleep(min(0.5, max(0, until - time.monotonic())))
    runner.guard(root)
    runner.save(root / "session.claim.json", {"head": head, "tree": tree, "utc_ms": ms()})
    market(root, head, tree)
    report = json.loads((root / "market-report.json").read_bytes())
    raw = (root / "stage04-readback.json").read_bytes()
    if (report.get("head") != head or report.get("tree") != tree
            or report.get("status") != "MARKET_TO_STAGE04_READBACK_PASS"
            or report.get("evidence_sha256") != digest(raw)):
        raise Stop("MARKET_READBACK_NOT_PINNED")
    event = json.loads(raw)["stage05_event"]
    if event.get("source_scope") != "APPROVED_REAL_SOURCE":
        raise Stop("REAL_MARKET_RECEIPT_REQUIRED")
    runner.save(root / "telegram.claim.json", {"head": head, "candidate_id": event["candidate_id"]})
    state = {"head": head, "candidate_id": event["candidate_id"], "api_calls": 0,
             "outbound_attempts": 0, "readback_sha256": digest(raw),
             "05C": "05C_LIVE_INBOUND_NOT_VERIFIED", "owner_visual": "NOT_ATTESTED",
             "status": "PARTIAL_OR_UNKNOWN_STOP_NO_RETRY"}
    market_start = runner.report_path_time(root)
    def api(role, method, data=None, document=None):
        runner.guard(root)
        if not 0 <= ms() - market_start < TTL_MS:
            raise Stop("MARKET_SESSION_EXPIRED")
        if state["api_calls"] >= 7 or method not in ("getMe", "sendMessage", "sendDocument"):
            raise Stop("TELEGRAM_BUDGET_OR_METHOD_STOP")
        if method.startswith("send"):
            if role not in ("05A", "05B") or state["outbound_attempts"] >= 4:
                raise Stop("TELEGRAM_ROUTE_OR_SEND_BUDGET_STOP")
            state["outbound_attempts"] += 1
        runner.save(root / f"api-{state['api_calls']+1:02}.json",
                    {"role": role, "method": method, "utc_ms": ms()})
        return smoke.api(state, tokens[role], method, data, document)
    def note(label, receipt):
        runner.save(root / (label + "-" + receipt["status"] + ".json"), receipt)
    try:
        identities = {smoke.identity(tokens[role], api(role, "getMe"), role) for role in tokens}
        if len(identities) != 3:
            raise Stop("BOT_IDENTITIES_NOT_DISTINCT")
        state["bot_identities"] = "THREE_EXPECTED_ROLES_VERIFIED"
        runner.deliver(event, cfg, api, note, None, interactive=False)
        state["status"] = "05A_05B_API_ACCEPTED_05C_INBOUND_NOT_VERIFIED"
    finally:
        runner.save(root / "telegram-report.json", state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    tree = runner.pins(args.head)
    ROOT.mkdir(exist_ok=True)
    pin = {"head": args.head, "tree": tree, "offline": "PASS"}
    preflight = ROOT / "preflight.json"
    if preflight.exists() and json.loads(preflight.read_bytes()) != pin:
        raise Stop("FOLLOWUP_PREFLIGHT_PIN_MISMATCH")
    test_env = {k: v for k, v in os.environ.items() if not k.upper().startswith("ZS_")}
    for suite in ("test_e2e51.py", "test_e2e51_autonomous.py"):
        subprocess.run([sys.executable, "-B", "-m", "unittest", "discover",
                        "-s", "tests", "-p", suite], cwd=runner.REPO, check=True, env=test_env)
    if not preflight.exists():
        runner.save(preflight, pin)
    session(ROOT, args.head, tree)


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print(str(exc) if type(exc) is Stop else "E2E_STOP_NO_RETRY_" + type(exc).__name__, file=sys.stderr)
        sys.exit(2)
