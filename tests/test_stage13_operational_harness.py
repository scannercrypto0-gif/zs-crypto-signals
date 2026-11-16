from pathlib import Path
import sqlite3
import tempfile
from contextlib import closing
from unittest import TestCase
from unittest.mock import patch

from zs_smart_gate.stage05_contracts import ContractError, canonical, digest
from zs_smart_gate.stage05_custody import LocalOutbox
from zs_smart_gate.stage13_operational_harness import CycleController, MockUnavailable, Ports, STAGES

NOW = "2026-11-16T14:00:02Z"
MARKET = dict(scope="SYNTHETIC_TEST_ONLY", source_id="SYNTHETIC:STAGE13",
              coverage="COMPLETE_FIXTURE", closed=True, qualified_fixture=True,
              closed_at="2026-11-16T14:00:00Z", received_at=NOW, available_at=NOW,
              reference_at=NOW, symbol="BTCUSDT", direction="UP", rule="FIXTURE_V1")


class MockServices:
    def __init__(self):
        self.row = MARKET.copy()
        self.objects = {}
        self.deliveries = {}
        self.calls = []
        self.failure = None
        self.fail_after_commit = None
        self.corrupt = False
        self.bad_ack = None
        self.monotonic = iter((0, 10, 20, 50, 60, 160))

    def scan(self):
        if self.failure == "scanner":
            raise MockUnavailable
        return self.row

    def apply(self, stage, key, identity, raw):
        self.calls.append(stage)
        if self.failure == stage:
            raise MockUnavailable
        record = (stage, identity, digest(raw))
        if self.deliveries.setdefault(key, record) != record:
            raise AssertionError("MOCK_IDEMPOTENCY_CONFLICT")
        if self.fail_after_commit == stage:
            raise MockUnavailable
        return "wrong" if self.bad_ack == stage else key

    def put(self, key, identity, raw):
        ack = self.apply("github", key, identity, raw)
        self.objects.setdefault(identity, raw)
        return ack

    def read(self, identity):
        if self.failure == "read":
            raise MockUnavailable
        return b"corrupt" if self.corrupt else self.objects.get(identity)

    def ports(self):
        return Ports(self.scan, self, lambda key, dest, ident, raw:
                     self.apply("telegram_" + dest.lower(), key, ident, raw),
                     lambda *args: self.apply("sql", *args),
                     lambda *args: self.apply("outcome", *args),
                     lambda: NOW, lambda: next(self.monotonic))


