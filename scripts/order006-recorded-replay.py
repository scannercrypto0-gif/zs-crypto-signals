"""ORDER006 pinned historical multi-asset replay. No network or delivery."""
import argparse
import json
from pathlib import Path
import runpy

from zs_smart_gate.marketwide_cursor import ScanLedger
from zs_smart_gate.marketwide_research import inventory, packet_from_receipts, evaluate
from zs_smart_gate.stage05_contracts import canonical, digest


def replay(capture_path, pin, output):
    raw = capture_path.read_bytes()
    if digest(raw) != pin:
        raise ValueError("CAPTURE_SHA_MISMATCH")
    baseline = runpy.run_path(str(Path(__file__).with_name("stage01-stage03-multi-spot.py")))
    validated = baseline["evaluate"](raw)
    capture = json.loads(raw)
    snap = inventory(capture["receipts"][:3], capture["decision_at"], scope="RECORDED_BOUNDED_INVENTORY")
    output.mkdir()
    ledger = ScanLedger(output / "scan.sqlite")
    scan = ledger.register(snap, capture["anchor_ms"])
    # Historical multi-asset capture only includes six 5m bars per selected pair.
    # Record the real insufficiency rather than invent the missing 20-bar history.
    symbols = sorted(row["identity"]["symbol"] for row in validated["rows"])
    for offset, symbol in enumerate(symbols):
        item = next(r for r in snap["rows"] if r["symbol"] == symbol)
        selected = capture["receipts"][3 + offset*4: 7 + offset*4]
        packet = packet_from_receipts(item, selected, boundary_ms=capture["anchor_ms"],
                                      decision_at=capture["decision_at"], scope="RECORDED_PUBLIC_SPOT",
                                      clock_status="RECORDED_CONDITIONAL_BRACKET")
        results = evaluate(packet)
        if any(r["status"] != "DATA_INVALID" for r in results):
            raise ValueError("SIX_BARS_CANNOT_SATISFY_22_BAR_DETECTOR")
        capture.setdefault("directional_replay", []).append(dict(
            symbol=symbol, detector_history="INSUFFICIENT_22_BAR_HISTORY",
            direction_states={r["direction"]: r["status"] for r in results},
            direction_results=results, r0_r1_r2_status="POLICY_HOLD", signal_id=None,
        ))
    report = dict(capture_sha256=pin, snapshot_sha256=snap["snapshot_sha256"],
                  baseline_replay="PASS", inventory_count=len(snap["rows"]),
                  source_validated_symbols=symbols, attempted_directional_evaluations=2*len(symbols), valid_directional_evaluations=0,
                  unscanned_symbols=sorted(set(r["symbol"] for r in snap["rows"]) - set(symbols)),
                  rows=capture["directional_replay"], coverage="MARKET_COVERAGE_PARTIAL",
                  qualification="QV1_REAL_POLICY_BLOCKED", signal_id=None,
                  live_e2e="LIVE_E2E_NOT_PROVEN", baseline_input_sha256=digest(canonical(validated)))
    (output/"result.json").write_bytes(canonical(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("pin")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.resolve().drive.upper() != "D:":
        parser.error("output must be on D:")
    print(canonical(replay(args.capture, args.pin, args.output)).decode())
