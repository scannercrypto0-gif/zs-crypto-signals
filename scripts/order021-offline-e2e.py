"""Offline-only reproducible ORDER-021 E2E; emits evidence, no market I/O."""
import argparse
from collections import Counter
from pathlib import Path
import json
import tempfile

from zs_smart_gate.setup021 import CONFIG_SHA256, canonical, evaluate
from zs_smart_gate.setup021_fixtures import scenario
from zs_smart_gate.setup021_store import SQLiteResearchJournal


def run():
    samples = {
        "DEV": [
            ("2026-09-01T00:00:00Z", "BTCUSDT", True, {}),
            ("2026-09-02T00:00:00Z", "BTCUSDT", False, {}),
            ("2026-09-03T00:00:00Z", "ETHUSDT", True, {}),
            ("2026-09-04T00:00:00Z", "ETHUSDT", True, {"missing": True}),
        ],
        "OOS": [
            ("2026-10-01T00:00:00Z", "BTCUSDT", True, {}),
            ("2026-10-02T00:00:00Z", "BTCUSDT", False, {}),
            ("2026-10-03T00:00:00Z", "ETHUSDT", True, {}),
            ("2026-10-04T00:00:00Z", "ETHUSDT", True, {"forming": True}),
            ("2026-10-05T00:00:00Z", "ETHUSDT", True, {"delayed": True}),
        ],
    }
    with tempfile.TemporaryDirectory(prefix="order021-offline-") as tmp:
        root = Path(tmp)
        journal = SQLiteResearchJournal(root / "research.sqlite")
        summaries = {}
        for partition, rows in samples.items():
            outcomes = []
            for date, symbol, breakout, flags in rows:
                bundle = scenario(date, symbol=symbol, breakout=breakout, **flags)
                value = evaluate(**bundle, partition=partition)
                ack = journal.append_readback(value)
                if ack != "COMMITTED_AND_READBACK_VERIFIED":
                    raise RuntimeError("EVIDENCE_WRITE_NOT_CONFIRMED")
                outcomes.append(value)
            summaries[partition] = {
                "count": len(outcomes),
                "by_symbol": {s: {
                    "candidates": sum(r["status"] == "RESEARCH_CANDIDATE" and r["symbol"] == s for r in outcomes),
                    "detected_internal": sum(r["status"] == "DETECTED_SIGNAL" and r["symbol"] == s for r in outcomes),
                } for s in ("BTCUSDT", "ETHUSDT")},
                "excluded": dict(sorted(Counter(
                    reason for r in outcomes if r["status"] == "RESEARCH_CANDIDATE" for reason in r["reason_codes"]
                ).items())),
                "outcome_labels": "NOT_AVAILABLE",
                "accuracy": "INSUFFICIENT_EVIDENCE",
                "net_returns_after_costs": "NOT_CALCULATED_NO_OUTCOME_DATA",
                "historical_pit": "HISTORICAL_PIT_UNVERIFIED",
            }
        restore = journal.backup_and_restore_verify(root / "independent-restore.sqlite")
        all_rows = journal.rows()
        if restore["rows"] != sum(x["count"] for x in summaries.values()):
            raise RuntimeError("RESTORE_COUNT_MISMATCH")
        if any(r["contract_sha256"] != CONFIG_SHA256 for r in all_rows):
            raise RuntimeError("CONTRACT_CHANGED")
        return {
            "order": "ORDER-021",
            "status": "OFFLINE_SYNTHETIC_E2E_PASS",
            "contract_sha256": CONFIG_SHA256,
            "source": "SYNTHETIC_PUBLIC_KLINE_FORMAT_ONLY_NOT_BINANCE_OBSERVED",
            "stages": [
                "SYNTHETIC_FIXTURE", "EXISTING_BINANCE_KLINE_PARSER",
                "EXISTING_SCANNER_AND_CORE_CANDIDATE",
                "CLOSED_AND_RECEIPT_TIME_GUARDS",
                "FROZEN_SETUP_V1", "EVENT_ID_AND_DEDUP",
                "SQLITE_COMMIT_READBACK", "INDEPENDENT_BACKUP_RESTORE",
            ],
            "DEV": summaries["DEV"],
            "OOS": summaries["OOS"],
            "PROSPECTIVE": {"count": 0, "status": "NOT_AUTHORIZED_NOT_OBSERVED"},
            "restore": restore,
            "market_requests": 0,
            "field_authorization": "NOT_GRANTED",
            "publishable": False,
            "qualified": False,
            "score": None,
            "probability": None,
            "historical_pit": "HISTORICAL_PIT_UNVERIFIED",
            "utc_independent_authority": "NOT_PROVEN",
            "windows_owner_native_recovery": "NOT_PROVEN",
            "stage05": "FULL_HOLD",
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    a = parser.parse_args()
    report = run()
    dest = Path(a.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(canonical(report) + b"\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
