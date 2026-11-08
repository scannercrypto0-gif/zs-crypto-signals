"""Targeted offline contract integration for the new source-preserving bridge."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase
from unittest.mock import patch

from test_stage03_r2_offline import intraday, swing, falling_structure
from test_stage03_r2_functional import stage03_inputs
from test_stage03_r2_source_contract import (
    packet_pair, swing_readiness, mode_evidence,
)
from zs_smart_gate.mtf_contracts import CandleWindow, ReconciliationTolerance
from zs_smart_gate.stage03a_contracts import Direction
from zs_smart_gate.stage03_r2_offline import Unavailable
from zs_smart_gate.stage03_r2_closed_bundle import stage03_r2_from_closed_bundle


def sample(x, readiness):
    source = readiness["parent"].source_id
    def typed(bar, frame):
        return CandleWindow(
            frame, bar.open_at, bar.close_at, bar.received_at,
            bar.available_at, source, bar.o, bar.h, bar.l, bar.c,
            D("10"), bar.q)
    frames = {key: ("4h" if key == "structure4h" else key)
              for key in x["context"]}
    contexts = {key: tuple(typed(b, frames[key]) for b in history)
                for key, history in x["context"].items()}
    core = tuple(CandleWindow.from_five_minute(c, source_id=source)
                 for c in readiness["core_5m"])
    book, ticker = packet_pair(x)
    ticker = replace(ticker, base_volume=D("250"))
    return dict(
        symbol="BTCUSDT", horizon=x["horizon"], direction=x["direction"],
        mode=x["mode"], parent=readiness["parent"],
        children=tuple(readiness["children"]), core_5m=core,
        context=contexts, book=book, ticker24=ticker,
        witness=x["witness"], decision_at=x["decision_at"],
        tolerance=ReconciliationTolerance(
            "0", "0", "0", "SYNTHETIC_SOURCE_PRESERVING_BUNDLE"),
        event_discriminator="BUNDLE-SYNTHETIC-ONCE",
    )


class ClosedSourceBundleIntegration(TestCase):
    def test_intraday_01_03a_r2_one_input_deterministic_no_production(self):
        x = intraday()
        data = sample(x, stage03_inputs(x))
        with patch("socket.create_connection", side_effect=AssertionError("NO_NETWORK")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("NO_NETWORK")):
            a = stage03_r2_from_closed_bundle(**data)
            b = stage03_r2_from_closed_bundle(**data)
        self.assertEqual(a, b)
        self.assertEqual(a["status"], "RESEARCH_CANDIDATE")
        self.assertEqual(a["market_source_review"]["status"],
                         "SYNTHETIC_PACKETS_VALID_NOT_REAL_PIT")
        self.assertEqual(a["r2"]["status"], "DEV_CANDIDATE")
        self.assertIsNone(a["r2"]["normalizers"]["MOMENTUM_EARLY_TIMING"])
        self.assertIsNotNone(a["r2"]["normalizers"]["VOLUME_CONTINUITY"])
        self.assertIsNotNone(a["r2"]["normalizers"]["LIQUIDITY_QUALITY"])
        self.assertEqual(a["source_match_reasons"], [])
        self.assertEqual(len(a["packet_sha256"]), 64)
        self.assertIsNone(a["score"])
        self.assertIsNone(a["signal_id"])
        self.assertFalse(a["publishable"])
        self.assertFalse(a["delivery_authorized"])
        self.assertEqual(a["market_requests"], 0)

    def test_reject_base_volume_tamper_foreign_context_and_untrusted_market(self):
        data = sample(intraday(), stage03_inputs(intraday()))
        core = list(data["core_5m"])
        core[-1] = replace(core[-1], base_volume=D("999"))
        with self.assertRaisesRegex(Unavailable, "BUNDLE_CORE_CHILD_SOURCE_OR_BASE_VOLUME_MISMATCH"):
            stage03_r2_from_closed_bundle(**dict(data, core_5m=core))
        ctx = dict(data["context"])
        foreign = list(ctx["1h"])
        foreign[-1] = replace(foreign[-1], source_id="SYNTHETIC:FOREIGN")
        ctx["1h"] = tuple(foreign)
        with self.assertRaisesRegex(Unavailable, "BUNDLE_CANDLE_SOURCE_MISMATCH"):
            stage03_r2_from_closed_bundle(**dict(data, context=ctx))
        with self.assertRaisesRegex(Unavailable, "BUNDLE_24H_BASE_VOLUME_EXPLICIT_REQUIRED"):
            stage03_r2_from_closed_bundle(**dict(
                data, ticker24=replace(data["ticker24"], base_volume=None)))
        with self.assertRaisesRegex(Unavailable, "TICKER_24H_QUOTE_UNIT_OR_WINDOW_INVALID"):
            stage03_r2_from_closed_bundle(**dict(
                data, ticker24=replace(data["ticker24"], volume_unit="BASE")))

    def test_swing_independent_prior_mode_from_4h_not_n10(self):
        x = swing()
        x["direction"] = Direction.UP
        data = sample(x, swing_readiness(x))
        prior = falling_structure(x["parent"].open_at - timedelta(hours=4))
        prior_window = tuple(CandleWindow(
            "4h", b.open_at, b.close_at, b.received_at, b.available_at,
            b.source_id, b.o, b.h, b.l, b.c, D("10"), b.q,
        ) for b in prior)
        data["prior_mode_4h"] = prior_window
        row = stage03_r2_from_closed_bundle(**data)
        self.assertEqual(row["status"], "RESEARCH_CANDIDATE")
        self.assertEqual(row["mode_evidence_review"]["mode"], "REVERSAL")
        self.assertIsNotNone(row["r2"]["normalizers"]["DAILY_WEEKLY_CONTEXT"])
        self.assertIsNone(row["signal_id"])
        with self.assertRaisesRegex(Unavailable, "BUNDLE_INDEPENDENT_MODE_CONFLICT"):
            stage03_r2_from_closed_bundle(**dict(data, mode="CONTINUATION"))
        with self.assertRaisesRegex(Unavailable, "BUNDLE_TWO_MODE_AUTHORITIES_FORBIDDEN"):
            stage03_r2_from_closed_bundle(**dict(data,
                mode_source_evidence=mode_evidence(x)))
