"""Scoped Stage07 offline tests; no source, Telegram, SQL or market access."""
from dataclasses import replace
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from unittest import TestCase

from zs_smart_gate.mtf_contracts import CandleWindow
from zs_smart_gate.stage07_intraday import ResearchWindow, evaluate_window, retrospective_labels
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
        self.assertIn(out["status"], ("CENSORED", "DIRECTIONAL_MOVE_TOUCHED",
                                      "OPPOSITE_MOVE_TOUCHED", "AMBIGUOUS_OHLC_ORDER"))
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
