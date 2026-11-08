"""Regression for R2 cross-feed context isolation; synthetic and offline only."""
from dataclasses import replace
from unittest import TestCase

from test_stage03_r2_offline import intraday, swing
from zs_smart_gate.stage03_r2_offline import evaluate_r2


class R2ContextSourceGuardTests(TestCase):
    def test_intraday_mixed_1h_source_blocks_n05_not_parent_arithmetic(self):
        inputs = intraday()
        context = dict(inputs["context"])
        bars = list(context["1h"])
        bars[-1] = replace(bars[-1], source_id="SYNTHETIC:FOREIGN_1H")
        context["1h"] = tuple(bars)
        inputs["context"] = context

        result = evaluate_r2(**inputs)
        self.assertEqual(result["status"], "DEV_CANDIDATE")
        self.assertIsNone(result["normalizers"]["MTF_NEARBY_STRUCTURE"])
        self.assertEqual(
            result["missing_reasons"]["MTF_NEARBY_STRUCTURE"],
            "CONTEXT_SOURCE_MISMATCH:1h",
        )
        self.assertIsNotNone(result["normalizers"]["30M_STRONG_CLOSE"])
        self.assertFalse(result["publishable"])
        self.assertIsNone(result["signal_id"])

    def test_swing_mixed_weekly_source_blocks_n10_not_parent_arithmetic(self):
        inputs = swing()
        context = dict(inputs["context"])
        bars = list(context["1w"])
        bars[0] = replace(bars[0], source_id="SYNTHETIC:FOREIGN_1W")
        context["1w"] = tuple(bars)
        inputs["context"] = context

        result = evaluate_r2(**inputs)
        self.assertEqual(result["status"], "DEV_CANDIDATE")
        self.assertIsNone(result["normalizers"]["DAILY_WEEKLY_CONTEXT"])
        self.assertEqual(
            result["missing_reasons"]["DAILY_WEEKLY_CONTEXT"],
            "CONTEXT_SOURCE_MISMATCH:1w",
        )
        self.assertIsNotNone(result["normalizers"]["FOUR_H_STRONG_CLOSE"])
        self.assertEqual(result["score_status"], "SCORE_UNAVAILABLE")

    def test_swing_mixed_structure_source_blocks_n07_before_pivot_math(self):
        inputs = swing()
        context = dict(inputs["context"])
        bars = list(context["structure4h"])
        bars[5] = replace(bars[5], source_id="SYNTHETIC:FOREIGN_4H")
        context["structure4h"] = tuple(bars)
        inputs["context"] = context

        result = evaluate_r2(**inputs)
        self.assertIsNone(result["normalizers"]["MARKET_STRUCTURE"])
        self.assertEqual(
            result["missing_reasons"]["MARKET_STRUCTURE"],
            "CONTEXT_SOURCE_MISMATCH:structure4h",
        )
        self.assertFalse(result["structural_event"])
        self.assertFalse(result["publishable"])
