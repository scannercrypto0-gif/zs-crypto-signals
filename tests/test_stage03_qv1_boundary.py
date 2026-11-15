from pathlib import Path
import tempfile
import unittest

from test_stage51_material import bind, fixture
from test_stage05_real_telegram import event
from zs_smart_gate.stage03_qv1_boundary import (
    FIXTURE_GATES, evaluate_boundary, fixture_stage05, seal_fixture,
)
from zs_smart_gate.stage05_contracts import ContractError, canonical, digest
from zs_smart_gate.stage05_custody import LocalOutbox
from zs_smart_gate.stage05_delivery import DeliveryCoordinator, plan


def bound(row, gates):
    source = row["source"]
    source.update(venue="BINANCE_SPOT", scope=row["source_scope"],
                  path=[row["horizon"], row["direction"]],
                  event_close_at=row["event_close_at"], decision_at=row["decision_at"],
                  feed="FIXTURE-FEED", fixture_gates_sha256=digest(canonical(gates)))
    for bar in row["candles"].values():
        bar.update(feed=source["feed"], symbol=row["symbol"])
    for name in ("clock", "liquidity"):
        if name in source:
            source[name]["bound_feed"] = source["feed"]
    return bind(row)


class Qv1BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.store = LocalOutbox(Path(self.temp.name) / "test.sqlite")
        self.gates = dict.fromkeys(FIXTURE_GATES, "PASS")

    def test_approved_fixture_branch_with_no_score_and_reopen(self):
        row = bound(fixture(), self.gates)
        decision = seal_fixture(row, self.gates, self.store)
        self.assertEqual(decision["qualification_state"], "QUALIFIED")
        self.assertIsNone(decision["score"])
        self.assertEqual(decision, seal_fixture(row, self.gates, LocalOutbox(self.store.path)))
        out = fixture_stage05(row, self.gates, self.store, event())
        jobs = plan(out)
        self.assertEqual([job.destination for job in jobs], ["A","B","C"])
        self.assertEqual({job.signal_id for job in jobs}, {decision["signal_id"]})
        self.assertTrue(out["signal_id"].startswith("fixture-sig-"))
        with self.assertRaisesRegex(ContractError, "SYNTHETIC_EVENT_LIVE"):
            from test_stage05_real_telegram import config
            DeliveryCoordinator(store=self.store, config=config()).step(out, "A")

    def test_failure_and_missing_gate_never_signal(self):
        self.gates["SETUP"] = "FAIL"
        row = bound(fixture(), self.gates)
        out = fixture_stage05(row, self.gates, self.store, event())
        self.assertEqual(out["qualification_status"], "REJECTED")
        self.assertIsNone(out["signal_id"])
        self.assertEqual([job.destination for job in plan(out)], ["C"])
        self.gates.pop("SETUP")
        self.assertEqual(fixture_stage05(bound(fixture(direction="DOWN"), self.gates),
                         self.gates, self.store, event())["route"], "05B_AUDIT_ONLY")

    def test_real_holds_and_fixture_relabel_blocked(self):
        row = fixture()
        row["source_scope"] = "APPROVED_REAL_SOURCE"
        bound(row, self.gates)
        out = evaluate_boundary(row)
        self.assertEqual(out["qualification_state"], "UNKNOWN")
        self.assertEqual(out["setup_state"], "DETECTED_SIGNAL")
        self.assertIsNone(out["signal_id"])
        with self.assertRaisesRegex(ContractError, "FORBIDS_REAL_SOURCE"):
            seal_fixture(row, self.gates, self.store)

    def test_future_partial_mixed_sem_and_n03_fail_closed(self):
        cases = [
            (lambda r: r["candles"]["5m"].update(feed="OTHER"), "MIXED_CANDLE"),
            (lambda r: r["candles"]["5m"].update(closed=False), "CAUSAL_FRAME"),
            (lambda r: r["candles"]["5m"].update(available_at="2026-11-09T00:00:01Z"), "CAUSAL_FRAME"),
            (lambda r: r["components"].update(N03={"status":"PRESENT","reason":"FORBIDDEN"}), "N03_NOT_APPROVED"),
            (lambda r: r.update(sem_mappings={"SEM-I-01":"FORBIDDEN"}), "SEM_MAPPING"),
        ]
        for mutate, error in cases:
            with self.subTest(error=error):
                row = bound(fixture(), self.gates)
                mutate(row)
                with self.assertRaisesRegex(ContractError, error):
                    evaluate_boundary(bind(row))

    def test_same_event_cannot_replace_gate_evidence(self):
        seal_fixture(bound(fixture(),self.gates), self.gates, self.store)
        changed = {**self.gates, "SETUP": "FAIL"}
        with self.assertRaisesRegex(ContractError, "READBACK_CONFLICT"):
            seal_fixture(bound(fixture(),changed), changed, self.store)
    def test_real_rejection_replays_existing_archive_without_dispatch(self):
        import json
        from zs_smart_gate.stage03_qv1_boundary import recorded_rejection_archive
        from zs_smart_gate.stage05_contracts import parse_utc
        from zs_smart_gate.stage51_integration import prepare
        source = Path("research/stage51/closure/final-003-account-a-retry1")
        report = json.loads((source/"final-manifest.json").read_bytes())
        receipts = json.loads((source/"market-receipts.json").read_bytes())
        upstream, ref, _ = prepare(Path(self.temp.name), session_id="QV1-REJECTION-REPLAY",
                                   receipts=receipts,
                                   decision_ms=int(parse_utc(report["decision_at"]).timestamp()*1000),
                                   reviewed_readback_sha=report["stage04_readback_sha256"])
        verified, document = recorded_rejection_archive(upstream, *ref)
        self.assertIsNone(verified["signal_id"])
        self.assertEqual(document["manifest"]["sha256"], report["archive_sha256"])
        self.assertEqual([job.destination for job in plan(verified)], ["C"])
