"""Scoped Stage07 offline tests; no source, Telegram, SQL or market access."""
from dataclasses import replace
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from unittest import TestCase

from zs_smart_gate.mtf_contracts import CandleWindow
from zs_smart_gate.stage07_intraday import (ResearchWindow, evaluate_window,
    evaluate_partial_window, retrospective_labels, compare_research_candidates)
from zs_smart_gate.stage05_contracts import ContractError


START = datetime(2026, 11, 15, 10, tzinfo=timezone.utc)
SOURCE = "SYNTHETIC:STAGE07"


def bars(direction="UP"):
    sign = D("1") if direction == "UP" else D("-1")
    def make(frame, at, minutes, op, close, vol=D("10")):
        hi, lo = max(op, close) + D("0.2"), min(op, close) - D("0.2")
        return CandleWindow(frame, at, at + timedelta(minutes=minutes),
            at + timedelta(minutes=minutes, seconds=1),
            at + timedelta(minutes=minutes, seconds=2),
            SOURCE, op, hi, lo, close, vol, vol * D("100"))
    past = tuple(make("5m", START + timedelta(minutes=5*i), 5,
                      D("100"), D("100")) for i in range(6))
    items = []
    price = D("100")
    for i in range(6):
        nxt = price + sign * D("0.3")
        items.append(make("5m", START + timedelta(minutes=30 + 5*i),
                          5, price, nxt))
        price = nxt
    parent = CandleWindow("30m", START+timedelta(minutes=30),
        START+timedelta(minutes=60), START+timedelta(minutes=60, seconds=1),
        START+timedelta(minutes=60, seconds=2), SOURCE,
        items[0].open, max(x.high for x in items),
        min(x.low for x in items), items[-1].close,
        sum((x.base_volume for x in items), D("0")),
        sum((x.quote_volume for x in items), D("0")))
    return ResearchWindow("BTCUSDT", direction, parent, tuple(items), past,
                          source_manifest_sha256="a"*64)


def run(window):
    return evaluate_window(window, decision_at=window.parent.available_at)


