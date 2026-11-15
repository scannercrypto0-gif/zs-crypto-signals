"""Pure synthetic tests; no external API, market data, or Telegram."""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from zs_smart_gate.stage06a_outcomes import ClosedBar, TradeLevels, evaluate_outcome

T = datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)
LONG = TradeLevels("LONG", D("100"), D("95"), D("110"))
SHORT = TradeLevels("SHORT", D("100"), D("105"), D("90"))


def bar(i, low, high, *, available_delay=1, closed=True, open_price="100"):
    start = T + timedelta(minutes=5 * i)
    end = start + timedelta(minutes=5)
    return ClosedBar(start, end, end + timedelta(seconds=available_delay),
                     D(str(open_price)), D(str(high)), D(str(low)), D(str(open_price)), closed)


class Stage06AOutcomeTests(unittest.TestCase):
    def result(self, bars, plan=LONG, available=T):
        return evaluate_outcome(plan, available, T + timedelta(hours=2), bars)

    def test_long_entry_then_target_later(self):
        out = self.result([bar(0, 99, 102), bar(1, 99, 111)])
        self.assertEqual((out.status, out.examined_bars, out.exit_bar_open_at),
                         ("TARGET_TOUCHED", 2, T + timedelta(minutes=5)))

    def test_long_entry_then_stop_later(self):
        self.assertEqual(self.result([bar(0, 99, 101), bar(1, 94, 101)]).status, "STOP_TOUCHED")

    def test_entry_bar_with_target_is_ambiguous(self):
        self.assertEqual(self.result([bar(0, 99, 111)]).status, "AMBIGUOUS_ENTRY_BAR")

    def test_entry_bar_with_stop_is_ambiguous(self):
        self.assertEqual(self.result([bar(0, 94, 101)]).status, "AMBIGUOUS_ENTRY_BAR")

    def test_subsequent_same_bar_target_and_stop_is_ambiguous(self):
        self.assertEqual(self.result([bar(0, 99, 101), bar(1, 94, 111)]).status, "AMBIGUOUS_EXIT_BAR")

    def test_no_entry_and_left_censored_prefix(self):
        out = self.result([bar(0, 99, 101), bar(1, 102, 103, open_price=102)], available=T + timedelta(minutes=2))
        self.assertEqual(out.status, "NO_ENTRY")
        self.assertEqual(out.examined_bars, 1)
        self.assertIn("straddling", out.note)

    def test_data_gap_fails_closed(self):
        self.assertEqual(self.result([bar(0, 99, 102), bar(2, 99, 111)]).status, "DATA_GAP")

    def test_future_bar_not_eligible(self):
        future_asof = T + timedelta(minutes=4)
        self.assertEqual(evaluate_outcome(LONG, T, future_asof, [bar(0, 99, 101)]).status,
                         "UNAVAILABLE_FUTURE_BAR")

    def test_no_complete_postavailability_data(self):
        self.assertEqual(self.result([bar(0, 99, 102)], available=T + timedelta(minutes=3)).status,
                         "INSUFFICIENT_HISTORY")

    def test_short_direction_entry_then_target(self):
        self.assertEqual(self.result([bar(0, 99, 102), bar(1, 89, 101)], SHORT).status,
                         "TARGET_TOUCHED")

    def test_invalid_ohlc_and_plan_fail_closed(self):
        with self.assertRaises(ValueError):
            self.result([bar(0, 110, 100)])
        with self.assertRaises(ValueError):
            self.result([bar(0, 99, 101)], TradeLevels("LONG", D("100"), D("110"), D("95")))

    def test_unclosed_or_non_utc_rejected(self):
        with self.assertRaises(ValueError):
            self.result([bar(0, 99, 101, closed=False)])
        with self.assertRaises(ValueError):
            evaluate_outcome(LONG, T.replace(tzinfo=None), T + timedelta(hours=2), [])


if __name__ == "__main__":
    unittest.main()
