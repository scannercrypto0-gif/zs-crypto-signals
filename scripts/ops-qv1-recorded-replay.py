"""Recompute a recorded QV1 observation and verify local custody without network."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import runpy

from zs_smart_gate.stage03_research_handoff import make_recorded_spot_handoff
from zs_smart_gate.stage04_windows_operational import WindowsOperationalJournal
from zs_smart_gate.stage05_contracts import canonical, digest


def replay(capture, pin, output):
    raw = capture.read_bytes()
    handoff = make_recorded_spot_handoff(raw, pin)
    record = json.loads(raw)
    source = record["source"]["source"]
    witness = record["witness"]
    receipts = json.loads(capture.with_name("market-receipts.json").read_bytes())
    samples = json.loads(capture.with_name("clock-summary.json").read_bytes())
    markers = json.loads(capture.with_name("capture-markers.json").read_bytes())
    if (digest(canonical(receipts)) != source["receipts_sha256"]
            or digest(canonical(samples)) != witness["calibration_ref"]):
        raise ValueError("RECORDED_RECEIPTS_MISMATCH")
    output.mkdir()
    probe = runpy.run_path(str(Path(__file__).with_name("probe-qv1-market-qualification.py")))
    with redirect_stdout(io.StringIO()):
        probe["evaluate_capture"](output, receipts, samples, markers)
    computed = json.loads((output / "qualification.json").read_bytes())
    for key in ("source", "witness", "joined_inputs", "gates", "observation_outcome"):
        if computed[key] != record[key]:
            raise ValueError("RECORDED_DECISION_MISMATCH:" + key)
    evaluator = computed["evaluator"]
    if computed["signal_id"] is not None or computed["production_qualification_enabled"]:
        raise ValueError("RECORDED_INPUT_CANNOT_PROMOTE")
    path = output / "research.sqlite"
    key = "research/" + handoff["event_id"]
    payload = canonical(handoff)
    if not WindowsOperationalJournal(path).create_if_absent(key, payload):
        raise ValueError("NEW_RECORD_NOT_CREATED")
    reopened = WindowsOperationalJournal(path)
    if reopened.create_if_absent(key, payload) or reopened.read(key) != payload:
        raise ValueError("REOPEN_DUPLICATE_OR_READBACK_FAILURE")
    if (evaluator["reconciliation"] != "PASS" or not evaluator["context_complete"]
            or computed["gates"]["UTC_WITNESS"] != "PASS"
            or evaluator["research_market_gate"] != "PASS"):
        detection = "DATA_INVALID"
    elif evaluator["setup_reason"] in ("NO_BREAKOUT", "NO_FALSE_TO_TRUE_TRANSITION"):
        detection = "NO_TRIGGER"
    elif evaluator["setup_state"] == "DETECTED_SIGNAL":
        detection = "CANDIDATE_SHADOW_ONLY"
    else:
        detection = "QUALIFICATION_BLOCKED"
    return dict(
        source="RECORDED_PUBLIC_SPOT", symbol=source["symbol"], capture_sha256=pin,
        source_manifest_sha256=record["source"]["source_sha256"],
        receipt_set_sha256=source["receipts_sha256"], clock_receipt_sha256=witness["calibration_ref"],
        detector_sha256=evaluator["rule_sha256"], evaluator_policy_sha256=computed["policy_sha256"],
        research_gates=computed["gates"], setup_reason=evaluator["setup_reason"],
        detection=detection, disposition="QUALIFICATION_BLOCKED", readiness="NOT_READY",
        signal_id=None, dispatch_attempts=0, custody_sha256=digest(payload),
        journal_integrity=reopened.verify_all(),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("pin")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.resolve().drive.upper() != "D:":
        parser.error("output on D: required")
    print(canonical(replay(args.capture, args.pin, args.output)).decode())


if __name__ == "__main__":
    main()

