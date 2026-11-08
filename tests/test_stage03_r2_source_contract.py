"""PM 6707403159: four minimal synthetic source/definition controls, no network."""
from __future__ import annotations

import socket
import urllib.request
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase
from unittest.mock import patch

from test_stage03_r2_offline import candle, intraday, swing, WITNESS
from test_stage03_r2_functional import stage03_inputs
from zs_smart_gate.core import Candle as CoreCandle, MarketSnapshot
from zs_smart_gate.mtf_contracts import CandleWindow, ReconciliationTolerance
from zs_smart_gate.stage03a_contracts import Direction, Horizon
from zs_smart_gate.stage03_r2_offline import Unavailable
from zs_smart_gate.stage03_r2_functional import stage03_r2_functional_e2e
from zs_smart_gate.stage03_r2_source_contract import (
    BookTickerPacket, Ticker24Packet, ModeSourceEvidence, ImpulseState,
    VersionedFullImpulsePredicate, CausalImpulseObservation,
    inspect_full_impulse_trace, market_from_explicit_packets, require_prior_mode,
)


def packet_pair(x):
    m = x["market"]
    return (
        BookTickerPacket("BTCUSDT", "USDT", "TRADING", True,
                         m.bid, m.ask, m.book),
        Ticker24Packet("BTCUSDT", "USDT", m.quote_24h, "USDT",
                       "ROLLING_24H", m.ticker24),
    )


def trace_bundle(x):
    candles = tuple(x["context"]["5m"][-39:]) + tuple(x["children"])
    definition = VersionedFullImpulsePredicate(
        "SYNTHETIC:DEFINITION_NOT_SCIENTIFICALLY_APPROVED", "DEV_ONLY_V1",
        "a"*64, "5m", x["direction"], x["horizon"], x["mode"])
    rows = tuple(CausalImpulseObservation(
        b.open_at, b.close_at, b.close_at, b.received_at, b.available_at,
        x["decision_at"], b.source_id, ImpulseState.FALSE) for b in candles)
    return definition, rows, candles


def mode_evidence(x):
    parent_open = x["parent"].open_at
    context_close = parent_open - timedelta(hours=4)
    return ModeSourceEvidence(
        x["mode"], x["direction"], x["horizon"],
        "SYNTHETIC:INDEPENDENT_MODE_INPUT_NOT_INFERRED_FROM_N10",
        "DEV_MODE_V1", "SYNTHETIC:MODE_SOURCE",
        context_close, context_close + timedelta(seconds=1),
        context_close + timedelta(seconds=2),
        context_close + timedelta(seconds=3), x["decision_at"])


def swing_readiness(x):
    p = x["parent"]
    def window(b, timeframe, base):
        return CandleWindow(
            timeframe, b.open_at, b.close_at, b.received_at, b.available_at,
            b.source_id, b.o, b.h, b.l, b.c, D(base), b.q)
    parent = window(p, "4h", "40")
    children = tuple(window(b, "1h", "10") for b in x["children"])
    start = p.close_at - timedelta(minutes=105)
    core = tuple(CoreCandle(
        b.open_at, b.close_at, b.received_at, b.available_at,
        b.o, b.h, b.l, b.c, D("10"), b.q)
        for b in (candle(start+timedelta(minutes=5*i), 5) for i in range(21)))
    m = x["market"]
    mv = MarketSnapshot("BTCUSDT", "USDT", True, "TRADING", m.quote_24h,
                        m.bid, m.ask, x["decision_at"])
    return dict(
        symbol="BTCUSDT", horizon=Horizon.SWING, direction=x["direction"],
        parent=parent, children=children, core_5m=core, market=mv,
        decision_at=x["decision_at"],
        tolerance=ReconciliationTolerance("0", "0", "0", "SYNTHETIC_009B_EXACT"),
        event_discriminator="009B-SWING-SYNTHETIC")


