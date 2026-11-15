"""Exercise Stage04 backup and fresh-path restore with a non-secret test record."""
import argparse
import json
from pathlib import Path

from test_stage03_research_handoff import synthetic_handoff
from zs_smart_gate.stage04_windows_operational import WindowsOperationalJournal
from zs_smart_gate.stage05_contracts import canonical, digest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=("backup", "restore", "verify"))
parser.add_argument("journal", type=Path)
parser.add_argument("--backup", type=Path)
parser.add_argument("--pin")
parser.add_argument("--external", action="store_true")
args = parser.parse_args()
row = synthetic_handoff()
payload = canonical(row)
key = "research/" + row["event_id"]
if args.mode == "backup":
    if args.journal.exists():
        parser.error("use a fresh drill journal")
    journal = WindowsOperationalJournal(args.journal)
    if not journal.create_if_absent(key, payload) or journal.create_if_absent(key, payload):
        raise RuntimeError("CUSTODY_DUPLICATE_FAILURE")
    print(json.dumps(journal.make_backup(args.backup, expected_external_volume=args.external).__dict__))
elif args.mode == "restore":
    journal = WindowsOperationalJournal.restore_to_new_path(args.backup, args.pin, args.journal)
else:
    if not args.journal.is_file():
        parser.error("restored journal is missing")
    journal = WindowsOperationalJournal(args.journal)
if journal.read(key) != payload or journal.verify_all() != (1, len(payload)):
    raise RuntimeError("CUSTODY_READBACK_FAILURE")
print(json.dumps({"operation": args.mode, "readback": "PASS", "payload_sha256": digest(payload)}))
