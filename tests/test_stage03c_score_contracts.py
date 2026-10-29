from __future__ import annotations

import unittest

from zs_smart_gate.stage03c_score_contracts import (
    WEIGHTS, assert_delivery_blocked, detection_event_key, score_v2,
)


class ScoreContractTests(unittest.TestCase):
    def test_weight_tables_sum_to_100(self):
        for horizon in ("INTRADAY", "SWING"):
            with self.subTest(horizon=horizon):
                self.assertEqual(sum(WEIGHTS[horizon].values()), 100)

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
                self.assertEqual(sum(map(float, full.contributions.values())), 100.0)
                self.assertEqual(
                    full.score_kind, "RESEARCH_DISCOVERY_STRENGTH_NOT_PROBABILITY"
                )

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

    def test_delivery_is_blocked_even_with_numeric_research_score(self):
        result = score_v2(
            "INTRADAY",
            {key: 0.5 for key in WEIGHTS["INTRADAY"]},
        )
        with self.assertRaisesRegex(PermissionError, "PHASE_03C_RESEARCH_ONLY"):
            assert_delivery_blocked(result)


if __name__ == "__main__":
    unittest.main()
