"""Replay only published evidence on Windows, with no network."""
import argparse
import json
from pathlib import Path
import tempfile

from zs_smart_gate.e2e51 import analyze, persist
from zs_smart_gate.stage05_contracts import canonical, digest, make_document, parse_utc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    opts = parser.parse_args()
    if opts.scratch.resolve().drive.upper() != "D:":
        parser.error("scratch must be on D:")
    here = Path(__file__).resolve().parent
    expected = json.loads((here / "stage04-readback.json").read_bytes())
    report = json.loads((here / "market-report.json").read_bytes())
    original = expected["stage05_event"]
    decision = int(parse_utc(original["timestamps"]["decision_at"]).timestamp() * 1000)
    receipts = json.loads((here / "market-receipts.json").read_bytes())
    event = analyze(receipts, decision, synthetic=False)
    if event != original:
        raise SystemExit("REPLAY_DECISION_MISMATCH")
    with tempfile.TemporaryDirectory(dir=opts.scratch) as d:
        value, _ = persist(Path(d), receipts, event)
    expected_hash = report["evidence_sha256"]
    if (value != expected or digest(canonical(value)) != expected_hash
            or make_document(event)["document"] != (here / "analytics-test-only.json").read_bytes()):
        raise SystemExit("REPLAY_READBACK_OR_ARCHIVE_MISMATCH")
    print("GITHUB_MARKET_RECEIPT_REPLAY_PASS", expected_hash)


if __name__ == "__main__":
    main()
