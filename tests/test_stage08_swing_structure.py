"""Stage08 source/time and nonrepainting structure tests, synthetic offline only."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from unittest import TestCase

from zs_smart_gate.mtf_contracts import CandleWindow
from zs_smart_gate.stage08_swing_structure import (
    EightHourObservation, SwingWindow, analyze_swing,
    retrospective_swing_observation, compare_synthetic_structure, _pivots_and_breaks,
)
from zs_smart_gate.stage05_contracts import ContractError

UTC = timezone.utc
START = datetime(2026, 11, 2, tzinfo=UTC)  # Monday UTC
SOURCE = "SYNTHETIC:STAGE08"


def candle(frame, at, hours, opening, closing, *, source=SOURCE,
           high=None, low=None, base=D("10")):
    opening, closing = D(str(opening)), D(str(closing))
    high = D(str(high)) if high is not None else max(opening, closing)+D("0.5")
    low = D(str(low)) if low is not None else min(opening, closing)-D("0.5")
    end = at + timedelta(hours=hours)
    return CandleWindow(frame, at, end, end+timedelta(seconds=1),
                        end+timedelta(seconds=2), source,
                        opening, high, low, closing, base, base*D("100"))


def fixture(direction="UP", *, history_count=13, with_eight=False,
            daily=(), weekly=()):
    history = tuple(candle("4h", START+timedelta(hours=4*i), 4,
                           100, 100+((i*3)%11)-5)
                    for i in range(history_count))
    parent_at = START+timedelta(hours=4*history_count)
    sign = D("1") if direction == "UP" else D("-1")
    children = tuple(candle("1h", parent_at+timedelta(hours=i), 1,
                            100+sign*D(i), 100+sign*D(i+1),
                            base=D("5")) for i in range(4))
    parent = CandleWindow("4h", parent_at, parent_at+timedelta(hours=4),
        parent_at+timedelta(hours=4, seconds=1),
        parent_at+timedelta(hours=4, seconds=2), SOURCE,
        children[0].open, max(b.high for b in children),
        min(b.low for b in children), children[-1].close,
        sum((b.base_volume for b in children), D("0")),
        sum((b.quote_volume for b in children), D("0")))
    eight = None
    if with_eight:
        before = history[-1]
        eight = EightHourObservation(
            before.open_at, parent.close_at,
            parent.close_at+timedelta(seconds=1),
            parent.close_at+timedelta(seconds=2),
            SOURCE, before.open, max(before.high, parent.high),
            min(before.low, parent.low), parent.close,
            before.base_volume+parent.base_volume,
            before.quote_volume+parent.quote_volume)
    return SwingWindow("BTCUSDT", direction, parent, children, history,
                       eight, tuple(daily), tuple(weekly), "a"*64)


def run(w):
    return analyze_swing(w, decision_at=w.parent_4h.available_at)


def series_of_extrema(highs, lows):
    return tuple(candle("4h", START+timedelta(hours=4*i), 4,
                        100, 100, high=hi, low=lo) for i, (hi, lo)
                 in enumerate(zip(highs, lows)))


class Stage08SwingTests(TestCase):
    def test_full_bundle_up_down_no_authority(self):
        for side in ("UP", "DOWN"):
            w = fixture(side)
            r = run(w)
            self.assertEqual(r["status"], "RESEARCH_MEASURED")
            self.assertIsNone(r["signal_id"])
            self.assertIsNone(r["score"])
            self.assertFalse(r["dispatch_allowed"])
            self.assertEqual(run(w), r)
            self.assertEqual(r["direction"], side)
        self.assertNotEqual(run(fixture("UP"))["event_id"],
                            run(fixture("DOWN"))["event_id"])

    def test_source_mismatch_and_future_receipt_fail_closed(self):
        w = fixture()
        broken = replace(w.children_1h[1], source_id="SYNTHETIC:OTHER")
        self.assertEqual(run(replace(w, children_1h=(
            w.children_1h[0], broken, *w.children_1h[2:])))["status"], "UNAVAILABLE")
        late = replace(w.parent_4h, available_at=w.parent_4h.available_at+timedelta(seconds=5))
        self.assertEqual(analyze_swing(replace(w, parent_4h=late),
                                      decision_at=w.parent_4h.available_at)["status"], "UNAVAILABLE")
        self.assertEqual(run(replace(w, source_scope="APPROVED_REAL_SOURCE"))["status"],
                         "UNAVAILABLE")

    def test_gap_duplicates_order_and_reconciliation(self):
        w = fixture()
        self.assertEqual(run(replace(w, children_1h=tuple(reversed(w.children_1h))))["status"],
                         "UNAVAILABLE")
        duplicated = (*w.children_1h[:3], w.children_1h[2])
        self.assertEqual(run(replace(w, children_1h=duplicated))["status"], "UNAVAILABLE")
        changed = replace(w.parent_4h, quote_volume=w.parent_4h.quote_volume+D("1"))
        self.assertEqual(run(replace(w, parent_4h=changed))["status"], "UNAVAILABLE")
        self.assertEqual(run(replace(w, history_4h=w.history_4h[:-1]))["status"],
                         "UNAVAILABLE")

    def test_utc_alignment_and_missing_history(self):
        w = fixture()
        shifted = replace(w.children_1h[0],
            open_at=w.children_1h[0].open_at+timedelta(minutes=15),
            close_at=w.children_1h[0].close_at+timedelta(minutes=15),
            received_at=w.children_1h[0].received_at+timedelta(minutes=15),
            available_at=w.children_1h[0].available_at+timedelta(minutes=15))
        self.assertEqual(run(replace(w, children_1h=(shifted, *w.children_1h[1:])))[
                         "status"], "UNAVAILABLE")
        short = fixture(history_count=0)
        self.assertEqual(run(short)["structure"]["status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(run(short)["features"]["ema26_4h"]["status"], "INSUFFICIENT_HISTORY")

    def test_8h_optional_absent_and_reconciliation(self):
        self.assertEqual(run(fixture())["comparison_8h"]["status"], "UNAVAILABLE")
        w = fixture(with_eight=True)
        self.assertEqual(run(w)["comparison_8h"]["status"], "PRESENT")
        bad = replace(w.comparison_8h, high=w.comparison_8h.high+D("0.1"))
        self.assertEqual(run(replace(w, comparison_8h=bad))["status"], "UNAVAILABLE")
        bad_source = replace(w.comparison_8h, source_id="SYNTHETIC:DIFFERENT")
        self.assertEqual(run(replace(w, comparison_8h=bad_source))["status"], "UNAVAILABLE")

    def test_8h_non_aligned_parent_rejected(self):
        w = fixture(history_count=12)
        previous = w.history_4h[-1]
        pair = EightHourObservation(previous.open_at, w.parent_4h.close_at,
            w.parent_4h.received_at, w.parent_4h.available_at,
            SOURCE, previous.open, max(previous.high,w.parent_4h.high),
            min(previous.low,w.parent_4h.low), w.parent_4h.close,
            previous.base_volume+w.parent_4h.base_volume,
            previous.quote_volume+w.parent_4h.quote_volume)
        self.assertEqual(run(replace(w, comparison_8h=pair))["status"], "UNAVAILABLE")

    def test_strict_pivot_confirmation_right_two_and_delayed_availability(self):
        bars = series_of_extrema([101,102,106,103,101], [99,98,95,98,99])
        early = _pivots_and_breaks(bars[:4])
        self.assertFalse(early["confirmed_pivots"])
        confirmed = _pivots_and_breaks(bars)
        highs = [x for x in confirmed["confirmed_pivots"] if x["kind"] == "HIGH"]
        self.assertEqual(len(highs),1)
        self.assertEqual(highs[0]["confirmation_close_at"], bars[4].close_at.isoformat().replace("+00:00","Z"))
        self.assertEqual(highs[0]["first_available_at"],
                         bars[4].available_at.isoformat().replace("+00:00","Z"))

    def test_tie_rejects_equal_high_low(self):
        bars = series_of_extrema([101,106,106,103,101], [99,95,95,98,99])
        result = _pivots_and_breaks(bars)
        self.assertEqual(result["confirmed_pivots"], [])
        self.assertGreater(result["tie_rejections"], 0)

    def test_wick_only_then_close_initial_then_choch_down(self):
        prefix = series_of_extrema([101,102,106,103,101], [99,98,95,98,99])
        wick = candle("4h", START+timedelta(hours=20), 4, 100, 100, high=108, low=98)
        up = candle("4h", START+timedelta(hours=24), 4, 100, 107, high=108, low=99)
        down = candle("4h", START+timedelta(hours=28), 4, 107, 94, high=108, low=93)
        a = _pivots_and_breaks((*prefix, wick))
        self.assertEqual(a["latest_wick_only"]["status"], "WICK_ONLY")
        self.assertFalse(a["close_breaks"])
        b = _pivots_and_breaks((*prefix, wick, up, down))
        self.assertEqual(b["close_breaks"][0]["kind"], "INITIAL_BREAK")
        self.assertEqual(b["close_breaks"][0]["side"], "UP")
        self.assertEqual(b["close_breaks"][1]["kind"], "CHoCH")
        self.assertEqual(b["close_breaks"][1]["side"], "DOWN")

    def test_nonrepainting_confirmation_and_future_mutation(self):
        b = series_of_extrema([101,102,106,103,101,102], [99,98,95,98,99,98])
        frozen = _pivots_and_breaks(b[:5])["confirmed_pivots"]
        later = replace(b[5], high=D("120"), low=D("80"))
        updated = _pivots_and_breaks((*b[:5], later))["confirmed_pivots"]
        self.assertEqual(updated[:len(frozen)], frozen)
        w = fixture()
        before = run(w)
        # Later observations are not a feature input: no retroactive reclassification.
        self.assertEqual(run(w), before)

    def test_indicator_minimum_history_and_ema_rsi_macd(self):
        short = run(fixture())
        self.assertEqual(short["features"]["ema12_4h"]["status"], "PRESENT")
        self.assertEqual(short["features"]["ema26_4h"]["status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(short["features"]["rsi14_4h"]["status"], "INSUFFICIENT_HISTORY")
        longer = run(fixture(history_count=35))
        for k in ("ema12_4h","ema26_4h","rsi14_4h",
                  "macd_12_26_9_line","macd_12_26_9_signal"):
            self.assertEqual(longer["features"][k]["status"], "PRESENT")
        self.assertEqual(longer["features"]["ma50_week_close"]["status"],
                         "INSUFFICIENT_HISTORY")

    def test_weekly_50_not_reconstructed_from_4h(self):
        end = START
        weekly = tuple(candle("1w", end-timedelta(weeks=50-i), 24*7, 100, 100)
                       for i in range(50))
        w = fixture(weekly=weekly)
        r = run(w)
        self.assertEqual(r["features"]["ma50_week_close"]["value"], "100")
        self.assertEqual(r["features"]["latest_1w_close"]["status"], "PRESENT")
        self.assertEqual(run(fixture())["features"]["ma50_week_close"]["status"],
                         "INSUFFICIENT_HISTORY")

    def test_daily_and_weekly_context_not_inferred(self):
        w = fixture()
        r = run(w)
        self.assertEqual(r["timeframe_context"]["4h_vs_last_daily_close"], "UNKNOWN")
        self.assertEqual(r["timeframe_context"]["4h_vs_last_weekly_close"], "UNKNOWN")
        d = candle("1d", START, 24, 100, 101)
        self.assertEqual(run(replace(w, daily=(d,)))["features"]["latest_1d_close"]["status"],
                         "PRESENT")
        late = replace(d, available_at=w.parent_4h.available_at+timedelta(seconds=1))
        self.assertEqual(run(replace(w, daily=(late,)))["status"], "UNAVAILABLE")

    def test_outcome_separate_future_source_and_no_trade(self):
        w = fixture()
        r = run(w)
        later = w.parent_4h.close_at+timedelta(hours=4)
        b = candle("4h", later, 4, 105, 107)
        o = retrospective_swing_observation(r, (b,), as_of=b.available_at)
        self.assertEqual(o["status"], "OBSERVED")
        self.assertFalse(o["is_trade"])
        self.assertEqual(o["research_sha256"], r["result_sha256"])
        self.assertEqual(r, run(w))
        with self.assertRaises(ContractError):
            retrospective_swing_observation(r, (replace(b, source_id="SYNTHETIC:FOREIGN"),),
                                            as_of=b.available_at)
        with self.assertRaises(ContractError):
            retrospective_swing_observation(r, (w.parent_4h,), as_of=b.available_at)

    def test_tamper_research_receipt_outcome_rejected(self):
        w = fixture()
        row = run(w)
        edited = dict(row, direction="DOWN")
        with self.assertRaises(ContractError):
            retrospective_swing_observation(edited, (), as_of=w.parent_4h.available_at)

    def test_nonfinite_and_bad_manifest_fail(self):
        w = fixture()
        with self.assertRaises(ValueError):
            replace(w.parent_4h, high=D("NaN"))
        self.assertEqual(run(replace(w, source_manifest_sha256="not-a-sha"))["status"],
                         "UNAVAILABLE")

    def test_bos_after_previous_confirmed_uptrend(self):
        prefix = series_of_extrema([101,102,106,103,101], [99,98,95,98,99])
        wick = candle("4h", START+timedelta(hours=20), 4, 100, 100, high=108, low=98)
        initial = candle("4h", START+timedelta(hours=24), 4, 100, 107, high=108, low=99)
        fresh_high = candle("4h", START+timedelta(hours=28), 4, 100, 100,
                            high=111, low=98)
        right1 = candle("4h", START+timedelta(hours=32), 4, 100, 100,
                        high=109, low=97)
        right2 = candle("4h", START+timedelta(hours=36), 4, 100, 100,
                        high=108, low=98)
        breakout = candle("4h", START+timedelta(hours=40), 4, 100, 112,
                          high=113, low=99)
        r = _pivots_and_breaks((*prefix, wick, initial,
                               fresh_high, right1, right2, breakout))
        self.assertEqual([x["kind"] for x in r["close_breaks"][:2]],
                         ["INITIAL_BREAK", "BOS"])
        self.assertEqual(r["close_breaks"][1]["side"], "UP")

    def test_directional_initial_down_break(self):
        prefix = series_of_extrema([101,102,106,103,101], [99,98,95,98,99])
        down = candle("4h", START+timedelta(hours=20), 4, 100, 94,
                      high=101, low=93)
        r = _pivots_and_breaks((*prefix, down))
        self.assertEqual(r["close_breaks"][0]["side"], "DOWN")
        self.assertEqual(r["close_breaks"][0]["kind"], "INITIAL_BREAK")

    def test_timezone_utc_offset_normalizes_without_changing_snapshot(self):
        w = fixture()
        original = run(w)
        ksa_clock = w.parent_4h.available_at.astimezone(
            timezone(timedelta(hours=3)))
        adjusted = analyze_swing(w, decision_at=ksa_clock)
        self.assertEqual(original, adjusted)
        self.assertEqual(original["decision_lag_seconds"], "2.0")

    def test_future_initial_gap_censored_not_observed(self):
        w = fixture()
        row = run(w)
        # First full eligible 4h bar starts one 4h boundary after decision.
        gap_start = w.parent_4h.close_at + timedelta(hours=8)
        later = candle("4h", gap_start, 4, 105, 107)
        label = retrospective_swing_observation(
            row, (later,), as_of=later.available_at)
        self.assertEqual(label["status"], "CENSORED_GAP")
        self.assertIsNone(label["signed_close_return"])

    def test_future_boundary_availability_and_later_gap(self):
        w = fixture()
        row = run(w)
        expected_start = w.parent_4h.close_at + timedelta(hours=4)
        first = candle("4h", expected_start, 4, 105, 107)
        second = candle("4h", first.close_at, 4, 107, 108)
        result = retrospective_swing_observation(row, (first, second), as_of=second.available_at)
        self.assertEqual(result["status"], "OBSERVED")
        self.assertEqual(result["expected_first_full_bar_at"],
                         expected_start.isoformat().replace("+00:00", "Z"))
        self.assertEqual(result["closed_bar_count"], 2)
        with self.assertRaisesRegex(ContractError, "INVALID_OR_UNAVAILABLE_4h"):
            retrospective_swing_observation(row, (first,), as_of=first.received_at)
        third = candle("4h", second.close_at, 4, 108, 109)
        with self.assertRaisesRegex(ContractError, "GAP_DUPLICATE_OR_OUT_OF_ORDER"):
            retrospective_swing_observation(row, (first, third), as_of=third.available_at)

    def test_aligned_decision_admits_bar_opening_at_decision(self):
        w = fixture()
        decision = w.parent_4h.close_at + timedelta(hours=4)
        row = analyze_swing(w, decision_at=decision)
        first = candle("4h", decision, 4, 105, 107)
        result = retrospective_swing_observation(row, (first,), as_of=first.available_at)
        self.assertEqual(result["status"], "OBSERVED")

    def test_8h_zero_price_and_negative_volume_fail_closed(self):
        w = fixture(with_eight=True)
        for fields in ({"open": D("0")}, {"base_volume": D("-1")}):
            result = run(replace(w, comparison_8h=replace(w.comparison_8h, **fields)))
            self.assertEqual(result["status"], "UNAVAILABLE")
            self.assertIn("STAGE08_8H_INVALID_OHLCV", str(result))

    def test_synthetic_baseline_agreement_is_not_predictive_claim(self):
        up, down = run(fixture("UP")), run(fixture("DOWN"))
        report = compare_synthetic_structure([up, down])
        self.assertEqual(report["summary"]["count"], 2)
        self.assertEqual(report["summary"]["known_pairs"] +
                         report["summary"]["unknown_pairs"], 2)
        self.assertIsNone(report["prediction_accuracy"])
        self.assertIsNone(report["false_positive_rate"])
        damaged = dict(up, signal_id="FAKE")
        with self.assertRaises(ContractError):
            compare_synthetic_structure([damaged])

    def test_late_pivot_source_receipt_never_backdates_confirmation(self):
        bars = series_of_extrema([101,102,106,103,101], [99,98,95,98,99])
        delayed_source = replace(
            bars[2], available_at=bars[4].available_at+timedelta(minutes=7))
        observed = _pivots_and_breaks((*bars[:2], delayed_source, *bars[3:]))
        high = next(p for p in observed["confirmed_pivots"] if p["kind"]=="HIGH")
        self.assertEqual(
            high["first_available_at"],
            delayed_source.available_at.isoformat().replace("+00:00","Z"))
        self.assertNotEqual(high["first_available_at"], high["confirmation_close_at"])
