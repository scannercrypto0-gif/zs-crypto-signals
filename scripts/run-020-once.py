"""Manual native entry. With no PM comment pin it performs zero market I/O."""
import argparse
import json
import os
from pathlib import Path
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--workspace',required=True)
    p.add_argument('--review-comment-id',type=int)
    a=p.parse_args()
    if not a.review_comment_id:
        print(json.dumps(dict(status='020_FIELD_PREFLIGHT_BLOCKED',reason='INDEPENDENT_PM_COMMENT_REQUIRED',market_requests=0)))
        return 2
    from zs_smart_gate.pilot020_native import execute
    os.chdir(Path(__file__).resolve().parents[1])
    try:
        result=execute(a.manifest,a.review_comment_id,a.workspace)
        print(json.dumps(result,sort_keys=True));return 0
    except Exception as exc:
        # Never print a token, GCM stdout, HTTP headers or response body.
        print(json.dumps(dict(status='020_FIELD_PREFLIGHT_BLOCKED_OR_STOPPED',reason=type(exc).__name__,
                             detail=str(exc) if isinstance(exc,ValueError) else 'SANITIZED_NATIVE_ERROR')))
        return 2


if __name__=='__main__':sys.exit(main())
