"""ORDER-022 offline-only entrypoint. Does not fetch or generate market data."""
import argparse
import json
from pathlib import Path

from zs_smart_gate.stage03_order022 import ResearchBlocked, canonical, freeze, inventory, run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("inventory", "freeze", "run"))
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--catalog", help="Local 12-file SHA256 catalog; freeze requires it")
    parser.add_argument("--manifest", help="One-time frozen experiment manifest file")
    parser.add_argument("--database", help="New local research database for real run")
    parser.add_argument("--backup", help="Different path for independent SQLite backup")
    parser.add_argument("--output", required=True, help="Write-once JSON technical report")
    args = parser.parse_args()
    if args.command == "inventory":
        response = inventory(args.data_dir, args.catalog)
    elif args.command == "freeze":
        if not args.catalog or not args.manifest:
            parser.error("Freeze requires --catalog and --manifest")
        response = freeze(args.data_dir, args.catalog, args.manifest)
    else:
        if not all((args.manifest, args.database, args.backup)):
            parser.error("Run requires frozen --manifest, --database and --backup")
        response = run(args.manifest, args.data_dir, args.database, args.backup)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as fp:
        fp.write(canonical(response) + b"\n")
    print(json.dumps({"status": response.get("status", "FROZEN"),
                      "source": response.get("source_kind", response.get("source")),
                      "report": str(destination),
                      "market_requests": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
