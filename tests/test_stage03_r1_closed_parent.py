"""R1 independent closed-30m local input tests (Windows only; no network)."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile

from zs_smart_gate.core import MarketSnapshot
from zs_smart_gate.mtf_contracts import CandleWindow
from zs_smart_gate.stage03_r0_identity import DiscoveryReference
from zs_smart_gate.stage03_r1_closed_parent import (
    Closed30mItem, MarketReceipt, evaluate_local_universe, persist_local_research,
)
from zs_smart_gate.stage05_contracts import ContractError
from zs_smart_gate.stage05_custody import LocalOutbox

UTC = timezone.utc
T = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
CLOSE = T + timedelta(minutes=30)
DECISION = CLOSE + timedelta(seconds=10)
FEED = "SYNTHETIC:SPOT:REST"


def window(frame, start, o, h, l, c, base, quote, *, received=None, source=FEED):
    minutes = {"5m": 5, "30m": 30, "1h": 60, "4h": 240}[frame]
    close = start + timedelta(minutes=minutes)
    received = received or (CLOSE + timedelta(seconds=2))
    return CandleWindow(frame, start, close, received, received, source,
                        o, h, l, c, base, quote)


def fixture(*, discovery=None, weak=False, symbol="BTCUSDT"):
    candles = []
    for i in range(6):
        o = str(100+i if not weak else 100-i)
        c = str(101+i if not weak else 99-i)
        candles.append(window("5m", T+timedelta(minutes=5*i),
                              o, str(max(int(o), int(c))+1),
                              str(min(int(o), int(c))-1), c, "10", "1000"))
    parent = window("30m", T, candles[0].open, max(c.high for c in candles),
                    min(c.low for c in candles), candles[-1].close, "60", "6000")
    context = (
        window("1h", T-timedelta(hours=1), "95", "108", "94", "101", "120", "12000"),
        window("4h", T-timedelta(hours=4), "90", "110", "89", "102", "400", "40000"),
    )
    market = MarketSnapshot(symbol, "USDT", True, "TRADING", "20000000",
                            "106", "106.01", CLOSE+timedelta(seconds=1))
    receipt = MarketReceipt(FEED, market.observed_at, CLOSE+timedelta(seconds=2),
                            CLOSE+timedelta(seconds=3))
    return Closed30mItem(market, receipt, symbol, parent, tuple(candles),
                         context, "a"*64, discovery=discovery)


class TestR1ClosedParent(unittest.TestCase):
    def evaluate(self, *items):
        return evaluate_local_universe(tuple(items), closed_at=CLOSE, decision_at=DECISION)

    def test_f01_independent_30m_no_breakout(self):
        a = self.evaluate(fixture())[0]
        b = self.evaluate(fixture(discovery=DiscoveryReference("NO_BREAKOUT")))[0]
        self.assertTrue(a["raw_30m_evaluation_eligible"])
        self.assertEqual(a["evaluation_status"], "POLICY_HOLD")
        self.assertEqual(a["event_id"], b["event_id"])
        self.assertEqual(a["candidate_id"], b["candidate_id"])
        self.assertIsNone(a["discovery"])
        self.assertEqual(b["discovery"]["state"], "NO_BREAKOUT")
        self.assertIsNone(a["signal_id"])
        self.assertFalse(a["publishable"])

    def test_f02_5m_breakout_never_implies_30m_qualified(self):
        row = self.evaluate(fixture(weak=True,
                   discovery=DiscoveryReference("DETECTED_SETUP")))[0]
        self.assertTrue(row["raw_30m_evaluation_eligible"])
        self.assertEqual(row["evaluation_status"], "POLICY_HOLD")
        self.assertEqual(row["qualification_state"], "UNKNOWN")
        self.assertIsNone(row["signal_id"])

    def test_exact_six_same_source_and_source_mismatch(self):
        good = fixture()
        self.assertEqual(self.evaluate(good)[0]["reconciliation"],
                         "EXACT_MATCH_NOT_POLICY_APPROVAL")
        for damaged in (
            replace(good, children=good.children[:-1]),
            replace(good, children=(good.children[0],)*6),
            replace(good, children=good.children[:2]+
                    (replace(good.children[2],source_id="OTHER"),)+good.children[3:]),
            replace(good, children=good.children[:2]+
                    (replace(good.children[2],available_at=DECISION+timedelta(seconds=1)),)+good.children[3:]),
        ):
            with self.subTest(damaged=damaged.children):
                row = self.evaluate(damaged)[0]
                self.assertEqual(row["evaluation_status"], "INVALID")
                self.assertFalse(row["raw_30m_evaluation_eligible"])

    def test_parent_base_quote_exact_and_unapproved_tolerance(self):
        good = fixture()
        for field in ("base_volume", "quote_volume"):
            bad = replace(good, parent=replace(good.parent,
                               **{field:getattr(good.parent,field)+1}))
            row = self.evaluate(bad)[0]
            self.assertEqual(row["evaluation_status"], "UNKNOWN")
            self.assertIn("SOURCE_TOLERANCE_UNAPPROVED", row["reason_codes"][0])
            self.assertIsNone(row["signal_id"])

    def test_context_latest_available_and_absent(self):
        good=fixture()
        future = replace(good.context[0],open_at=CLOSE,
                        close_at=CLOSE+timedelta(hours=1),
                        received_at=CLOSE+timedelta(hours=1,seconds=1),
                        available_at=CLOSE+timedelta(hours=1,seconds=1))
        row=self.evaluate(replace(good,context=good.context+(future,)))[0]
        self.assertTrue(row["raw_30m_evaluation_eligible"])
        self.assertEqual(row["context_close_at"]["1h"],"2026-11-11T12:00:00Z")
        absent=self.evaluate(replace(good,context=()))[0]
        self.assertEqual(absent["evaluation_status"],"UNKNOWN")
        self.assertFalse(absent["raw_30m_evaluation_eligible"])

    def test_trigger_universe_eligibility_and_bounded_dedup(self):
        good=fixture()
        thin=replace(good,market=replace(good.market,quote_volume_24h="1"))
        self.assertEqual(self.evaluate(thin)[0]["evaluation_status"],"NOT_ELIGIBLE")
        with self.assertRaises(ContractError):
            self.evaluate(good,good)
        self.assertEqual(self.evaluate()[0:0], [])
        with self.assertRaises(ContractError):
            self.evaluate(*[replace(good,market=replace(good.market,symbol="T%02dUSDT"%i),
                              candle_symbol="T%02dUSDT"%i) for i in range(9)])

    def test_sqlite_reopen_append_only_without_v1_archive_or_signal(self):
        row=self.evaluate(fixture())[0]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"r1.sqlite"
            receipt=persist_local_research(LocalOutbox(path),row)
            self.assertEqual(receipt,persist_local_research(LocalOutbox(path),row))
            self.assertTrue(receipt["readback"]=="PASS")
            self.assertIsNone(receipt["signal_id"])
            self.assertFalse(receipt["dispatch_allowed"])
            self.assertFalse(row["stage05_event_v1_compatible"])
