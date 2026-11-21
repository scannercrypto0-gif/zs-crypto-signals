"""CLOCK74 Windows offline suite runner with socket/urllib traffic blocked."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if os.name != "nt" or sys.version_info[:3] != (3, 12, 10):
        parser.error("Windows Python 3.12.10 required")
    if args.receipt.resolve().drive.upper() != "D:":
        parser.error("receipt must be on D:")
    sys.path.insert(0, str(root/"tests"))
    attempts = []

    def forbidden(*unused_args, **unused_kwargs):
        attempts.append("SOCKET_OR_URLLIB_CONNECTION_ATTEMPT")
        raise PermissionError("CLOCK74_OFFLINE_NETWORK_FORBIDDEN")

    started = time.monotonic()
    with ExitStack() as stack:
        for target in (
                "socket.socket.connect", "socket.socket.connect_ex",
                "socket.create_connection", "urllib.request.urlopen",
                "urllib.request.OpenerDirector.open"):
            stack.enter_context(patch(target, forbidden))
        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromName(args.suite))
    receipt = dict(
        suite=args.suite, tests=result.testsRun, failures=len(result.failures),
        errors=len(result.errors), skipped=len(result.skipped),
        passed=result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
        success=result.wasSuccessful() and not result.skipped and not attempts,
        duration_seconds=round(time.monotonic()-started, 6),
        python_network_attempts=len(attempts),
        network_scope="PYTHON_SOCKET_AND_URLLIB_BLOCKED_DURING_TESTS",
    )
    args.receipt.write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    return 0 if receipt["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
