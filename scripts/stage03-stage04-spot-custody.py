"""Persist and independently verify a pinned Spot research capture in Stage04."""
import argparse
import json
from pathlib import Path

from zs_smart_gate.stage03_research_handoff import make_recorded_spot_handoff
from zs_smart_gate.stage04_windows_operational import WindowsOperationalJournal
from zs_smart_gate.stage05_contracts import canonical, digest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=("write", "verify"))
parser.add_argument("capture", type=Path)
parser.add_argument("pin")
parser.add_argument("journal", type=Path)
args = parser.parse_args()

raw = args.capture.read_bytes()
handoff = make_recorded_spot_handoff(raw, args.pin)
record = json.loads(raw)
for filename, expected in (
    ("market-receipts.json", record["source"]["source"]["receipts_sha256"]),
    ("clock-summary.json", record["witness"]["calibration_ref"]),
):
    if digest(canonical(json.loads(args.capture.with_name(filename).read_bytes()))) != expected:
        raise SystemExit("CAPTURE_RECEIPT_MISMATCH:" + filename)
payload = canonical(handoff)
key = "research/" + handoff["event_id"]
if args.mode == "verify" and not args.journal.is_file():
    raise SystemExit("JOURNAL_MISSING")
journal = WindowsOperationalJournal(args.journal)
if args.mode == "write":
    journal.create_if_absent(key, payload)
    if journal.create_if_absent(key, payload):
        raise SystemExit("DUPLICATE_ACCEPTED")
if journal.read(key) != payload:
    raise SystemExit("READBACK_MISMATCH")
print(canonical({
    "operation": args.mode, "capture_sha256": args.pin, "record_sha256": digest(payload),
    "event_id": handoff["event_id"], "evaluation_status": handoff["evaluation_status"],
    "qualification_state": handoff["qualification_state"], "signal_id": handoff["signal_id"],
    "delivery_authorized": handoff["delivery_authorized"], "journal_integrity": journal.verify_all(),
}).decode())
