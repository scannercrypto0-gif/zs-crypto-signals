"""009A only: new N07 reachable calculation, liquidity units, N10 and one 03A E2E.

Tests use typed synthetic sources and no network. Existing 007A/008 studies are
not invoked. Fixed expected results are independently calculated here.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch
import socket
import urllib.request

from test_stage03_r2_offline import (
    D, candle, falling_structure, intraday, market, swing,
)
from zs_smart_gate.core import Candle as CoreCandle, MarketSnapshot
from zs_smart_gate.mtf_contracts import CandleWindow, ReconciliationTolerance
from zs_smart_gate.stage03a_contracts import Direction, Horizon
from zs_smart_gate.stage03_r2_offline import (
    evaluate_r2, liquidity, Unavailable,
)
from zs_smart_gate.stage03_r2_functional import stage03_r2_functional_e2e


def stage03_inputs(kw):
    raw = kw["parent"]
    children = kw["children"]
    def make_window(c, frame, base):
        return CandleWindow(frame, c.open_at, c.close_at, c.received_at,
                            c.available_at, c.source_id, c.o, c.h, c.l, c.c,
                            D(base), c.q)
    cwindows = [make_window(c, "5m", "10") for c in children]
    pwindow = make_window(raw, "30m", str(10 * len(children)))
    historical = tuple(kw["context"]["5m"][-15:]) + tuple(children)
    core = [CoreCandle(c.open_at, c.close_at, c.received_at, c.available_at,
                       c.o, c.h, c.l, c.c, D("10"), c.q) for c in historical]
    m = kw["market"]
    # Synthetic fixture only. The 03A snapshot is not asserted atomic with
    # independently timestamped book/ticker; it is observed at decision.
    marketview = MarketSnapshot("BTCUSDT", "USDT", True, "TRADING",
                                m.quote_24h, m.bid, m.ask, kw["decision_at"])
    return dict(symbol="BTCUSDT", horizon=Horizon.INTRADAY,
                direction=kw["direction"], parent=pwindow, children=cwindows,
                core_5m=core, market=marketview, decision_at=kw["decision_at"],
                tolerance=ReconciliationTolerance("0", "0", "0", "SYNTHETIC_EXACT_009A"),
                event_discriminator="009A-OFFLINE-TEST")


class R2009AMinimalTests(TestCase):
    def test_n07_real_reachable_branch_with_prior_confirmed_pivots(self):
        x = swing()
        start = x["parent"].open_at
        prior = falling_structure(start)
        # Four reconciled 1h children of a 4h parent with an UP CHoCH.
        children = (
            candle(start, 60, o="95", h="103", l="94", c="97"),
            candle(start+timedelta(hours=1), 60, o="97", h="101", l="95", c="99"),
            candle(start+timedelta(hours=2), 60, o="99", h="101", l="98", c="100"),
            candle(start+timedelta(hours=3), 60, o="100", h="103", l="99", c="102"),
        )
        parent = candle(start, 240, o="95", h="103", l="94", c="102", q="40")
        x.update(parent=parent, children=children, direction=Direction.UP,
                 mode="REVERSAL", market=market(x["decision_at"],spread=".20"))
        x["context"] = {**x["context"], "structure4h": prior}
        row = evaluate_r2(**x)
        self.assertTrue(row["structural_event"])
        self.assertEqual(row["structural_event_kind"], "CHoCH")
        self.assertIsNotNone(row["normalizers"]["MARKET_STRUCTURE"])
        # Independent reference: TR for 14 previous 4h bars, plus
        # level 100 known by the end of the pivot right-hand window.
        bars = prior[-15:]
        tr = [max(b.h-b.l, abs(b.h-a.c), abs(b.l-a.c))
              for a,b in zip(bars[:-1],bars[1:])]
        atr = sum(tr,D("0"))/14
        expected = (D("27") + D("8") *
                    min(D("1"),(D("102")-D("100")-D(".20"))/atr))/D("35")
        self.assertEqual(D(row["normalizers"]["MARKET_STRUCTURE"]),expected)
        self.assertLess(prior[24].available_at, parent.open_at)
        self.assertEqual(row["score_status"],"SCORE_UNAVAILABLE")
        self.assertFalse(row["qualified"])

        # A future-delivered middle confirmation must NOT be silently dropped.
        untrusted=list(prior)
        untrusted[24]=replace(untrusted[24],
                              available_at=parent.open_at+timedelta(seconds=1))
        blocked=evaluate_r2(**{**x,"context":{**x["context"],
                                             "structure4h":tuple(untrusted)}})
        self.assertIsNone(blocked["normalizers"]["MARKET_STRUCTURE"])
        self.assertIn("PIVOT_ASOF_HISTORY_GAP",
                      blocked["missing_reasons"]["MARKET_STRUCTURE"])

    def test_n06_n12_quote24_units_reference_and_missingness(self):
        for make in (intraday,swing):
            x=make()
            m=x["market"]
            spread=D("10000")*(m.ask-m.bid)/((m.ask+m.bid)/2)
            expected=(D("3")*(D("1")-spread/D("20"))
                      +D("2")*(D("1")-D("10000000")/m.quote_24h))/5
            self.assertEqual(liquidity(m,x["decision_at"],x["witness"]),expected)
            for changes in (
                {"ticker24_unit":"BASE"},
                {"ticker24_window":"CANDLE_24H"},
                {"quote_asset":"BTC"},
                {"trading_status":"HALT"},
            ):
                with self.subTest(make=make.__name__, changes=changes):
                    with self.assertRaisesRegex(Unavailable,
                                                "MARKET_QUOTE_UNIT_WINDOW_OR_TRADING"):
                        liquidity(replace(m,**changes),x["decision_at"],x["witness"])
            bad=replace(m, ticker24=replace(m.ticker24,
                          available_at=x["decision_at"]+timedelta(seconds=5)))
            with self.assertRaisesRegex(Unavailable,"PIT_AVAILABILITY"):
                liquidity(bad,x["decision_at"],x["witness"])
        self.assertNotEqual(D("100"),D("20000000"))
        self.assertEqual(intraday()["market"].ticker24_unit,"USDT")

    def test_n10_two_closed_frames_and_context_only(self):
        x=swing()
        daily=list(x["context"]["1d"])
        weekly=list(x["context"]["1w"])
        daily[-1]=replace(daily[-1],c=D("103"),h=D("104"))
        weekly[-1]=replace(weekly[-1],c=D("110"),h=D("111"))
        x["context"]={**x["context"],"1d":tuple(daily),"1w":tuple(weekly)}
        x.update(direction=Direction.UP,mode="CONTINUATION")
        row=evaluate_r2(**x)
        expected=D(".6")*(D("3")/D("5"))+D(".4")*(D("5")/D("6"))
        self.assertEqual(D(row["normalizers"]["DAILY_WEEKLY_CONTEXT"]),expected)
        self.assertIn("DAILY_WEEKLY_CONTEXT",row["context_only"])
        self.assertFalse(row["structural_event"])
        late=list(weekly)
        late[-1]=replace(late[-1],available_at=x["decision_at"]+timedelta(seconds=1))
        blocked=evaluate_r2(**{**x,"context":{**x["context"],"1w":tuple(late)}})
        self.assertIsNone(blocked["normalizers"]["DAILY_WEEKLY_CONTEXT"])
        self.assertIn("PIT_AVAILABILITY",
                      blocked["missing_reasons"]["DAILY_WEEKLY_CONTEXT"])

    def test_one_stage03_functional_e2e_reproducible_and_rejected(self):
        x=intraday()
        y=stage03_inputs(x)
        with patch("socket.create_connection",side_effect=AssertionError("NO_NETWORK")), \
             patch("urllib.request.urlopen",side_effect=AssertionError("NO_NETWORK")):
            ok=stage03_r2_functional_e2e(r2_inputs=x,readiness_inputs=y)
            retry=stage03_r2_functional_e2e(r2_inputs=x,readiness_inputs=y)
            self.assertEqual(ok,retry)
            self.assertEqual(ok["status"],"RESEARCH_CANDIDATE")
            self.assertEqual(ok["readiness_status"],"RESEARCH_CANDIDATE")
            self.assertEqual(ok["qualification_status"],"NOT_EVALUATED")
            self.assertEqual(ok["r2"]["status"],"DEV_CANDIDATE")
            self.assertEqual(len(ok["r2"]["normalizers"]),6)
            self.assertEqual(ok["source_match_reasons"],[])
            self.assertEqual(len(ok["packet_sha256"]),64)
            self.assertEqual(ok["provenance"]["quote24_unit"],"USDT")
            self.assertIsNone(ok["signal_id"])
            self.assertIsNone(ok["score"])
            self.assertFalse(ok["publishable"])
            self.assertEqual(ok["market_requests"],0)
            mismatch=replace(y["parent"],quote_volume=y["parent"].quote_volume+D("1"))
            bad=stage03_r2_functional_e2e(r2_inputs=x,
                           readiness_inputs={**y,"parent":mismatch})
            self.assertEqual(bad["status"],"REJECTED")
            self.assertIn("R2_03A_PARENT_SOURCE_AND_VALUES_DISAGREE",
                          bad["source_match_reasons"])
            self.assertIsNone(bad["signal_id"])
            future=replace(x["market"],ticker24=replace(x["market"].ticker24,
                          available_at=x["decision_at"]+timedelta(seconds=1)))
            denied=stage03_r2_functional_e2e(r2_inputs={**x,"market":future},
                                              readiness_inputs=y)
            self.assertIsNone(denied["r2"]["normalizers"]["LIQUIDITY_QUALITY"])
            self.assertIn("PIT_AVAILABILITY",
                          denied["r2"]["missing_reasons"]["LIQUIDITY_QUALITY"])
            self.assertFalse(denied["publishable"])
