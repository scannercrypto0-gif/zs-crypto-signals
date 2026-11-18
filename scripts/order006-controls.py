"""Synthetic Order006 funnel controls. No network, scientific approval or dispatch."""
import argparse
from pathlib import Path
import runpy

from zs_smart_gate.marketwide_cursor import ScanLedger
from zs_smart_gate.stage05_contracts import canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.resolve().drive.upper() != "D:":
        parser.error("output must be on D:")
    args.output.mkdir()
    fixture = runpy.run_path(str(Path(__file__).resolve().parents[1]/"tests"/"test_marketwide_research.py"))
    results = {}
    for benchmark in ("UP", "DOWN"):
        names = dict(BTCUSDT=benchmark, ETHUSDT=benchmark, OTHERUSDT="UP",
                     BEARUSDT="DOWN", FLATUSDT="FLAT")
        snap, _ = fixture["snapshot"](names)
        path = args.output / (benchmark + ".sqlite")
        ledger = ScanLedger(path)
        scan = ledger.register(snap, fixture["packet"]()["boundary_ms"])
        for _ in range(3):
            report = ScanLedger(path).chunk(
                scan, lambda item: fixture["packet"](item["symbol"], names[item["symbol"]]),
                max_pairs=2, healthy=lambda: True)
        results[benchmark] = report
    result = dict(scope="SYNTHETIC_TEST_ONLY", live_e2e="LIVE_E2E_NOT_PROVEN",
                  up_detector_engineering="PASS", down_detector_engineering="PASS", cases=results)
    (args.output/"controls.json").write_bytes(canonical(result))
    print(canonical(result).decode())


if __name__ == "__main__":
    main()
