"""Offline review of immutable Spot captures for Intraday UP calibration."""
from pathlib import Path
import json

from zs_smart_gate.e2e51 import analyze
from zs_smart_gate.stage05_contracts import canonical, digest, parse_utc

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = (
    ("research/stage51", "stage04-readback.json", "stage05_event"),
    ("research/stage51/live-followup-6761924797", "stage04-readback.json", "stage05_event"),
    ("research/stage51/closure/final-003-owner-override", "final-manifest.json", None),
    ("research/stage51/closure/final-003-account-a-retry1", "final-manifest.json", None),
)


def main():
    observations = []
    for folder, receipt, event_key in CAPTURES:
        root = ROOT / folder
        stored = json.loads((root / receipt).read_bytes())
        prior = stored[event_key] if event_key else stored
        decision = prior["timestamps"]["decision_at"] if event_key else prior["decision_at"]
        source = json.loads((root / "market-receipts.json").read_bytes())
        result = analyze(source, int(parse_utc(decision).timestamp() * 1000), synthetic=False)
        if event_key and result != prior:
            raise RuntimeError("RECORDED_DECISION_REPLAY_MISMATCH")
        if not event_key and digest(canonical(result)) != prior["decision_sha256"]:
            raise RuntimeError("RECORDED_DECISION_DIGEST_MISMATCH")
        n01 = next(row for row in result["indicators"] if row["indicator_id"] == "N01")
        observations.append({
            "repository_path": folder, "source_sha256": result["source_manifest_sha256"],
            "setup": result["scan_metadata"]["reasons"],
            "n01": n01["value"], "n01_window_close": result["candle_metadata"]["component_close_at"],
            "independent_strong_close_label": None,
        })
    print(json.dumps({"observations": observations,
                      "distinct_n01_windows": len({row["n01_window_close"] for row in observations}),
                      "independently_labeled_vectors": 0,
                      "selected_n01_threshold": None}, sort_keys=True))


if __name__ == "__main__":
    main()
