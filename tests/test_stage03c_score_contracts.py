from __future__ import annotations

import unittest
from decimal import Decimal
from types import MappingProxyType

from zs_smart_gate.stage03c_score_contracts import (
    SCORE_QUANTUM, SCORE_ROUNDING, VERSION, WEIGHTS,
    assert_delivery_blocked, detection_event_key, score_v2,
)


class ScoreContractTests(unittest.TestCase):
    def test_weight_tables_sum_to_100(self):
        for horizon in ("INTRADAY", "SWING"):
            with self.subTest(horizon=horizon):
                self.assertEqual(sum(WEIGHTS[horizon].values()), 100)

    def test_weight_contract_is_immutable_at_both_levels(self):
        self.assertIsInstance(WEIGHTS, MappingProxyType)
        self.assertIsInstance(WEIGHTS["INTRADAY"], MappingProxyType)
        with self.assertRaises(TypeError):
            WEIGHTS["NEW_HORIZON"] = {}
        with self.assertRaises(TypeError):
            WEIGHTS["INTRADAY"]["strong_close"] = 99
        self.assertEqual(VERSION, "SMART_GATE_V2_SCORE_CONTRACT_0.2")
        self.assertEqual(SCORE_QUANTUM, Decimal("0.01"))
        self.assertEqual(SCORE_ROUNDING, "ROUND_HALF_EVEN")

    def test_missing_group_means_no_partial_score(self):
        for horizon in ("INTRADAY", "SWING"):
            with self.subTest(horizon=horizon):
                result = score_v2(horizon, {})
                self.assertEqual(result.status, "SCORE_UNAVAILABLE")
                self.assertIsNone(result.score)
                self.assertEqual(result.contributions, {})
                self.assertFalse(result.as_dict()["publishable"])
                self.assertEqual(result.as_dict()["qualification_status"], "NOT_EVALUATED")

    def test_complete_zero_and_one_features_are_bounded(self):
        for horizon in ("INTRADAY", "SWING"):
            with self.subTest(horizon=horizon):
                weights = WEIGHTS[horizon]
                zero = score_v2(horizon, {key: 0 for key in weights})
                full = score_v2(horizon, {key: 1 for key in weights})
                self.assertEqual(zero.score, "0.00")
                self.assertEqual(full.score, "100.00")
                self.assertEqual(sum(map(Decimal, full.contributions.values())), Decimal("100"))
                self.assertEqual(
                    full.score_kind, "RESEARCH_DISCOVERY_STRENGTH_NOT_PROBABILITY"
                )

    def test_exact_contributions_are_summed_before_final_rounding(self):
        values = {key: "0.3333" for key in WEIGHTS["INTRADAY"]}
        result = score_v2("INTRADAY", values)
        self.assertEqual(result.score, "33.33")
        self.assertEqual(result.contributions["strong_close"], "6.666")
        self.assertEqual(result.contributions["mtf_structure"], "4.9995")
        self.assertEqual(result.contributions["liquidity"], "1.6665")

    def test_invalid_feature_values_are_rejected(self):
        for bad in (-0.01, 1.01, float("nan"), float("inf"), True, "oops"):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    score_v2(
                        "INTRADAY",
                        {key: bad for key in WEIGHTS["INTRADAY"]},
                    )

    def test_extra_group_rejected_to_prevent_silent_weight_drift(self):
        values = {key: 0.5 for key in WEIGHTS["SWING"]}
        values["rsi"] = 0.9
        with self.assertRaisesRegex(ValueError, "UNEXPECTED_FEATURE_GROUPS"):
            score_v2("SWING", values)

    def test_event_identity_is_deterministic_and_sensitive_to_event_dimensions(self):
        args = dict(
            rule_version="v1",
            market="BINANCE:SPOT",
            symbol="BTCUSDT",
            direction="UP",
            horizon="INTRADAY",
            setup_type="CONTINUATION",
            decision_close_utc="2026-10-30T12:30:00Z",
        )
        self.assertEqual(detection_event_key(**args), detection_event_key(**args))
        self.assertNotEqual(
            detection_event_key(**args),
            detection_event_key(**{**args, "direction": "DOWN"}),
        )
        self.assertNotEqual(
            detection_event_key(**args),
            detection_event_key(**{**args, "symbol": "ETHUSDT"}),
        )

    def test_equivalent_timestamp_offsets_share_canonical_event_key(self):
        utc_args = dict(
            rule_version="v1", market="BINANCE:SPOT", symbol="BTCUSDT",
            direction="UP", horizon="INTRADAY", setup_type="CONTINUATION",
            decision_close_utc="2026-10-30T12:30:00Z",
        )
        offset_args = {
            **utc_args,
            "decision_close_utc": "2026-10-30T15:30:00+03:00",
        }
        self.assertEqual(
            detection_event_key(**utc_args), detection_event_key(**offset_args)
        )

    def test_event_timestamp_must_be_valid_and_timezone_aware(self):
        args = dict(
            rule_version="v1", market="BINANCE:SPOT", symbol="BTCUSDT",
            direction="UP", horizon="INTRADAY", setup_type="CONTINUATION",
            decision_close_utc="2026-10-30T12:30:00Z",
        )
        for invalid in (
            "2026-10-30T12:30:00", "2026-02-30T12:30:00Z",
            "not-a-timestamp", "2026-10-30 12:30:00Z",
        ):
            with self.subTest(timestamp=invalid):
                with self.assertRaisesRegex(ValueError, "INVALID_DECISION_TIMESTAMP"):
                    detection_event_key(**{**args, "decision_close_utc": invalid})

    def test_delivery_is_blocked_even_with_numeric_research_score(self):
        result = score_v2(
            "INTRADAY",
            {key: 0.5 for key in WEIGHTS["INTRADAY"]},
        )
        with self.assertRaisesRegex(PermissionError, "PHASE_03C_RESEARCH_ONLY"):
            assert_delivery_blocked(result)


if __name__ == "__main__":
    unittest.main()
