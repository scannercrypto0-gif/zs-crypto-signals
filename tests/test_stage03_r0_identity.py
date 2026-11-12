"""R0 independent identity regressions; Windows-local only, no network."""
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

from zs_smart_gate.stage03_r0_identity import (
    DiscoveryReference, EvaluationIdentity, VERSION,
)
from zs_smart_gate.stage05_contracts import ContractError

CLOSE = datetime(2026, 11, 11, 12, 30, tzinfo=timezone.utc)


class TestR0Identity(unittest.TestCase):
    def test_same_economic_window_is_idempotent_without_a_5m_candidate(self):
        one = EvaluationIdentity("BTCUSDT", CLOSE)
        two = EvaluationIdentity("BTCUSDT", CLOSE)
        self.assertEqual(one, two)
        self.assertEqual(one.as_dict(), two.as_dict())
        self.assertEqual(one.as_dict()["schema"], VERSION)
        self.assertIsNone(one.as_dict()["signal_id"])
        self.assertEqual(one.as_dict()["qualification_state"], "UNKNOWN")

    def test_independent_close_and_bounded_family_make_distinct_ids(self):
        base = EvaluationIdentity("BTCUSDT", CLOSE)
        self.assertNotEqual(base.key, replace(base, parent_close_at=CLOSE+timedelta(minutes=30)).key)
        self.assertNotEqual(base.key, replace(base, discriminator="CONTINUATION_30M").key)
        self.assertNotEqual(base.key, replace(base, symbol="ETHUSDT").key)
        self.assertNotEqual(base.as_dict()["candidate_id"], base.as_dict()["event_id"])
        with self.assertRaises(ContractError):
            replace(base, discriminator="ARBITRARY_RETRY_ID")

    def test_discovery_reference_is_optional_metadata_not_event_identity(self):
        base = EvaluationIdentity("BTCUSDT", CLOSE)
        discovery = DiscoveryReference("NO_BREAKOUT")
        self.assertEqual(discovery.as_dict()["subtype"], "5M_BREAKOUT_SUBTYPE")
        self.assertEqual(base.key, EvaluationIdentity("BTCUSDT", CLOSE).key)
        self.assertNotIn("discovery", base.as_dict())
        with self.assertRaises(ContractError):
            DiscoveryReference("QUALIFIED_SIGNAL")

    def test_identity_is_immutable_and_aligned(self):
        identity = EvaluationIdentity("BTCUSDT", CLOSE)
        with self.assertRaises(FrozenInstanceError):
            identity.symbol = "ETHUSDT"
        with self.assertRaises(ContractError):
            EvaluationIdentity("BTCUSDT", CLOSE-timedelta(minutes=5))
        with self.assertRaises(ContractError):
            EvaluationIdentity("BTCUSD", CLOSE)
        with self.assertRaises(ValueError):
            EvaluationIdentity("BTCUSDT", datetime(2026, 11, 11, 12, 30))
