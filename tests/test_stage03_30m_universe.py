"""Offline Stage03 30m universe coordinator regression tests."""
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch
import unittest

from test_stage03_r1_closed_parent import CLOSE, DECISION, fixture
from zs_smart_gate.stage03_30m_universe import run_closed_30m_research_universe as scan
from zs_smart_gate.stage05_contracts import ContractError


class Stage03ThirtyMinuteUniverseTests(unittest.TestCase):
    def test_twelve_symbols_are_all_evaluated_without_eight_asset_loss(self):
        items=[fixture(symbol="AA%02dUSDT"%i) for i in range(12)]
        with patch("zs_smart_gate.setup021.evaluate",
                   side_effect=AssertionError("FROZEN_5M_SETUP_USED")), \
             patch("socket.create_connection",
                   side_effect=AssertionError("NETWORK_USED")):
            result=scan(tuple(reversed(items)),closed_at=CLOSE,decision_at=DECISION)
        self.assertEqual(result["input_inventory_count"],12)
        self.assertEqual(result["evaluated_count"],12)
        self.assertEqual(len(result["inventory"]),12)
        self.assertEqual(len({x["event_id"] for x in result["inventory"]}),12)
        self.assertFalse(result["complete_exchange_universe_verified"])
        self.assertFalse(result["dispatch_authorized"])
        self.assertTrue(all(row["qualification_state"]=="UNKNOWN"
                            and row["signal_id"] is None for row in result["rows"]))
        self.assertEqual(result,scan(items,closed_at=CLOSE,decision_at=DECISION))

    def test_no_breakout_is_not_a_precondition(self):
        from zs_smart_gate.stage03_r0_identity import DiscoveryReference
        result=scan([fixture(discovery=DiscoveryReference("NO_BREAKOUT"))],
                    closed_at=CLOSE,decision_at=DECISION)
        self.assertEqual(result["rows"][0]["evaluation_status"],"POLICY_HOLD")
        self.assertTrue(result["rows"][0]["raw_30m_evaluation_eligible"])
        self.assertIsNone(result["rows"][0]["signal_id"])

    def test_duplicate_or_wrong_boundary_is_fail_closed(self):
        row=fixture()
        with self.assertRaises(ContractError):
            scan([row,row],closed_at=CLOSE,decision_at=DECISION)
        with self.assertRaises(ContractError):
            scan([row],closed_at=CLOSE-timedelta(minutes=5),decision_at=DECISION)
        with self.assertRaises(ContractError):
            scan([],closed_at=CLOSE,decision_at=DECISION)

    def test_bad_symbol_candle_binding_is_explicit_not_silently_dropped(self):
        row=fixture()
        wrong=replace(row,candle_symbol="ETHUSDT")
        result=scan([wrong],closed_at=CLOSE,decision_at=DECISION)
        self.assertEqual(result["evaluated_count"],1)
        self.assertEqual(result["rows"][0]["evaluation_status"],"INVALID")
        self.assertFalse(result["rows"][0]["raw_30m_evaluation_eligible"])
