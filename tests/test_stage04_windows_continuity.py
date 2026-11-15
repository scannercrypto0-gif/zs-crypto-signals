"""Offline subprocess drill for Windows journal and 05B continuity."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_e2e51 import config, fixture
from test_stage03_research_handoff import synthetic_handoff
from zs_smart_gate.e2e51 import analyze
from zs_smart_gate.stage04_windows_operational import WindowsOperationalJournal
from zs_smart_gate.stage05_contracts import canonical, digest
from zs_smart_gate.stage05_custody import LocalOutbox
from zs_smart_gate.stage05_delivery import DeliveryCoordinator
from zs_smart_gate.stage05_telegram_http import ApiResult


def worker(root, phase):
    row = synthetic_handoff()
    payload = canonical(row)
    key = "research/" + row["event_id"]
    journal = WindowsOperationalJournal(root / "journal.sqlite")
    if phase == "offline":
        assert journal.create_if_absent(key, payload)
    assert not journal.create_if_absent(key, payload)
    assert journal.read(key) == payload
    assert journal.verify_all() == (1, len(payload))
    calls = []

    class FakeTransport:
        def send_document(self, *args, **kwargs):
            calls.append(1)
            if phase == "fail":
                raise OSError("simulated Telegram connection reset")
            return ApiResult("ACCEPTED", 1, "2026-11-09T12:00:00Z")

    source, now = fixture()
    event = analyze(source, now, synthetic=True)
    db_name = "failed.sqlite" if phase in ("fail", "recover") else "delivery.sqlite"
    outbox = LocalOutbox(root / db_name)
    coordinator = DeliveryCoordinator(store=outbox, config=config(), simulation=True,
                                      transports={"ANALYTICS": FakeTransport()})
    with patch("socket.create_connection", side_effect=AssertionError("NETWORK_FORBIDDEN")):
        result = coordinator.step(event, "C", network_available=phase != "offline")
    assert outbox.read("delivery/" + result["delivery_id"]) is not None
    if phase == "offline":
        # Terminate without interpreter cleanup after durable commits.
        print(json.dumps([result["status"], len(calls), digest(payload), result["delivery_id"]]), flush=True)
        os._exit(17)
    print(json.dumps([result["status"], len(calls), digest(payload), result["delivery_id"]]))


class ContinuityTests(unittest.TestCase):
    def test_restart_offline_resume_and_ambiguous_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = []
            for phase, code, status, calls in (
                ("offline", 17, "PENDING_OFFLINE", 0),
                ("online", 0, "ACCEPTED", 1),
                ("duplicate", 0, "ACCEPTED", 0),
                ("fail", 0, "UNKNOWN_DELIVERY", 1),
                ("recover", 0, "UNKNOWN_DELIVERY", 0),
            ):
                run = subprocess.run([sys.executable, __file__, tmp, phase],
                                     capture_output=True, text=True, timeout=20)
                self.assertEqual(run.returncode, code, run.stderr)
                result = json.loads(run.stdout)
                self.assertEqual(result[:2], [status, calls])
                results.append(result)
                print(phase, run.stdout.strip(), flush=True)
            self.assertEqual(len({row[2] for row in results}), 1)
            self.assertEqual(len({row[3] for row in results[:3]}), 1)
            self.assertEqual(results[3][3], results[4][3])



if __name__ == "__main__":
    worker(Path(sys.argv[1]), sys.argv[2])