class Stage07Tests(TestCase):
    def test_both_directions_and_no_signal(self):
        for direction in ("UP", "DOWN"):
            r = run(bars(direction))
            self.assertEqual(r["status"], "RESEARCH_MEASURED")
            self.assertEqual(r["features"]["directional_return"]["status"], "PRESENT")
            self.assertIsNone(r["signal_id"])
            self.assertIsNone(r["score"])
            self.assertFalse(r["publishable"])
            self.assertEqual(run(bars(direction)), r)
        self.assertNotEqual(run(bars("UP"))["event_id"], run(bars("DOWN"))["event_id"])

    def test_future_mutation_cannot_change_feature(self):
        w = bars()
        r = run(w)
        future = tuple(replace(b, high=b.high+D("50")) for b in w.children)
        # Input mutation after decision must be rejected, not retroactively alter the snapshot.
        self.assertNotEqual(r["status"], run(replace(w, children=future))["status"])
        self.assertEqual(r, run(w))

    def test_source_mismatch_and_partial(self):
        w = bars()
        bad = replace(w.children[0], source_id="SYNTHETIC:OTHER")
        self.assertEqual(run(replace(w, children=(bad, *w.children[1:])))["status"], "UNAVAILABLE")
        partial = replace(w.children[-1], available_at=w.parent.available_at+timedelta(seconds=10))
        self.assertEqual(run(replace(w, children=(*w.children[:-1], partial)))["status"], "UNAVAILABLE")

    def test_out_of_order_gap_and_stale_source(self):
        w = bars()
        self.assertEqual(run(replace(w, children=tuple(reversed(w.children))))["status"], "UNAVAILABLE")
        self.assertEqual(run(replace(w, history_5m=w.history_5m[:-1]))["status"], "UNAVAILABLE")
        self.assertEqual(run(replace(w, source_scope="APPROVED_REAL_SOURCE"))["status"], "UNAVAILABLE")

    def test_no_universal_six_green_prerequisite(self):
        w = bars()
        mid = replace(w.children[2], close=w.children[2].open)
        # A non-green bar is not a forbidden input; reconcile parent to changed children.
        latest = (*w.children[:2], mid, *w.children[3:])
        parent = replace(w.parent, high=max(x.high for x in latest),
                         low=min(x.low for x in latest))
        self.assertEqual(run(replace(w, parent=parent, children=latest))["status"], "RESEARCH_MEASURED")

    def test_labels_separate_and_straddling_rejected(self):
        w = bars()
        record = run(w)
        start = w.parent.available_at
        # Align the first future bar to the next full UTC 5-minute boundary.
        begin = datetime.fromtimestamp((int(start.timestamp()) // 300+1)*300, timezone.utc)
        b = replace(w.children[0], open_at=begin, close_at=begin+timedelta(minutes=5),
                    received_at=begin+timedelta(minutes=5, seconds=1),
                    available_at=begin+timedelta(minutes=5, seconds=2))
        out = retrospective_labels(record, (b,), as_of=b.available_at, move_fraction=D("0.01"))
        self.assertEqual(set(out["horizons"]), {"1", "2", "4", "8", "12", "24"})
        self.assertEqual(out["horizons"]["1"]["status"], "OPPOSITE_MOVE_TOUCHED")
        self.assertEqual(out["reference_price"], record["decision_reference_price"])
        self.assertIsNone(record["signal_id"])
        with self.assertRaises(ContractError):
            retrospective_labels(record, (replace(b, open_at=start-timedelta(seconds=1)),),
                                 as_of=b.available_at, move_fraction=D("0.01"))

    def test_label_rejects_record_tampering_and_foreign_source(self):
        w = bars()
        record = run(w)
        a = w.parent.available_at
        begin = datetime.fromtimestamp((int(a.timestamp()) // 300+1)*300, timezone.utc)
        b = replace(w.children[0], open_at=begin, close_at=begin+timedelta(minutes=5),
                    received_at=begin+timedelta(minutes=5, seconds=1),
                    available_at=begin+timedelta(minutes=5, seconds=2))
        tampered = deepcopy(record)
        tampered["direction"] = "DOWN"
        with self.assertRaises(ContractError):
            retrospective_labels(tampered, (b,), as_of=b.available_at, move_fraction=D("0.01"))
        with self.assertRaises(ContractError):
            retrospective_labels(record, (replace(b, source_id="SYNTHETIC:OTHER"),),
                                 as_of=b.available_at, move_fraction=D("0.01"))
        with self.assertRaises(ContractError):
            retrospective_labels(record, (b,), as_of=b.available_at, move_fraction=D("1"))

    def test_partial_prefix_uses_no_parent_future_ohlc(self):
        w = bars()
        prefix = w.children[:3]
        decision = prefix[-1].available_at
        a = evaluate_partial_window(w, prefix, decision_at=decision)
        self.assertEqual(a["status"], "RESEARCH_MEASURED")
        self.assertEqual(a["observation_status"], "PARTIAL_PARENT_30M")
        self.assertEqual(a["observed_closed_5m_count"], 3)
        full_mutated = replace(w.parent, high=w.parent.high+D("900"), close=D("500"))
        after = tuple(replace(x, high=x.high+D("50")) for x in w.children[3:])
        newer = evaluate_partial_window(replace(w, parent=full_mutated, children=(*prefix,*after)),
                                        prefix, decision_at=decision)
        self.assertEqual(a, newer)
        self.assertIsNone(a["signal_id"])
        self.assertFalse(a["publishable"])
        self.assertEqual(evaluate_partial_window(w, w.children, decision_at=decision)["status"], "UNAVAILABLE")

    def test_partial_rejects_future_closed_bar_and_history_gap(self):
        w = bars("DOWN")
        prefix = w.children[:3]
        now = prefix[-1].available_at
        self.assertEqual(evaluate_partial_window(w, prefix, decision_at=now)["status"], "RESEARCH_MEASURED")
        late = replace(prefix[-1], received_at=now+timedelta(seconds=1),
                       available_at=now+timedelta(seconds=2))
        self.assertEqual(evaluate_partial_window(w, (*prefix[:2], late), decision_at=now)["status"], "UNAVAILABLE")
        self.assertEqual(evaluate_partial_window(replace(w, history_5m=w.history_5m[:-1]),
                         prefix, decision_at=now)["status"], "UNAVAILABLE")

    def test_real_future_mutation_changes_labels_not_features(self):
        w = bars()
        rec = run(w)
        begin = datetime.fromtimestamp((int(w.parent.available_at.timestamp()) // 300+1)*300,
                                        timezone.utc)
        b = replace(w.children[0], open_at=begin, close_at=begin+timedelta(minutes=5),
                    received_at=begin+timedelta(minutes=5, seconds=1),
                    available_at=begin+timedelta(minutes=5, seconds=2))
        low = replace(b, high=max(b.open,b.close)+D("0.2"), low=b.open-D("0.2"))
        high = replace(low, high=low.open+D("10"))
        a = retrospective_labels(rec, (low,), as_of=low.available_at, move_fraction=D("0.01"))
        z = retrospective_labels(rec, (high,), as_of=high.available_at, move_fraction=D("0.01"))
        self.assertNotEqual(a["horizons"]["1"]["status"], z["horizons"]["1"]["status"])
        self.assertEqual(rec, run(w))
        self.assertEqual(a["reference_price"], z["reference_price"])

    def test_double_touch_ambiguity_and_six_horizons(self):
        w = bars()
        rec = run(w)
        begin = datetime.fromtimestamp((int(w.parent.available_at.timestamp()) // 300+1)*300,
                                        timezone.utc)
        b = replace(w.children[0], open_at=begin, close_at=begin+timedelta(minutes=5),
                    received_at=begin+timedelta(minutes=5, seconds=1),
                    available_at=begin+timedelta(minutes=5, seconds=2),
                    high=D("120"), low=D("80"))
        x = retrospective_labels(rec, (b,), as_of=b.available_at, move_fraction=D("0.01"))
        for h in ("1","2","4","8","12","24"):
            self.assertEqual(x["horizons"][h]["status"], "AMBIGUOUS_OHLC_ORDER")
            self.assertIsNone(x["horizons"][h]["lead_hours"])
        self.assertEqual(x["reference_price"], rec["decision_reference_price"])

    def test_label_censoring_gap_and_timezone(self):
        w = bars()
        rec = run(w)
        begin = datetime.fromtimestamp((int(w.parent.available_at.timestamp()) // 300+2)*300,
                                        timezone.utc)
        b = replace(w.children[0], open_at=begin, close_at=begin+timedelta(minutes=5),
                    received_at=begin+timedelta(minutes=5, seconds=1),
                    available_at=begin+timedelta(minutes=5, seconds=2))
        label = retrospective_labels(rec, (b,), as_of=b.available_at.astimezone(
            timezone(timedelta(hours=3))), move_fraction=D("0.01"))
        self.assertEqual(label["horizons"]["1"]["status"], "CENSORED_GAP")
        self.assertEqual(label["horizons"]["1"]["censor_reason"], "UNOBSERVED_INTERVAL")

    def test_synthetic_baseline_ablation_and_overlap_exclusion(self):
        w = bars()
        rec = run(w)
        begin = datetime.fromtimestamp((int(w.parent.available_at.timestamp()) // 300+1)*300,
                                        timezone.utc)
        b = replace(w.children[0], open_at=begin, close_at=begin+timedelta(minutes=5),
                    received_at=begin+timedelta(minutes=5, seconds=1),
                    available_at=begin+timedelta(minutes=5, seconds=2))
        label = retrospective_labels(rec, (b,), as_of=b.available_at, move_fraction=D("0.01"))
        sample = compare_research_candidates([(rec,label),(rec,label)], horizon_hours=4)
        self.assertEqual(sample["input_count"], 2)
        self.assertEqual(sample["nonoverlapping_count"], 1)
        self.assertEqual(sample["excluded_overlap"], 1)
        self.assertEqual(sample["scientific_validity"], "DEMONSTRATION_ONLY_NOT_OOS")

    def test_nonfinite_scalar_fail_closed(self):
        w = bars()
        with self.assertRaises((ValueError, ArithmeticError)):
            replace(w.parent, high=D("NaN"))
        self.assertEqual(run(replace(w, source_manifest_sha256="NOT_A_SHA"))["status"], "UNAVAILABLE")

    def test_independent_horizon_censoring_after_first_hour(self):
        w = bars()
        rec = run(w)
        begin = datetime.fromtimestamp((int(w.parent.available_at.timestamp()) // 300+1)*300,
                                        timezone.utc)
        future = []
        for i in range(12):
            at = begin + timedelta(minutes=5*i)
            b = replace(w.children[0], open_at=at, close_at=at+timedelta(minutes=5),
                        received_at=at+timedelta(minutes=5, seconds=1),
                        available_at=at+timedelta(minutes=5, seconds=2),
                        open=D("101.8"), close=D("101.8"),
                        high=D("102"), low=D("101.6"))
            future.append(b)
        out = retrospective_labels(rec, tuple(future), as_of=future[-1].available_at,
                                   move_fraction=D("0.05"))
        one_hour = out["horizons"]["1"]
        self.assertNotEqual(w.parent.available_at.second, 0)
        self.assertGreaterEqual(future[-1].available_at,
                                w.parent.available_at + timedelta(hours=1))
        self.assertEqual(one_hour["status"], "CENSORED_HORIZON")
        self.assertEqual(one_hour["bars_examined"], 11)
        self.assertEqual(one_hour["observed_until"], "2026-11-15T12:00:00Z")
        self.assertEqual(one_hour["horizon_end_at"], "2026-11-15T12:00:02Z")
        self.assertEqual(out["horizons"]["2"]["bars_examined"], 12)
        self.assertEqual(out["horizons"]["24"]["status"], "CENSORED_HORIZON")
        self.assertNotEqual(out["horizons"]["1"]["horizon_end_at"],
                            out["horizons"]["24"]["horizon_end_at"])

    def test_comparison_observed_true_false_positive_and_censor(self):
        w = bars()
        rec = run(w)
        begin = datetime.fromtimestamp((int(w.parent.available_at.timestamp()) // 300+1)*300,
                                        timezone.utc)
        base = replace(w.children[0], open_at=begin,
                       close_at=begin+timedelta(minutes=5),
                       received_at=begin+timedelta(minutes=5, seconds=1),
                       available_at=begin+timedelta(minutes=5, seconds=2),
                       open=D("101.8"), close=D("101.8"),
                       low=D("101.7"), high=D("104"))
        positive = retrospective_labels(rec, (base,), as_of=base.available_at,
                                        move_fraction=D("0.01"))
        bad = replace(base, high=D("101.9"), low=D("99"))
        negative = retrospective_labels(rec, (bad,), as_of=bad.available_at,
                                        move_fraction=D("0.01"))
        alt = run(replace(w, symbol="ETHUSDT"))
        alternative = retrospective_labels(alt, (bad,), as_of=bad.available_at,
                                           move_fraction=D("0.01"))
        report = compare_research_candidates([(rec,positive),(alt,alternative)],horizon_hours=1)
        baseline = report["baseline_and_ablation"]["baseline_directional_sign"]
        self.assertEqual(baseline["selected"], 2)
        self.assertEqual(baseline["true_positive"], 1)
        self.assertEqual(baseline["false_positive"], 1)
        self.assertEqual(baseline["false_positive_rate"], "0.5")
