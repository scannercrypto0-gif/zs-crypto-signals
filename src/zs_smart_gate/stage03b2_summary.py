"""Read frozen research JSON produced by individual on-demand Github Actions jobs.

Artifacts are transient CI evidence; GitHub repo storage backend NOT decided.
The summary NEVER promotes a numerical score, probability or Signal.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .stage03b2_manifest import MANIFEST
from .stage03b2_research import compare_study


def collect_directory(directory: str) -> dict:
    root=Path(directory)
    rows=[]
    for path in sorted(root.glob("*.json")):
        with path.open("r",encoding="utf-8") as stream:
            rows.append(json.load(stream))
    summary=compare_study(rows,MANIFEST)
    summary["transient_ci_artifacts_not_durable_source_of_truth"]=True
    summary["files_received"]=len(rows)
    summary["manifest"]=MANIFEST.as_dict()
    return summary


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="03B2 frozen nonpredictive study summary")
    parser.add_argument("--directory",required=True)
    args=parser.parse_args(argv)
    out=collect_directory(args.directory)
    print(json.dumps(out,sort_keys=True))
    # INSUFFICIENT_EVIDENCE is the expected research conclusion, not CI failure.
    return 0


if __name__=="__main__":
    raise SystemExit(main())
