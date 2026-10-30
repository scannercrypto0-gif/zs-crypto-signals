"""G0 preflight regression: synthetic only, no network or numeric scoring."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from test_stage03_qualification_readiness import setup
from zs_smart_gate.mtf_contracts import CandleWindow
from zs_smart_gate.stage03a_contracts import (
    Direction, Horizon, ResearchKeyRegistry, SwingPivot,
)
from zs_smart_gate.stage03_offline_scientific_preflight import scientific_g0_preflight


UTC = timezone.utc


def window(frame, start, hours, source="SYNTHETIC:SAME_SOURCE"):
    close = start + timedelta(hours=hours)
    return CandleWindow(
        frame, start, close, close+timedelta(seconds=1),
        close+timedelta(seconds=2), source, "100", "102", "99", "101", "10", "1000")


def contexts(horizon):
    if horizon is Horizon.INTRADAY:
        return {
            "1h": [window("1h", datetime(2026,10,28,7,tzinfo=UTC),1)],
            "4h": [window("4h", datetime(2026,10,28,4,tzinfo=UTC),4)],
        }
    return {
        "1d": [window("1d", datetime(2026,10,27,tzinfo=UTC),24)],
        "1w": [window("1w", datetime(2026,10,19,tzinfo=UTC),168)],
    }


def run(horizon=Horizon.INTRADAY, direction=Direction.UP, **overrides):
    args = {**setup(horizon,direction), "context_windows": contexts(horizon)}
    args.update(overrides)
    return scientific_g0_preflight(**args)


class ScientificG0PreflightTests(TestCase):
    def assert_closed(self, row):
        self.assertEqual(row["scientific_g0"], "NO_GO_PIT_UNVERIFIED")
        self.assertEqual(row["qualification_status"], "NOT_EVALUATED")
        self.assertEqual(row["score_status"], "SCORE_UNAVAILABLE")
        self.assertIsNone(row["score"])
        self.assertIsNone(row["signal_id"])
        self.assertFalse(row["publishable"])
        self.assertFalse(row["delivery_authorized"])
        self.assertIsNone(row["source_publication_time"])
        self.assertIsNone(row["clock_uncertainty_ms"])
        self.assertFalse(row["market_receipt_and_publication_verified"])
        self.assertEqual(row["freshness_policy"], "UNAPPROVED")
        self.assertIn("INDEPENDENT_CLOCK_UNCERTAINTY_UNKNOWN",row["reason_codes"])
        self.assertIn("SOURCE_PUBLICATION_TIME_UNKNOWN",row["reason_codes"])

    def test_valid_synthetic_mtf_both_horizons_directions_but_no_scientific_pit(self):
        for horizon in Horizon:
            for direction in Direction:
                with self.subTest(horizon=horizon.value,direction=direction.value):
                    with patch("urllib.request.urlopen",side_effect=AssertionError("OUTBOUND_FORBIDDEN")), \
                         patch("socket.create_connection",side_effect=AssertionError("OUTBOUND_FORBIDDEN")):
                        result = run(horizon,direction)
                    self.assertEqual(result["code_input_status"],
                                     "SOFTWARE_CONTRACTS_VALID_ON_SYNTHETIC_INPUT")
                    self.assertEqual(result["candidate_status"],"RESEARCH_CANDIDATE")
                    self.assertEqual(set(result["context"]),set(contexts(horizon)))
                    self.assertTrue(all(c["status"]=="CLOSED_AVAILABLE_CONTRACT_ONLY"
                                        for c in result["context"].values()))
                    self.assertEqual(result["structure_status"],"UNVERIFIED_RESEARCH_CONTRACT")
                    self.assert_closed(result)

    def test_context_current_unclosed_or_arriving_after_decision_is_not_usable(self):
        for horizon in Horizon:
            kw=setup(horizon)
            ctx=contexts(horizon)
            frame=next(iter(ctx))
            original=ctx[frame][0]
            for altered in (
                replace(original, available_at=kw["decision_at"]+timedelta(seconds=1)),
                replace(original, received_at=kw["decision_at"]+timedelta(seconds=1),
                        available_at=kw["decision_at"]+timedelta(seconds=2)),
                replace(original, close_at=kw["decision_at"]+timedelta(hours=1)),
            ):
                with self.subTest(horizon=horizon.value,at=altered.available_at):
                    out=run(horizon,context_windows={**ctx,frame:[altered]})
                    self.assertEqual(out["code_input_status"],
                                     "SOFTWARE_INPUTS_INVALID_OR_INCOMPLETE")
                    self.assertIn("CONTEXT_NOT_CLOSED_OR_UNAVAILABLE:"+frame,out["reason_codes"])
                    self.assertEqual(out["context"][frame]["status"],"UNAVAILABLE")
                    self.assert_closed(out)

    def test_last_known_context_used_instead_of_newer_future_bar(self):
        kw=setup(Horizon.INTRADAY)
        ctx=contexts(Horizon.INTRADAY)
        prior=ctx["1h"][0]
        future=window("1h", datetime(2026,10,28,8,tzinfo=UTC),1)
        ctx["1h"]=[prior,future]
        out=run(context_windows=ctx)
        self.assertEqual(out["context"]["1h"]["close_at"],prior.close_at.isoformat())
        self.assertNotEqual(out["context"]["1h"]["close_at"],future.close_at.isoformat())
        self.assertEqual(out["code_input_status"],
                         "SOFTWARE_CONTRACTS_VALID_ON_SYNTHETIC_INPUT")
        self.assert_closed(out)

    def test_missing_invalid_frame_and_mixed_source_fail_closed(self):
        for horizon in Horizon:
            ctx=contexts(horizon)
            frame=next(iter(ctx))
            for modified,marker in (
                ({k:v for k,v in ctx.items() if k!=frame},"MISSING_CONTEXT:"+frame),
                ({**ctx,frame:[replace(ctx[frame][0],source_id="OTHER")]},
                 "CONTEXT_SOURCE_MISMATCH:"+frame),
                ({**ctx,frame:[replace(ctx[frame][0],timeframe="5m")]},
                 "CONTEXT_TIMEFRAME_MISMATCH:"+frame),
            ):
                with self.subTest(horizon=horizon.value,reason=marker):
                    out=run(horizon,context_windows=modified)
                    self.assertIn(marker,out["reason_codes"])
                    self.assertEqual(out["code_input_status"],
                                     "SOFTWARE_INPUTS_INVALID_OR_INCOMPLETE")
                    self.assert_closed(out)
        out=run(context_windows={**contexts(Horizon.INTRADAY),"1d":[]})
        self.assertIn("UNEXPECTED_CONTEXT_FRAME",out["reason_codes"])
        self.assertEqual(out["code_input_status"],"SOFTWARE_INPUTS_INVALID_OR_INCOMPLETE")

    def test_future_pivot_and_mismatched_pivot_source_block_without_bos_claim(self):
        kw=setup(Horizon.SWING)
        pivot=SwingPivot(
            "SYNTHETIC_P", "4h", kw["parent"].open_at,
            kw["decision_at"]+timedelta(seconds=1),
            kw["decision_at"]+timedelta(seconds=2),
            "100", "HIGH", kw["parent"].source_id,
        )
        future=run(Horizon.SWING,pivots=(pivot,))
        self.assertIn("PIVOT_FUTURE_AT_DECISION",future["reason_codes"])
        self.assertEqual(future["code_input_status"],
                         "SOFTWARE_INPUTS_INVALID_OR_INCOMPLETE")
        old=replace(pivot,confirmed_at=kw["parent"].open_at,
                    available_at=kw["parent"].open_at,source_id="OTHER")
        wrong=run(Horizon.SWING,pivots=(old,))
        self.assertIn("PIVOT_SOURCE_MISMATCH",wrong["reason_codes"])
        for row in (future,wrong):
            self.assertEqual(row["structure_status"],"UNVERIFIED_RESEARCH_CONTRACT")
            self.assert_closed(row)

    def test_up_down_and_retry_share_parent_cluster_not_independent_samples(self):
        registry=ResearchKeyRegistry()
        kw=setup(Horizon.INTRADAY)
        a=run(Horizon.INTRADAY,Direction.UP,registry=registry)
        b=run(Horizon.INTRADAY,Direction.UP,registry=registry)
        down=run(Horizon.INTRADAY,Direction.DOWN,registry=registry)
        self.assertEqual(a["parent_window_cluster"],down["parent_window_cluster"])
        self.assertEqual(a["parent_window_cluster"],b["parent_window_cluster"])
        self.assertEqual(a["dedup_status_ephemeral_only"],"NEW_RESEARCH_EVENT")
        self.assertEqual(b["dedup_status_ephemeral_only"],"DUPLICATE_RETRY")
        self.assertEqual(down["dedup_status_ephemeral_only"],"NEW_RESEARCH_EVENT")
        self.assertEqual(a["independence_status"],"UNKNOWN_OUTCOME_OVERLAP_AND_COHORT")
        self.assert_closed(down)

    def test_raw_unapproved_and_missing_parent_stay_unscored(self):
        kw=setup(Horizon.INTRADAY)
        keys={"30M_STRONG_CLOSE":"0.9"}
        row=run(normalized_groups=keys)
        self.assertEqual(row["candidate_status"],"INVALID")
        self.assertIn("NORMALIZATION_INPUT_NOT_APPROVED",row["reason_codes"])
        self.assertEqual(row["code_input_status"],"SOFTWARE_INPUTS_INVALID_OR_INCOMPLETE")
        self.assert_closed(row)
        delayed=replace(kw["parent"], available_at=kw["decision_at"]+timedelta(seconds=1))
        row=run(parent=delayed)
        self.assertEqual(row["candidate_status"],"INVALID")
        self.assertTrue(any("MTF_PARENT_" in code for code in row["reason_codes"]))
        self.assert_closed(row)

    def test_invalid_context_and_pivot_input_types_rejected(self):
        with self.assertRaisesRegex(ValueError,"CONTEXT_WINDOWS_MAPPING_REQUIRED"):
            run(context_windows="not-a-mapping")
        with self.assertRaisesRegex(ValueError,"TYPED_PIVOTS_REQUIRED"):
            run(pivots=(object(),))
        with self.assertRaisesRegex(ValueError,"TYPED_CONTEXT_WINDOWS_REQUIRED"):
            run(context_windows={"1h":["bad"],"4h":[]})


if __name__ == "__main__":
    import unittest
    unittest.main()
