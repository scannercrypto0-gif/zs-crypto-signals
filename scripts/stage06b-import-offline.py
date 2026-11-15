"""Stage06B OFFLINE Windows/local archive staging; no implicit SQL connection.

Example:
  py -3.12 -B scripts/stage06b-import-offline.py --manifest D:\secure\a.json \
      --export D:\secure\a\result.json --root D:\secure\a

Repeat --manifest/--export/--root for A, B and C. Prints ONLY hashes and
counts; source messages, bot/chat IDs and credentials are never printed.
"""
import argparse
import json
import os
from pathlib import Path
import sys

from zs_smart_gate.stage06b_desktop_sql import build_sql_staging, apply_sql_server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="append", type=Path, required=True)
    parser.add_argument("--export", action="append", type=Path, required=True)
    parser.add_argument("--root", action="append", type=Path, required=True)
    parser.add_argument("--apply-sql", action="store_true",
                        help="Opt-in to locally authorized SQL Server via ZS_STAGE06B_SQL_ODBC")
    parser.add_argument("--authorize-local-sql-write", action="store_true")
    args = parser.parse_args(argv)
    if not (len(args.manifest) == len(args.export) == len(args.root)):
        raise ValueError("STAGE06B_INPUT_COUNTS_MISMATCH")
    if args.apply_sql != args.authorize_local_sql_write:
        raise ValueError("STAGE06B_SQL_EXPLICIT_AUTHORIZATION_REQUIRED")
    sources = [
        {"manifest": json.loads(m.read_bytes()),
         "raw_export": e.read_bytes(), "root": root}
        for m, e, root in zip(args.manifest, args.export, args.root)]
    packet = build_sql_staging(sources)
    summary = {"schema": packet["schema"], "batch_sha256": packet["batch_sha256"],
               "messages_count": len(packet["messages"]),
               "candidates_count": len(packet["candidates"]),
               "signals_count": len(packet["signals"]),
               "decisions_count": len(packet["candidate_decisions"]),
               "indicator_values_count": len(packet["indicator_values"]),
               "attachments_count": len(packet["attachments"]),
               "sql_executed": False}
    if args.apply_sql:
        odbc = os.environ.get("ZS_STAGE06B_SQL_ODBC")
        if not odbc:
            raise ValueError("STAGE06B_SQL_CONNECTION_NOT_CONFIGURED")
        import pyodbc  # Optional, installed ONLY on owner machine when authorized.
        conn = pyodbc.connect(odbc, autocommit=False, timeout=10)
        try:
            receipt = apply_sql_server(conn, packet)
            summary["sql_executed"] = receipt["transaction_committed"]
            summary["rows_verified"] = receipt["rows_verified"]
        finally:
            conn.close()
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Never print source paths, messages, credentials, SQL connection strings.
        print("STAGE06B_STOP_" + type(exc).__name__, file=sys.stderr)
        sys.exit(2)
