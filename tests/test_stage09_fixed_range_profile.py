"""Stage09 deterministic contracts; offline synthetic fixtures only."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from unittest import TestCase

from zs_smart_gate.mtf_contracts import CandleWindow
from zs_smart_gate.stage09_fixed_range_profile import (
    ProfileWindow, TradePrint, SyntheticTradeCoverage, ResearchHypothesis,
    evaluate_profile, retrospective_profile_observation, synthetic_ablation,
    _coverage_digest, _completed_week,
)
from zs_smart_gate.stage05_contracts import ContractError

UTC = timezone.utc
T = datetime(2026, 11, 16, 0, tzinfo=UTC)  # Monday
SOURCE = "SYNTHETIC:S09"


def bar(frame="1h", start=T, *, op="100", hi="102", lo="100", close="101",
        base="12", quote="1212", source=SOURCE):
    from zs_smart_gate.mtf_contracts import DURATIONS
    end = start + DURATIONS[frame]
    return CandleWindow(frame, start, end, end+timedelta(seconds=1),
        end+timedelta(seconds=2), source, D(op), D(hi), D(lo),
        D(close), D(base), D(quote))


def sample(**kw):
    values = dict(symbol="BTCUSDT", direction="UP", kind="1h",
        anchor_at=T, bars=(bar(),), bin_size=D("1"),
        source_manifest_sha256="a"*64)
    values.update(kw)
    return ProfileWindow(**values)


def run(w):
    latest = (*w.bars, *w.reaction)[-1]
    return evaluate_profile(w, decision_at=latest.available_at)


def full_trades():
    t1 = TradePrint(10, T+timedelta(minutes=1),
        T+timedelta(minutes=1, seconds=1),
        T+timedelta(minutes=1, seconds=2), SOURCE, D("100"), D("1"))
    t2 = TradePrint(11, T+timedelta(minutes=59),
        T+timedelta(minutes=59, seconds=1),
        T+timedelta(minutes=59, seconds=2), SOURCE, D("102"), D("1"))
    ts = (t1, t2)
    coverage = SyntheticTradeCoverage(
        SOURCE, T, T+timedelta(hours=1), 10, 11, 2,
        _coverage_digest(ts), True)
    return sample(method="EXACT_SYNTHETIC_TRADES", trades=ts,
        trade_coverage=coverage, bars=(bar(
            op="100", hi="102", lo="100", close="102", base="2", quote="202"),))


class Stage09Tests(TestCase):
    def test_approx_poc_tie_and_vwap_reference(self):
        row = run(sample())
        self.assertEqual(row["status"], "RESEARCH_MEASURED")
        self.assertEqual(row["features"]["poc"], "100.5")
        self.assertEqual(row["features"]["vwap"], "101")
        self.assertEqual(row["features"]["bin_volumes"], [[100,"6"],[101,"6"]])
        self.assertEqual(row["binning"]["poc_tie"], "LOWEST_BIN")
        self.assertIsNone(row["signal_id"])
        self.assertFalse(row["trade_ready"])
        self.assertEqual(row, run(sample()))

    def test_approx_is_not_marked_exact(self):
        r = run(sample())
        self.assertEqual(r["method"], "APPROX_OHLCV")
        self.assertIn("APPROX", r["precision_label"])
        self.assertIn("NOT_INDEPENDENT", r["source_trust"])

    def test_value_area_optional_and_contiguous(self):
        self.assertEqual(run(sample())["features"]["value_area"]["status"],
                         "NOT_REQUESTED")
        r = run(sample(value_area_fraction=D("0.7")))
        a = r["features"]["value_area"]
        self.assertEqual((a["val"],a["vah"]), ("100","102"))
        self.assertEqual(a["bin_count"], 2)
        self.assertEqual(a["status"], "PRESENT")
        self.assertEqual(run(sample(value_area_fraction=D("0")))["status"], "UNAVAILABLE")

    def test_ohlcv_high_exact_boundary_and_single_price_bin(self):
        point = bar(op="101", hi="101", lo="101", close="101",
                    base="5", quote="505")
        r = run(sample(bars=(point,)))
        self.assertEqual(r["features"]["bin_volumes"], [[101, "5"]])
        self.assertEqual(r["features"]["poc"], "101.5")

    def test_deterministic_price_origin(self):
        r = run(sample(price_origin=D("0.5")))
        self.assertEqual(r["features"]["poc"], "100.0")
        self.assertEqual(r["binning"]["origin"], "0.5")

    def test_signed_absolute_distances_both_directions(self):
        for direction in ("UP", "DOWN"):
            r = run(sample(direction=direction))
            self.assertEqual(r["features"]["poc_distance"]["signed_price"], "0.5")
            self.assertEqual(r["features"]["poc_distance"]["absolute_price"], "0.5")
            self.assertEqual(r["direction"], direction)
        self.assertNotEqual(run(sample(direction="UP"))["event_id"],
                            run(sample(direction="DOWN"))["event_id"])

    def test_gap_duplicate_and_out_of_order_fail(self):
        b1 = bar()
        b2 = bar(start=T+timedelta(hours=2))
        self.assertEqual(run(sample(bars=(b1,b2)))["status"], "UNAVAILABLE")
        self.assertEqual(run(sample(bars=(b1,b1)))["status"], "UNAVAILABLE")
        self.assertEqual(run(sample(bars=(b2,b1)))["status"], "UNAVAILABLE")

    def test_source_mismatch_and_late_receipt(self):
        b1 = bar()
        self.assertEqual(run(sample(bars=(replace(b1,source_id="SYNTHETIC:BAD"),)))["status"],
                         "RESEARCH_MEASURED")
        # All supplied source labels are internally consistent, but still synthetic.
        late = replace(b1, available_at=b1.available_at+timedelta(hours=1))
        self.assertEqual(evaluate_profile(sample(bars=(late,)),
            decision_at=b1.available_at)["status"], "UNAVAILABLE")
        other = bar(start=T+timedelta(hours=1),source="SYNTHETIC:OTHER")
        self.assertEqual(run(sample(bars=(b1,other)))["status"], "UNAVAILABLE")

    def test_invalid_ohlcv_and_nan_construction(self):
        with self.assertRaises(ValueError):
            bar(hi="NaN")
        with self.assertRaises(ValueError):
            bar(lo="104", hi="102")
        self.assertEqual(run(sample(bars=(bar(base="0"),)))["status"], "UNAVAILABLE")
        self.assertEqual(run(sample(source_manifest_sha256="invalid"))["status"], "UNAVAILABLE")
        self.assertEqual(run(sample(bin_size=D("0")))["status"], "UNAVAILABLE")

    def test_1h_4h_and_daily_profile_kinds(self):
        cases = (("1h",T),("4h",T),("DAILY",T))
        for kind, when in cases:
            frame = {"1h":"1h","4h":"4h","DAILY":"1d"}[kind]
            b = bar(frame, when)
            r = run(sample(kind=kind, anchor_at=when, bars=(b,)))
            self.assertEqual(r["status"], "RESEARCH_MEASURED")
            self.assertEqual(r["kind"], kind)

    def test_previous_completed_week_is_not_developing_week(self):
        previous = bar("1w", T-timedelta(weeks=1))
        r = evaluate_profile(sample(kind="PREVIOUS_COMPLETED_WEEK",
            anchor_at=previous.open_at, bars=(previous,)), decision_at=T+timedelta(hours=2))
        self.assertEqual(r["status"], "RESEARCH_MEASURED")
        developing = bar("1w",T)
        bad = evaluate_profile(sample(kind="PREVIOUS_COMPLETED_WEEK",
            anchor_at=T, bars=(developing,)), decision_at=T+timedelta(hours=2))
        self.assertEqual(bad["status"], "UNAVAILABLE")
        self.assertEqual(bad["reason_codes"][0], "PROFILE_BAR_TIME_OR_OHLCV_INVALID:FUTURE_OR_UNAVAILABLE_AT_DECISION")

    def test_weekly_utc_monday_rollover_and_tz(self):
        ksa = (T+timedelta(hours=2)).astimezone(timezone(timedelta(hours=3)))
        self.assertEqual(_completed_week(ksa),
                         (T-timedelta(weeks=1),T))
        prev = bar("1w",T-timedelta(weeks=1))
        a = evaluate_profile(sample(kind="PREVIOUS_COMPLETED_WEEK",
            anchor_at=prev.open_at,bars=(prev,)),decision_at=ksa)
        b = evaluate_profile(sample(kind="PREVIOUS_COMPLETED_WEEK",
            anchor_at=prev.open_at,bars=(prev,)),decision_at=T+timedelta(hours=2))
        self.assertEqual(a,b)

    def test_exact_synthetic_prints_reference_and_poc(self):
        r = run(full_trades())
        self.assertEqual(r["status"], "RESEARCH_MEASURED")
        self.assertEqual(r["features"]["poc"], "100.5")
        self.assertEqual(r["features"]["vwap"], "101")
        self.assertEqual(r["features"]["bin_volumes"], [[100,"1"],[102,"1"]])
        self.assertEqual(r["coverage"]["status"], "SYNTHETIC_FIXTURE_ATTESTED")
        self.assertIn("NOT_VERIFIED_EXCHANGE", r["precision_label"])

    def test_exact_requires_valid_coverage_attestation_and_digest(self):
        w = full_trades()
        self.assertEqual(run(replace(w,trade_coverage=None))["status"], "UNAVAILABLE")
        self.assertEqual(run(replace(w,trade_coverage=replace(
            w.trade_coverage,complete_attested=False)))["status"], "UNAVAILABLE")
        self.assertEqual(run(replace(w,trade_coverage=replace(
            w.trade_coverage,trade_digest_sha256="b"*64)))["status"], "UNAVAILABLE")

    def test_exact_rejects_missing_or_duplicate_trade_ids(self):
        w = full_trades()
        swapped = replace(w.trades[1], trade_id=13)
        self.assertEqual(run(replace(w,trades=(w.trades[0],swapped)))["status"], "UNAVAILABLE")
        duplicate = replace(w.trades[1], trade_id=10)
        self.assertEqual(run(replace(w,trades=(w.trades[0],duplicate)))["status"], "UNAVAILABLE")

    def test_exact_ohlcv_reconciliation_fail_closed(self):
        w = full_trades()
        mismatch = replace(w.bars[0], quote_volume=D("999"))
        self.assertEqual(run(replace(w,bars=(mismatch,)))["status"], "UNAVAILABLE")
        mismatch2 = replace(w.bars[0], high=D("105"))
        self.assertEqual(run(replace(w,bars=(mismatch2,)))["status"], "UNAVAILABLE")

    def test_exact_source_time_mismatch_fail_closed(self):
        w = full_trades()
        foreign = replace(w.trades[1],source_id="SYNTHETIC:FOREIGN")
        self.assertEqual(run(replace(w,trades=(w.trades[0],foreign)))["status"], "UNAVAILABLE")
        delayed = replace(w.trades[1], available_at=w.bars[0].available_at+timedelta(seconds=10))
        self.assertEqual(run(replace(w,trades=(w.trades[0],delayed)))["status"], "UNAVAILABLE")

    def test_approx_cannot_accept_exact_trade_input(self):
        w = full_trades()
        result = run(replace(w,method="APPROX_OHLCV"))
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["reason_codes"], ["APPROX_TRADES_MUST_BE_ABSENT"])

    def test_reaction_after_reference_cannot_straddle(self):
        first = bar(start=T+timedelta(hours=1))
        result = run(sample(reaction=(first,)))
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["reason_codes"], ["REACTION_STRADDLES_REFERENCE_AVAILABILITY"])

    def test_cross_retest_hold_rejection_after_reference(self):
        ref = bar(close="100")
        r1 = bar(start=T+timedelta(hours=2), op="100", hi="102", lo="100", close="102")
        r2 = bar(start=T+timedelta(hours=3), op="102", hi="103", lo="100.4", close="101")
        r3 = bar(start=T+timedelta(hours=4), op="101", hi="101.5", lo="99", close="99")
        record = run(sample(bars=(ref,),reaction=(r1,r2,r3)))
        self.assertEqual(record["status"], "RESEARCH_MEASURED")
        x = record["features"]["reaction_to_frozen_poc"]
        self.assertEqual(x["cross_count"], 1)
        self.assertEqual(x["retest_count"], 1)
        self.assertGreaterEqual(x["hold_consecutive_pairs"], 1)
        self.assertEqual(x["rejection_count"], 1)
        self.assertIsNotNone(x["seconds_since_last_cross_available"])

    def test_down_reaction_symmetric(self):
        ref = bar(close="101")
        r1 = bar(start=T+timedelta(hours=2), op="101",hi="102",lo="99",close="99")
        r2 = bar(start=T+timedelta(hours=3), op="99",hi="101",lo="98",close="99.5")
        r3 = bar(start=T+timedelta(hours=4), op="99.5",hi="102",lo="99",close="102")
        record = run(sample(direction="DOWN",bars=(ref,),reaction=(r1,r2,r3)))
        x = record["features"]["reaction_to_frozen_poc"]
        self.assertEqual(x["cross_count"], 1)
        self.assertEqual(x["retest_count"], 1)
        self.assertEqual(x["rejection_count"], 1)

    def test_hypothesis_levels_costs_and_structure_are_only_research(self):
        h = ResearchHypothesis("UP",D("101"),D("99"),D("105"),
            D("5"),D("3"),D("100"),T, SOURCE)
        r = run(sample(hypothesis=h))
        self.assertEqual(r["status"], "RESEARCH_MEASURED")
        self.assertEqual(r["hypothesis"]["gross_reward_to_risk"], "2")
        self.assertEqual(r["hypothesis"]["roundtrip_assumed_cost_bps"], "16")
        self.assertFalse(r["hypothesis"]["trade_ready"])
        self.assertFalse(r["trade_ready"])

    def test_hypothesis_bad_order_future_structure_cost_fail_closed(self):
        h = ResearchHypothesis("UP",D("101"),D("102"),D("105"),D("5"),D("3"))
        self.assertEqual(run(sample(hypothesis=h))["status"], "UNAVAILABLE")
        h2 = ResearchHypothesis("UP",D("101"),D("99"),D("105"),
            D("-1"),D("3"))
        self.assertEqual(run(sample(hypothesis=h2))["status"], "UNAVAILABLE")
        h3 = ResearchHypothesis("UP",D("101"),D("99"),D("105"),
            D("5"),D("3"),D("100"),T+timedelta(days=1),SOURCE)
        self.assertEqual(run(sample(hypothesis=h3))["status"], "UNAVAILABLE")

    def test_retro_future_mutation_does_not_change_features(self):
        w = sample()
        record = run(w)
        first_at = T+timedelta(hours=2)  # next complete 1h after 01:00:02 decision
        b = bar(start=first_at,close="101")
        later = replace(b, close=D("102"))
        result1 = retrospective_profile_observation(
            record,(b,),as_of=b.available_at)
        result2 = retrospective_profile_observation(
            record,(later,),as_of=later.available_at)
        self.assertNotEqual(result1["last_close_minus_frozen_poc"],
                            result2["last_close_minus_frozen_poc"])
        self.assertEqual(record,run(w))
        self.assertFalse(result1["is_trade"])

    def test_retro_gaps_and_unavailable_bar(self):
        record = run(sample())
        skipped = bar(start=T+timedelta(hours=3))
        x = retrospective_profile_observation(record,(skipped,),as_of=skipped.available_at)
        self.assertEqual(x["status"],"CENSORED_GAP")
        self.assertIsNone(x["last_close_minus_frozen_poc"])
        early = bar(start=T+timedelta(hours=1))
        with self.assertRaises(ContractError):
            retrospective_profile_observation(record,(early,),as_of=early.available_at)

    def test_retro_foreign_source_and_tampered_receipt_rejected(self):
        record = run(sample())
        first = bar(start=T+timedelta(hours=2),source="SYNTHETIC:OTHER")
        with self.assertRaises(ContractError):
            retrospective_profile_observation(record,(first,),as_of=first.available_at)
        with self.assertRaises(ContractError):
            retrospective_profile_observation(dict(record,signal_id="fake"),(),as_of=T+timedelta(hours=3))

    def test_synthetic_ablation_price_only_poc_and_vwap(self):
        a = run(sample())
        b = run(sample(direction="DOWN"))
        report = synthetic_ablation([a,b])
        self.assertEqual(report["sample_count"], 2)
        self.assertEqual(report["variants"]["price_only"]["up"], 2)
        self.assertEqual(report["variants"]["with_poc_without_vwap"]["up"], 2)
        self.assertIsNone(report["prediction_accuracy"])
        self.assertEqual(report["scientific_validity"],"DESCRIPTIVE_ONLY_NOT_OOS")
        with self.assertRaises(ContractError):
            synthetic_ablation([dict(a, score=2)])

    def test_time_zone_decision_normalization(self):
        w = sample()
        decision = w.bars[-1].available_at
        offset = decision.astimezone(timezone(timedelta(hours=3)))
        self.assertEqual(evaluate_profile(w,decision_at=decision),
                         evaluate_profile(w,decision_at=offset))