class Stage13Tests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.services = MockServices()

    def controller(self, name="test.db", quota=9):
        return CycleController(journal=LocalOutbox(self.root / name),
                               ports=self.services.ports(), quota=quota)

    def test_stable_signal_readback_and_three_destinations(self):
        ctl = self.controller()
        first = ctl.scan_once()
        duplicate = ctl.scan_once()
        self.assertEqual(first["status"], "MOCK_PASS")
        self.assertEqual(first["signal_id"], duplicate["signal_id"])
        self.assertEqual(self.services.calls, list(STAGES))
        self.assertEqual(set(first["receipts"]), set(STAGES))
        for receipt in first["receipts"].values():
            self.assertEqual(receipt["signal_id"], first["signal_id"])
            self.assertEqual(receipt["sha256"], first["sha256"])
        self.assertEqual(first["readiness"], "NOT_READY")
        self.assertFalse(first["trading_authorized"])

    def test_invalid_observations_never_deliver(self):
        for fields, reason in (
            (dict(scope="LIVE"), "S13_SYNTHETIC_SOURCE_REQUIRED"),
            (dict(coverage="PARTIAL"), "S13_SOURCE_OR_COVERAGE_INVALID"),
            (dict(closed=False), "S13_INCOMPLETE_CANDLE"),
            (dict(available_at="2026-11-16T14:00:03Z"), "S13_MARKET_TIME_INVALID"),
            (dict(closed_at="2026-11-16T13:58:00Z"), "S13_STALE_CANDLE"),
            (dict(reference_at="2026-11-16T13:59:59Z"), "S13_CLOCK_DRIFT"),
        ):
            with self.subTest(reason=reason):
                self.services.row = dict(MARKET, **fields)
                result = self.controller().scan_once()
                self.assertEqual(result["status"], "INVALID_OBSERVATION")
                self.assertEqual(result["reason"], reason)
        self.services.row = dict(MARKET, qualified_fixture=False)
        self.assertEqual(self.controller().scan_once()["status"], "NO_QUALIFIED_FIXTURE")
        self.assertEqual(self.services.calls, [])

    def test_quota_latency_and_health(self):
        result = self.controller(quota=6).run(3)
        self.assertEqual([item["status"] for item in result["reports"]],
                         ["MOCK_PASS","MOCK_PASS","QUOTA_EXHAUSTED"])
        self.assertEqual(result["mock_latency_ns"], {"p50":30,"p95":100})
        self.assertEqual(result["health"], "MOCK_DEGRADED")
        self.assertEqual(result["reports"][-1]["hypothetical_weight_used"], 6)

    def test_outage_and_restart_after_mock_send_commit(self):
        self.services.failure = "scanner"
        self.assertEqual(self.controller().scan_once()["status"], "SCAN_UNAVAILABLE")
        self.services.failure = None
        self.services.fail_after_commit = "telegram_b"
        interrupted = self.controller().scan_once()
        self.assertEqual(interrupted["status"], "PENDING_MOCK_RETRY")
        self.assertEqual(interrupted["stage"], "telegram_b")
        self.services.fail_after_commit = None
        recovered = self.controller().resume(interrupted["signal_id"])
        self.assertEqual(recovered["status"], "MOCK_PASS")
        self.assertEqual(len(self.services.deliveries), 6)
        self.assertEqual(self.services.calls.count("telegram_a"), 1)
        self.assertEqual(self.services.calls.count("telegram_b"), 2)
        self.assertEqual(self.services.calls.count("sql"), 1)

    def test_github_failure_corruption_and_restore_with_pin(self):
        self.services.failure = "github"
        interrupted = self.controller().scan_once()
        self.assertEqual(interrupted["stage"], "github")
        self.services.failure = None
        self.services.corrupt = True
        identity = interrupted["signal_id"]
        self.assertEqual(self.controller().resume(identity)["status"], "STORAGE_READBACK_MISMATCH")
        self.services.corrupt = False
        done = self.controller().resume(identity)
        fresh = self.controller("restore.db")
        self.assertEqual(fresh.resume(identity)["status"], "RESTORE_PIN_REQUIRED")
        self.assertEqual(fresh.resume(identity, expected_sha256="0"*64)["status"], "RESTORE_CHECKSUM_MISMATCH")
        self.services.failure = "read"
        self.assertEqual(fresh.resume(identity, expected_sha256=done["sha256"])["status"], "RESTORE_UNAVAILABLE")
        self.services.failure = None
        replay = fresh.resume(identity, expected_sha256=done["sha256"])
        self.assertEqual(replay["status"], "MOCK_PASS")
        self.assertEqual(replay["receipts"], done["receipts"])
        self.assertEqual(len(self.services.deliveries), 6)

    def test_committed_archive_with_unavailable_readback_blocks_all_delivery(self):
        self.services.failure = "read"
        stalled = self.controller().scan_once()
        self.assertEqual(stalled["status"], "PENDING_MOCK_RETRY")
        self.assertEqual(stalled["stage"], "github")
        self.assertIn(stalled["signal_id"], self.services.objects)
        self.assertEqual(stalled["receipts"], {})
        self.assertEqual(self.services.calls, ["github"])
        self.services.failure = None
        recovered = self.controller().resume(stalled["signal_id"])
        self.assertEqual(recovered["status"], "MOCK_PASS")
        self.assertEqual(self.services.calls, ["github", *STAGES])
        self.assertEqual(len(self.services.deliveries), len(STAGES))

    def test_local_signal_corruption_blocks_reopen_even_with_pin(self):
        self.services.failure = "github"
        saved = self.controller().scan_once()
        identity = saved["signal_id"]
        key = "signal/" + identity.removeprefix("fixture-")
        self.services.calls.clear()
        ctl = self.controller()
        with patch.object(ctl.journal, "read", return_value="not bytes"):
            self.assertEqual(ctl.resume(identity)["status"], "INVALID_STORED_SIGNAL")
        with patch.object(ctl.journal, "read", return_value=None):
            self.assertEqual(ctl.resume(identity)["status"], "RESTORE_PIN_REQUIRED")
        self.assertEqual(self.services.calls, [])
        with closing(sqlite3.connect(ctl.journal.path)) as db, db:
            db.execute("DROP TRIGGER no_UPDATE")
            db.execute("UPDATE records SET payload=? WHERE key=?", (b"broken", key))
        self.services.failure = None
        self.assertEqual(self.controller().resume(identity, expected_sha256=saved["sha256"])["status"],
                         "INVALID_STORED_SIGNAL")
        self.assertEqual(self.services.calls, [])
        with closing(sqlite3.connect(ctl.journal.path)) as db, db:
            db.execute("DROP TRIGGER no_UPDATE")
            db.execute("UPDATE records SET sha=? WHERE key=?", (digest(b"broken"), key))
        self.assertEqual(self.controller().resume(identity)["status"], "INVALID_STORED_SIGNAL")
        self.assertEqual(self.services.calls, [])

    def test_corrupt_ack_on_reopen_blocks_pending_transport(self):
        self.services.failure = "telegram_a"
        saved = self.controller().scan_once()
        identity = saved["signal_id"]
        key = "ack/" + digest(canonical(["outcome", identity]))
        ctl = self.controller()
        wrong = canonical({"stage": "outcome", "signal_id": identity, "sha256": "wrong"})
        ctl.journal.create_if_absent(key, wrong)
        self.services.failure = None
        self.services.calls.clear()
        report = self.controller().resume(identity)
        self.assertEqual(report["status"], "INVALID_STORED_ACK")
        self.assertEqual(report["stage"], "outcome")
        self.assertEqual(self.services.calls, [])
        with closing(sqlite3.connect(ctl.journal.path)) as db, db:
            db.execute("DROP TRIGGER no_UPDATE")
            db.execute("UPDATE records SET sha=? WHERE key=?", ("wrong", key))
        self.assertEqual(self.controller().resume(identity)["status"], "INVALID_STORED_ACK")
        self.assertEqual(self.services.calls, [])

    def test_invalid_ack_stops_before_later_integrations(self):
        self.services.bad_ack = "sql"
        result = self.controller().scan_once()
        self.assertEqual(result["status"], "INVALID_MOCK_ACK")
        self.assertNotIn("sql", result["receipts"])
        self.assertNotIn("outcome", self.services.calls)
        with self.assertRaisesRegex(ContractError, "FIXTURE_ID_REQUIRED"):
            self.controller().resume("live-id")
