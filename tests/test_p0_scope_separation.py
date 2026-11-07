"""006B: offline scope separation between functional research record and raw PIT.

Reuses accepted 03A contracts and 006 field harness without changing them.
These synthetic tests do NOT license a source, prove publisher-time PIT,
qualify a live signal, enable Telegram or validate a full SQL pipeline.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

from zs_smart_gate.stage03a_contracts import (
    Direction, EventIdentity, Horizon, Lifecycle, LifecycleObservation,
    PITDecisionSnapshot, unavailable_score,
)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "p0_field_harness_for_scope_check", ROOT / "scripts/p0-field-harness.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
UTC = timezone.utc
T0 = datetime(2026, 11, 7, 8, 0, tzinfo=UTC)


class ScopedEvidenceContracts(unittest.TestCase):
    def test_structural_research_record_without_full_market_raw_archive(self):
        """A decision record has identity, source/as-of and reasons, but no feed archive."""
        identity = EventIdentity.research_key(
            symbol="BTCUSDT", direction=Direction.UP, horizon=Horizon.INTRADAY,
            setup_type="RESEARCH_CONTINUATION",
            decision_candle_close_at=T0,
            rule_version="03A_RESEARCH_ONLY", event_discriminator="synthetic-006b")
        snapshot = PITDecisionSnapshot(
            source_id="SYNTHETIC:OFFLINE:FIXTURE",
            candle_open_at=T0 - timedelta(minutes=30),
            candle_close_at=T0,
            received_at=T0 + timedelta(seconds=1),
            available_at=T0 + timedelta(seconds=1),
            decision_at=T0 + timedelta(seconds=2))
        score = unavailable_score(Horizon.INTRADAY, Direction.UP)
        record = {
            "schema_version": "006B_OFFLINE_STRUCTURAL_PROPOSAL_ONLY",
            "identity": identity.as_dict(),
            "source_times": snapshot.as_dict(),
            "score": score.as_dict(),
            "lifecycle": "RESEARCH_CANDIDATE",
            "reason_codes": ["RESEARCH_ONLY_NOT_QUALIFIED"],
            "full_market_archive_required": False,
            "pit_raw_reproducibility": "NOT_ATTESTED",
            "delivery_authorized": False,
        }
        encoded = json.dumps(record, sort_keys=True, ensure_ascii=True).encode("ascii")
        digest = hashlib.sha256(encoded).hexdigest()
        self.assertEqual(len(digest), 64)
        self.assertIsNone(record["identity"]["signal_id"])
        self.assertIsNone(record["source_times"]["source_publication_time"])
        self.assertEqual(record["score"]["status"], "SCORE_UNAVAILABLE")
        self.assertIsNone(record["score"]["total"])
        self.assertFalse(record["delivery_authorized"])
        self.assertNotIn("market_wire_bytes", record)

    def test_late_input_cannot_be_recorded_as_available_before_decision(self):
        with self.assertRaisesRegex(ValueError, "PIT_SNAPSHOT_FUTURE_OR_INVALID_ORDER"):
            PITDecisionSnapshot(
                source_id="SYNTHETIC:OFFLINE:FIXTURE",
                candle_open_at=T0-timedelta(minutes=30),
                candle_close_at=T0,
                received_at=T0+timedelta(seconds=1),
                available_at=T0+timedelta(seconds=3),
                decision_at=T0+timedelta(seconds=2))

    def test_watch_record_with_invalid_availability_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_OBSERVATION_AVAILABILITY"):
            LifecycleObservation(
                Lifecycle.EARLY_WATCH, "BINANCE:SPOT:BTCUSDT",
                observed_at=T0+timedelta(seconds=2),
                available_at=T0+timedelta(seconds=1),
                reason_codes=("SYNTHETIC_OFFLINE_WATCH",))

    def test_missing_score_never_becomes_probability_or_qualified_signal(self):
        s = unavailable_score(Horizon.SWING, Direction.DOWN).as_dict()
        self.assertEqual(s["status"], "SCORE_UNAVAILABLE")
        self.assertIsNone(s["total"])
        self.assertIsNone(s["probability"])
        self.assertTrue(s["missing_reasons"])

    def test_raw_field_harness_blocks_absent_raw_even_when_functional_shape_exists(self):
        ctx = guard.synthetic_context()
        with self.assertRaisesRegex(guard.FieldBlocked, "SOURCE_NOT_SYNTHETIC"):
            guard.check_synthetic_context(ctx, b"")

    def test_raw_field_harness_blocks_missing_receipt_or_restoration(self):
        for k in ("file_sha256_verified", "restored_raw_verified",
                  "manifest_identity_verified"):
            ctx = guard.synthetic_context()
            ctx["receipt"][k] = False
            with self.subTest(k=k), self.assertRaisesRegex(
                    guard.FieldBlocked, "RECEIPT"):
                guard.check_synthetic_context(ctx, guard.synthetic_fixture())

    def test_synthetic_raw_and_receipt_do_not_authorize_real_pit_or_dispatch(self):
        """Even a positive synthetic fixture has no real market raw/PIT signoff."""
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            ctx = guard.synthetic_context()
            journal = guard.SyntheticJournal(
                Path(tmp) / "guard.jsonl", ctx, guard.synthetic_fixture())
            try:
                state = journal.snapshot()
                self.assertIs(state["permission_to_dispatch"], False)
                self.assertIs(state["real_field_authorized"], False)
                self.assertEqual(state["market_get_executed"], 0)
                self.assertEqual(state["market_ws_connected"], 0)
                self.assertNotIn("PIT_RAW_PASS", state.values())
            finally:
                journal.close()


if __name__ == "__main__":
    unittest.main()
