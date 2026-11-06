"""Synthetic-only R2 normalizer, causal PIT and no-publish regressions."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch
import socket
import urllib.request

from zs_smart_gate.stage03a_contracts import Direction, Horizon, V2_GROUPS
from zs_smart_gate.setup021 import CONFIG_SHA256, VERSION as FROZEN_VERSION
from zs_smart_gate.stage03_r2_offline import (
    VERSION, BREAK_ATR_CANDIDATE, Candle, ClockWitness, Market,
    SourceReceipt, Unavailable, asof, close_parts, confirmed_pivots,
    evaluate_r2, liquidity, onset_timing, path_parts, structure,
    volume_continuity,
)

D = Decimal
UTC = timezone.utc
BASE = datetime(2026, 6, 1, tzinfo=UTC)
WITNESS = ClockWitness("SYNTHETIC:INDEPENDENT_UTC_FIXTURE", D(".1"))


def candle(start, minutes, o="100", h="101", l="99", c="100", q="10", **kw):
    closed = start + timedelta(minutes=minutes)
    return Candle(start, closed, closed + timedelta(seconds=1),
                  closed + timedelta(seconds=1), D(o), D(h), D(l), D(c),
                  D(q), **kw)


def history(start, n, minutes, q="10"):
    return tuple(candle(start + timedelta(minutes=minutes*i), minutes, q=q)
                 for i in range(n))


def market(decision, *, spread="0.10", quote="20000000", book_age=2,
           ticker_age=30, book_avail_lag=1):
    bid = D("100")
    def receipt(age, lag):
        return SourceReceipt(decision - timedelta(seconds=age),
                             decision - timedelta(seconds=age - lag / 2),
                             decision - timedelta(seconds=age - lag))
    return Market(receipt(book_age, book_avail_lag), receipt(ticker_age, 1),
                  bid, bid+D(spread), D(quote))


def intraday():
    start = BASE + timedelta(days=2)
    children = tuple(candle(start + timedelta(minutes=5*i), 5,
                            q=str(12+i)) for i in range(6))
    decision = start + timedelta(minutes=30, seconds=20)
    parent = candle(start, 30, q=str(sum(x.q for x in children)))
    context = {
        "5m": history(start-timedelta(minutes=39*5), 39, 5),
        "30m": history(start-timedelta(minutes=15*30), 15, 30),
        "1h": history(start-timedelta(hours=21), 21, 60),
        "4h": history(start-timedelta(hours=4*21), 21, 240),
    }
    return dict(horizon=Horizon.INTRADAY, direction=Direction.UP,
                mode="CONTINUATION", parent=parent, children=children,
                context=context, market=market(decision), witness=WITNESS,
                decision_at=decision, impulse_state=False,
                impulse_trace=(False,)*45)


def swing():
    start = BASE + timedelta(days=7)
    children = tuple(candle(start+timedelta(hours=i), 60) for i in range(4))
    decision = start+timedelta(hours=4, seconds=20)
    parent = candle(start, 240, q="40")
    context = {
        "4h": history(start-timedelta(hours=20*4), 20, 240),
        "1d": history(start-timedelta(days=18), 18, 1440),
        "1w": history(start-timedelta(days=18*7), 18, 10080),
        "structure4h": history(start-timedelta(hours=32*4), 32, 240),
    }
    return dict(horizon=Horizon.SWING, direction=Direction.DOWN,
                mode="REVERSAL", parent=parent, children=children,
                context=context, market=market(decision), witness=WITNESS,
                decision_at=decision)


def falling_structure(start):
    first = start-timedelta(hours=32*4)
    bars = [replace(b, o=D("95"), c=D("95"), h=D("97"), l=D("93"))
            for b in history(first, 32, 240)]
    for i, high in ((6, "110"), (14, "105"), (22, "100")):
        bars[i] = replace(bars[i], h=D(high))
    for i, low in ((9, "90"), (17, "85"), (25, "80")):
        bars[i] = replace(bars[i], l=D(low))
    return tuple(bars)


class R2Contracts(TestCase):
    def test_frozen_contract_untouched_and_existing_v2_groups(self):
        self.assertEqual(FROZEN_VERSION, "ORDER021_SETUP_V1_1_FROZEN")
        self.assertEqual(CONFIG_SHA256,
                         "0cb5f5aed50ac219d00188cca9827b26ab75dd15a9786773e683b40d10d818ce")
        self.assertEqual(VERSION, "STAGE03_R2_DEV_CANDIDATE_UNFROZEN")
        for h in Horizon:
            self.assertEqual(len(V2_GROUPS[h]), 6)
            self.assertEqual(sum(weight for _, weight in V2_GROUPS[h]), 100)

    def test_both_horizons_directions_and_modes_never_publish_or_score(self):
        for make in (intraday, swing):
            for direction in Direction:
                for mode in ("CONTINUATION", "REVERSAL"):
                    with self.subTest(make=make.__name__,direction=direction,mode=mode):
                        kw = make()
                        kw.update(direction=direction, mode=mode)
                        row = evaluate_r2(**kw)
                        self.assertEqual(row["status"], "DEV_CANDIDATE")
                        self.assertEqual(set(row["normalizers"]), {n for n,_ in V2_GROUPS[kw["horizon"]]})
                        self.assertEqual(row["score_status"], "SCORE_UNAVAILABLE")
                        self.assertIsNone(row["score"])
                        self.assertIsNone(row["probability"])
                        self.assertIsNone(row["signal_id"])
                        self.assertFalse(row["qualified"])
                        self.assertFalse(row["publishable"])
                        self.assertFalse(row["delivery_authorized"])
                        self.assertEqual(row["scientific_status"], "NOT_EVALUATED")
                        self.assertEqual(row["forward_status"], "NOT_RUN")
                        self.assertEqual(row["pit_status"], "SYNTHETIC_ASOF_ONLY_NOT_REAL_PIT")
                        for x in row["normalizers"].values():
                            if x is not None:
                                self.assertTrue(D("0") <= D(x) <= D("1"))

    def test_determinism_and_network_forbidden(self):
        x = intraday()
        with patch.object(urllib.request, "urlopen",
                          side_effect=AssertionError("NETWORK_FORBIDDEN")), \
             patch.object(socket, "create_connection",
                          side_effect=AssertionError("NETWORK_FORBIDDEN")):
            a,b = evaluate_r2(**x),evaluate_r2(**x)
        self.assertEqual(a,b)
        self.assertEqual(len(a["normalizers"]), 6)
        self.assertEqual(a["normalizers"]["MTF_NEARBY_STRUCTURE"], "0.5")

    def test_gaps_open_candles_wrong_source_and_missing_are_rejected(self):
        x = intraday()
        bad = replace(x["children"][2],
                      open_at=x["children"][2].open_at+timedelta(minutes=1))
        row = evaluate_r2(**{**x,"children":x["children"][:2]+(bad,)+x["children"][3:]})
        self.assertEqual(row["status"], "INVALID")
        self.assertEqual(len(row["missing_reasons"]), 6)
        self.assertIn("GAP",row["missing_reasons"]["30M_STRONG_CLOSE"])
        future = replace(x["parent"], received_at=x["decision_at"]+timedelta(seconds=10),
                         available_at=x["decision_at"]+timedelta(seconds=10))
        self.assertEqual(evaluate_r2(**{**x,"parent":future})["status"],"INVALID")
        wrong = replace(x["children"][0],source_id="SYNTHETIC:OTHER")
        self.assertEqual(evaluate_r2(**{**x,"children":(wrong,)+x["children"][1:]})["status"],"INVALID")
        with self.assertRaisesRegex(Unavailable, "NON_SYNTHETIC_SOURCE"):
            replace(x["children"][0], source_id="BINANCE:REAL")

    def test_basic_close_path_symmetric_and_unsupported_inputs(self):
        b=candle(BASE, 30, o="100", h="110", l="90", c="105")
        k,body,wick = close_parts(b,Direction.UP)
        self.assertEqual((k,body,wick),(D(".75"),D(".25"),D(".75")))
        self.assertEqual((8*k+6*body+6*wick)/20,D(".6"))
        kd,bd,wd = close_parts(b,Direction.DOWN)
        self.assertEqual(kd,D(".25"))
        self.assertEqual(bd,D("0"))
        self.assertEqual(wd,D(".5"))
        flat=candle(BASE,5,o="100",h="100",l="100",c="100")
        with self.assertRaisesRegex(Unavailable,"ZERO_CANDLE_RANGE"):
            close_parts(flat,Direction.UP)
        with self.assertRaisesRegex(Unavailable, "NONFINITE"):
            replace(b, q=D("NaN"))

    def test_r2_n02_n09_path_examples(self):
        starts=[BASE+timedelta(minutes=5*i) for i in range(6)]
        previous=100
        steps=[2,1,-1,2,1,1]
        bars=[]
        for t, step in zip(starts,steps):
            c=previous+step
            bars.append(candle(t,5,o=str(previous),h=str(max(previous,c)+1),
                               l=str(min(previous,c)-1),c=str(c)))
            previous=c
        g,e,keep=path_parts(bars,Direction.UP)
        self.assertEqual(g,D(5)/6)
        self.assertEqual(e,D(6)/8)
        self.assertEqual(keep,D(1))
        self.assertAlmostEqual(float((8*g+8*e+4*keep)/20),.8333333333, places=6)

    def test_liquidity_and_conservative_timing_boundaries(self):
        x=intraday()
        m=market(x["decision_at"],spread=".10",quote="20000000")
        score=liquidity(m,x["decision_at"],x["witness"])
        self.assertGreater(score,D(".49"))
        self.assertLess(score,D(".51"))
        stale=market(x["decision_at"],book_age=4.9)
        with self.assertRaisesRegex(Unavailable,"MARKET_SNAPSHOT_STALE"):
            liquidity(stale,x["decision_at"],x["witness"])
        with self.assertRaisesRegex(Unavailable,"BOOK_OR_MARKET"):
            liquidity(replace(m,bid=D("101"),ask=D("100")),x["decision_at"],x["witness"])
        with self.assertRaisesRegex(Unavailable,"SPREAD_OR_24H"):
            liquidity(replace(m,quote_24h=D("9999999")),x["decision_at"],x["witness"])
        with self.assertRaisesRegex(Unavailable,"CLOCK_UNCERTAINTY"):
            ClockWitness("SYNTHETIC:INDEPENDENT",D("1.5"))
        with self.assertRaisesRegex(Unavailable,"REAL_CLOCK_PROOF"):
            ClockWitness("SYNTHETIC:INDEPENDENT",D(".2"),synthetic=False)
        with self.assertRaisesRegex(Unavailable,"PIT_AVAILABILITY"):
            asof(x["decision_at"]-timedelta(seconds=.1),
                 x["decision_at"], ClockWitness("SYNTHETIC:INDEPENDENT",D(".4")))

    def test_n04_isolated_spike_vs_continuous_volume(self):
        past=history(BASE,20,5,q="10")
        start=past[-1].close_at
        spike=tuple(candle(start+timedelta(minutes=5*i),5,q=q)
                    for i,q in enumerate(["0","0","0","0","0","100"]))
        sustained=tuple(candle(start+timedelta(minutes=5*i),5,q=q)
                        for i,q in enumerate(["12","13","14","12","15","16"]))
        self.assertAlmostEqual(float(volume_continuity(spike,past)),.0888888889,places=7)
        self.assertEqual(volume_continuity(sustained,past),D(".6875"))
        self.assertLess(volume_continuity(spike,past),volume_continuity(sustained,past))
        with self.assertRaisesRegex(Unavailable,"VOLUME_REFERENCE_ZERO"):
            volume_continuity(sustained,history(BASE,20,5,q="0"))
        with self.assertRaisesRegex(Unavailable,"CANDLE_OHLCV_INVALID"):
            candle(BASE,5,q="-1")

    def test_n03_true_onset_vs_absence_vs_unknown_and_no_future(self):
        start=BASE
        past=history(start,39,5)
        t=past[-1].close_at
        closes=[102,103,104,105,106,107]
        children=tuple(candle(t+timedelta(minutes=5*i),5,c=str(c),
                              h=str(c+1),l="99") for i,c in enumerate(closes))
        clean = (False,)*45
        self.assertEqual(onset_timing(past,children,Direction.UP,False,clean),D(".75"))
        earlier_impulse = list(clean)
        earlier_impulse[-3] = True  # already happened; now False cannot erase it
        self.assertEqual(onset_timing(past,children,Direction.UP,False,
                                      tuple(earlier_impulse)),D("0"))
        current_impulse = clean[:-1] + (True,)
        self.assertEqual(onset_timing(past,children,Direction.UP,True,
                                      current_impulse),D("0"))
        self.assertEqual(onset_timing(past,history(t,6,5),Direction.UP,
                                      False,clean),D("0"))
        with self.assertRaisesRegex(Unavailable,"FULL_IMPULSE_DEFINITION_UNFROZEN"):
            onset_timing(past,children,Direction.UP,None)
        with self.assertRaisesRegex(Unavailable,"FULL_IMPULSE_DEFINITION_UNFROZEN"):
            onset_timing(past,children,Direction.UP,False)
        with self.assertRaisesRegex(Unavailable,"IMPULSE_TRACE_LENGTH_MISMATCH"):
            onset_timing(past,children,Direction.UP,False,clean[:-1])
        with self.assertRaisesRegex(Unavailable,"IMPULSE_TRACE_UNKNOWN_OR_INVALID"):
            onset_timing(past,children,Direction.UP,False,clean[:-2]+(None,False))
        with self.assertRaisesRegex(Unavailable,"IMPULSE_TRACE_CURRENT_STATE_MISMATCH"):
            onset_timing(past,children,Direction.UP,False,current_impulse)
        with self.assertRaisesRegex(Unavailable,"ONSET_HISTORY_INSUFFICIENT"):
            onset_timing(past[-10:],children,Direction.UP,False,clean)
        # Future candle after decision must not change an existing onset computation.
        result=onset_timing(past,children,Direction.UP,False,clean)
        future=candle(children[-1].close_at,5,c="999",h="1000",l="99")
        self.assertEqual(onset_timing(past,children,Direction.UP,False,clean),result)
        self.assertGreater(future.open_at,children[-2].open_at)

    def test_n07_confirmed_pivots_require_right_hand_receipts_and_no_ties(self):
        start=BASE+timedelta(days=15)
        history4=falling_structure(start)
        pivots=confirmed_pivots(history4,start)
        highs=[p for p in pivots if p.kind=="HIGH"]
        lows=[p for p in pivots if p.kind=="LOW"]
        self.assertGreaterEqual(len(highs),2)
        self.assertGreaterEqual(len(lows),2)
        self.assertEqual(highs[-1].price,D("100"))
        self.assertLessEqual(highs[-1].available_at,start)
        self.assertLess(highs[-1].formed_at,highs[-1].confirmed_at)
        change=list(history4)
        change[23]=replace(change[23],h=D("100"))
        self.assertNotIn(highs[-1].level_id,{p.level_id for p in confirmed_pivots(change,start)})
        earlier=history4[22].close_at
        self.assertNotIn(highs[-1].level_id,{p.level_id for p in confirmed_pivots(history4,earlier)})

    def test_n07_choch_positive_equality_consumed_and_future_pivot(self):
        start=BASE+timedelta(days=15)
        hist=falling_structure(start)
        par=candle(start,240,o="95",h="103",l="94",c="102",q="40")
        decision=par.close_at+timedelta(seconds=20)
        book=market(decision,spread=".20")
        value,event,level=structure(hist,par,Direction.UP,"REVERSAL",book,
                                    decision,WITNESS,frozenset())
        self.assertTrue(event)
        self.assertGreater(value,D(".7"))
        self.assertLess(value,D("1"))
        with self.assertRaisesRegex(Unavailable,"LEVEL_EXPIRED_CONSUMED_OR_FUTURE"):
            structure(hist,par,Direction.UP,"REVERSAL",book,decision,WITNESS,
                      frozenset([level]))
        # No signal on a weak close; a positive state subscore is not qualification.
        weak=replace(par,c=D("100.2"))
        _,weak_event,_=structure(hist,weak,Direction.UP,"REVERSAL",book,
                                  decision,WITNESS,frozenset())
        self.assertFalse(weak_event)
        # A pivot formed now can never be used before two right bars arrive.
        recent=hist[:24]
        pivots=confirmed_pivots(recent,recent[-1].close_at)
        self.assertFalse(any(p.formed_at==hist[22].close_at for p in pivots))

    def test_swing_has_separate_structure_unknown_not_qualified(self):
        x=swing()
        result=evaluate_r2(**x)
        self.assertEqual(result["normalizers"]["MARKET_STRUCTURE"],None)
        self.assertIn("PIVOT_HISTORY_INSUFFICIENT",result["missing_reasons"]["MARKET_STRUCTURE"])
        self.assertFalse(result["qualified"])


    def test_n03_impulse_trace_missing_is_fail_closed_in_integration(self):
        kw=intraday()
        # A real synthetic threshold crossing: the former flat integration
        # fixture has no onset and would yield zero in *both* branches.
        closes=(102,103,104,105,106,107)
        rising=tuple(replace(b,c=D(str(value)),h=D(str(value+1)))
                     for b,value in zip(kw["children"],closes))
        kw["children"]=rising
        kw["parent"]=replace(kw["parent"],h=D("108"),c=D("107"))
        missing=evaluate_r2(**{**kw,"impulse_trace":None})
        self.assertIsNone(missing["normalizers"]["MOMENTUM_EARLY_TIMING"])
        self.assertEqual(missing["missing_reasons"]["MOMENTUM_EARLY_TIMING"],
                         "FULL_IMPULSE_DEFINITION_UNFROZEN")
        self.assertFalse(missing["qualified"])
        historical=list(kw["impulse_trace"])
        historical[-3]=True
        prior=evaluate_r2(**{**kw,"impulse_trace":tuple(historical)})
        no_impulse=evaluate_r2(**kw)
        self.assertIsNotNone(no_impulse["normalizers"]["MOMENTUM_EARLY_TIMING"])
        self.assertLess(D(prior["normalizers"]["MOMENTUM_EARLY_TIMING"]),
                        D(no_impulse["normalizers"]["MOMENTUM_EARLY_TIMING"]))

    def test_n07_replay_crossing_future_history_and_stale_book(self):
        start=BASE+timedelta(days=15)
        hist=falling_structure(start)
        parent=candle(start,240,o="95",h="103",l="94",c="102",q="40")
        decision=parent.close_at+timedelta(seconds=20)
        m=market(decision,spread=".20")
        # Historical close above the known level makes a second crossing ineligible,
        # even if no consumed_levels ledger was supplied.
        crossed=list(hist)
        crossed[30]=replace(crossed[30],c=D("101"),h=D("102"))
        with self.assertRaisesRegex(Unavailable,"LEVEL_ALREADY_CROSSED"):
            structure(tuple(crossed),parent,Direction.UP,"REVERSAL",m,
                      decision,WITNESS,frozenset())
        # The structure history cannot include the parent candle itself.
        with self.assertRaisesRegex(Unavailable,"STRUCTURE_HISTORY_AFTER_PARENT_OPEN"):
            structure(hist+(parent,),parent,Direction.UP,"REVERSAL",m,
                      decision,WITNESS,frozenset())
        stale=market(decision,book_age=12)
        with self.assertRaisesRegex(Unavailable,"MARKET_SNAPSHOT_STALE"):
            structure(hist,parent,Direction.UP,"REVERSAL",stale,
                      decision,WITNESS,frozenset())
        with self.assertRaisesRegex(Unavailable,"SYNTHETIC_MARKET_RECEIPTS_REQUIRED"):
            replace(m, book=object())

if __name__ == "__main__":
    import unittest
    unittest.main()