class Stage03MinimalSourceContractTests(TestCase):
    def test_n03_explicit_true_false_unknown_and_causal_receipt(self):
        x = intraday()
        definition, rows, bars = trace_bundle(x)
        reviewed = inspect_full_impulse_trace(
            definition=definition, trace=rows, candles=bars,
            direction=x["direction"], horizon=x["horizon"], mode=x["mode"],
            decision_at=x["decision_at"], witness=x["witness"])
        self.assertEqual(reviewed["observations"], 45)
        self.assertEqual(reviewed["n03_status"], "UNAVAILABLE")
        self.assertFalse(reviewed["full_impulse_event_approved"])
        self.assertEqual(reviewed["definition_status"], "UNAPPROVED")
        # An observed TRUE is a datum, not an approved scientific definition.
        known_true = rows[:-1] + (replace(rows[-1], state=ImpulseState.TRUE),)
        self.assertEqual(inspect_full_impulse_trace(
            definition=definition, trace=known_true, candles=bars,
            direction=x["direction"], horizon=x["horizon"], mode=x["mode"],
            decision_at=x["decision_at"], witness=x["witness"])["n03_status"],
            "UNAVAILABLE")
        with self.assertRaisesRegex(Unavailable, "FULL_IMPULSE_TRACE_UNKNOWN"):
            inspect_full_impulse_trace(
                definition=definition,
                trace=rows[:-1] + (replace(rows[-1], state=ImpulseState.UNKNOWN),),
                candles=bars, direction=x["direction"], horizon=x["horizon"],
                mode=x["mode"], decision_at=x["decision_at"], witness=x["witness"])
        late = rows[:-1] + (replace(
            rows[-1], observed_at=x["decision_at"]-timedelta(milliseconds=80),
            received_at=x["decision_at"]-timedelta(milliseconds=70),
            available_at=x["decision_at"]-timedelta(milliseconds=60)),)
        with self.assertRaisesRegex(Unavailable,"PIT_AVAILABILITY_NOT_BEFORE_DECISION"):
            inspect_full_impulse_trace(
                definition=definition, trace=late, candles=bars,
                direction=x["direction"], horizon=x["horizon"], mode=x["mode"],
                decision_at=x["decision_at"], witness=x["witness"])
        with self.assertRaisesRegex(Unavailable, "IMPULSE_DEFINITION_APPROVAL_NOT_AUTHORIZED"):
            replace(definition, definition_status="APPROVED")

    def test_n06_n12_packets_preserve_two_receipts_and_reject_units_time(self):
        for factory in (intraday, swing):
            x = factory()
            book, ticker = packet_pair(x)
            with self.subTest(factory=factory.__name__):
                out = market_from_explicit_packets(
                    book=book, ticker=ticker, decision_at=x["decision_at"],
                    witness=x["witness"])
                self.assertEqual(out, x["market"])
                self.assertEqual(out.ticker24_unit, "USDT")
                self.assertEqual(out.ticker24_window, "ROLLING_24H")
                with self.assertRaisesRegex(Unavailable, "UNIT_OR_WINDOW"):
                    market_from_explicit_packets(
                        book=book, ticker=replace(ticker, volume_unit="BTC"),
                        decision_at=x["decision_at"], witness=x["witness"])
                with self.assertRaisesRegex(Unavailable, "SYMBOL_OR_QUOTE_CONFLICT"):
                    market_from_explicit_packets(
                        book=book, ticker=replace(ticker, symbol="ETHUSDT"),
                        decision_at=x["decision_at"], witness=x["witness"])
                with self.assertRaisesRegex(Unavailable, "PIT_AVAILABILITY"):
                    market_from_explicit_packets(
                        book=book, ticker=replace(
                            ticker, receipt=replace(
                                ticker.receipt, available_at=x["decision_at"]+
                                timedelta(seconds=1))),
                        decision_at=x["decision_at"], witness=x["witness"])

    def test_n07_n10_mode_source_asof_and_scope_no_inference(self):
        x = swing()
        mode = mode_evidence(x)
        proof = require_prior_mode(
            mode, mode=x["mode"], direction=x["direction"],
            horizon=x["horizon"], parent=x["parent"],
            decision_at=x["decision_at"], witness=x["witness"])
        self.assertEqual(proof["status"], "SYNTHETIC_ASOF_CHECKED_NOT_REAL_PIT")
        with self.assertRaisesRegex(Unavailable, "MODE_SOURCE_EVIDENCE_MISSING"):
            require_prior_mode(
                None, mode=x["mode"], direction=x["direction"],
                horizon=x["horizon"], parent=x["parent"],
                decision_at=x["decision_at"], witness=x["witness"])
        with self.assertRaisesRegex(Unavailable, "MODE_SOURCE_SCOPE_OR_DECISION_MISMATCH"):
            require_prior_mode(
                replace(mode, mode="CONTINUATION"), mode=x["mode"],
                direction=x["direction"], horizon=x["horizon"],
                parent=x["parent"], decision_at=x["decision_at"], witness=x["witness"])
        with self.assertRaisesRegex(Unavailable, "PIT_AVAILABILITY"):
            require_prior_mode(
                replace(mode, available_at=x["parent"].open_at+
                        timedelta(seconds=1)), mode=x["mode"],
                direction=x["direction"], horizon=x["horizon"],
                parent=x["parent"], decision_at=x["decision_at"], witness=x["witness"])

    def test_one_bounded_stage03_e2e_with_contracts_and_fail_closed(self):
        x = intraday()
        y = stage03_inputs(x)
        definition, trace, _bars = trace_bundle(x)
        pair = packet_pair(x)
        with patch.object(socket, "create_connection", side_effect=AssertionError("NO_NETWORK")), \
             patch.object(urllib.request, "urlopen", side_effect=AssertionError("NO_NETWORK")):
            good = stage03_r2_functional_e2e(
                r2_inputs=x, readiness_inputs=y,
                full_impulse_definition=definition, full_impulse_trace=trace,
                market_source_packets=pair)
            repeat = stage03_r2_functional_e2e(
                r2_inputs=x, readiness_inputs=y,
                full_impulse_definition=definition, full_impulse_trace=trace,
                market_source_packets=pair)
            self.assertEqual(good, repeat)
            self.assertEqual(good["status"], "RESEARCH_CANDIDATE")
            self.assertEqual(good["market_source_review"]["status"],
                             "SYNTHETIC_PACKETS_VALID_NOT_REAL_PIT")
            self.assertEqual(good["full_impulse_trace_review"]["n03_status"],
                             "UNAVAILABLE")
            self.assertIsNone(good["r2"]["normalizers"]["MOMENTUM_EARLY_TIMING"])
            self.assertFalse(good["publishable"])
            self.assertIsNone(good["signal_id"])
            self.assertIsNone(good["score"])
            self.assertEqual(good["market_requests"], 0)
            bad = stage03_r2_functional_e2e(
                r2_inputs=x, readiness_inputs=y, market_source_packets=(
                    pair[0], replace(pair[1], window="FIXED_24H")))
            self.assertEqual(bad["status"], "REJECTED")
            self.assertIn("TICKER_24H_QUOTE_UNIT_OR_WINDOW_INVALID",
                          bad["source_match_reasons"][0])
            self.assertIsNone(bad["r2"]["normalizers"]["LIQUIDITY_QUALITY"])
        sw = swing()
        sy = swing_readiness(sw)
        known = stage03_r2_functional_e2e(
            r2_inputs=sw, readiness_inputs=sy, mode_source_evidence=mode_evidence(sw),
            market_source_packets=packet_pair(sw))
        unknown = stage03_r2_functional_e2e(
            r2_inputs=sw, readiness_inputs=sy, market_source_packets=packet_pair(sw))
        self.assertEqual(known["status"], "RESEARCH_CANDIDATE")
        self.assertIsNotNone(known["r2"]["normalizers"]["DAILY_WEEKLY_CONTEXT"])
        self.assertIsNone(unknown["r2"]["normalizers"]["DAILY_WEEKLY_CONTEXT"])
        self.assertEqual(unknown["r2"]["missing_reasons"]["DAILY_WEEKLY_CONTEXT"],
                         "MODE_SOURCE_EVIDENCE_MISSING")
        self.assertFalse(known["r2"]["structural_event"])
        self.assertFalse(unknown["publishable"])
