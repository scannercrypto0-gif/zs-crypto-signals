"""Read private D: original-source manifests and emit a sanitized science intake."""
import argparse
import json
import os
from pathlib import Path
import sys

from zs_smart_gate.order007_science import source_intake


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (os.name != "nt" or sys.version_info[:3] != (3, 12, 10)
            or args.data.resolve().drive.upper() != "D:"
            or args.output.resolve().drive.upper() != "D:"):
        parser.error("OWNER_WINDOWS_PYTHON_3_12_10_D_ONLY")
    if args.output.exists():
        parser.error("DO_NOT_OVERWRITE_SCIENTIFIC_MANIFEST")
    result = source_intake(args.data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n",
                           encoding="utf-8")
    print(json.dumps({"dataset_id_sha256": result["dataset_id_sha256"],
                      "symbol_count": result["symbol_count"],
                      "event_count": result["event_count"],
                      "status": result["status"],
                      "output": str(args.output)}, sort_keys=True))
    return 0 if not result["rejected_manifests"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
