"""03B1 deterministic real-core/03A E2E with simulated Binance GET transport.

Never uses the network. Fixture uses exchange inclusive closeTime and
real-source-like receipt metadata; the LIVE Actions workflow is separate.
"""
from __future__ import annotations

import dataclasses
import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from zs_smart_gate.binance_live import LiveBlocked, LiveFailure
from zs_smart_gate.core import MarketSnapshot, score_v1_partial
from zs_smart_gate.mtf_contracts import CandleWindow, ReconciliationTolerance, reconcile
from zs_smart_gate.research_metrics import Metric, VERSION, describe
from zs_smart_gate.stage03a_contracts import Direction, Horizon
from zs_smart_gate.stage03b1_live import (
    CONFIG, SOURCE_ID, deviations, parse_kline, probe_once,
)

UTC = timezone.utc
ANCHOR = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
NOW = ANCHOR + timedelta(minutes=15)
NOW_MS = int(NOW.timestamp() * 1000)


def kline(start_ms, duration_ms, *, base="10", quote="1000"):
    return [start_ms, "100", "102", "99", "101", base,
            start_ms + duration_ms - 1, quote, 42, "4", "400", "0"]


class FixtureTransport:
    """Every request records its actual physical send with the pre-send hook."""

    def __init__(self, horizon=Horizon.INTRADAY):
        self.horizon = horizon
        self.calls = []
        self.physical = 0
        self.fail_path = None
        self.invalid_mode = None
        self.receipts = []

    def __call__(self, path, params=None, *, on_attempt=None):
        on_attempt(path)
        self.physical += 1
        self.calls.append((path, params))
        if self.fail_path == path:
            # Two physical sends model a network retry and terminal block.
            on_attempt(path)
            self.physical += 1
            raise LiveBlocked("NETWORK_UNAVAILABLE_FAKE")
        idx = self.physical
        received = NOW_MS + 100 + idx * 10
        start = NOW_MS + idx * 10
        meta = {"path": path, "http_status": 200, "latency_ms": 10,
                "t0_local_ms": start, "received_local_ms": received,
                "used_weight_1m": str(10 + idx)}
        if path == "/api/v3/time":
            return {"serverTime": NOW_MS}, meta
        if path == "/api/v3/exchangeInfo":
            return {"symbols": [{"symbol": "BTCUSDT", "quoteAsset": "USDT",
                                 "status": "TRADING",
                                 "isSpotTradingAllowed": True}]}, meta
        if path == "/api/v3/ticker/24hr":
            return {"symbol": "BTCUSDT", "quoteVolume": "50000000"}, meta
        if path == "/api/v3/ticker/bookTicker":
            return {"symbol": "BTCUSDT", "bidPrice": "100", "askPrice": "100.01"}, meta
        if path != "/api/v3/klines":
            raise AssertionError("unexpected endpoint")
        duration = {"30m": 1_800_000, "4h": 14_400_000,
                    "5m": 300_000, "1h": 3_600_000}[params["interval"]]
        limit = int(params["limit"])
        end = int(params["endTime"]) + 1
        if self.invalid_mode == "missing_child" and params["interval"] in ("5m", "1h"):
            if (self.horizon is Horizon.INTRADAY and params["interval"] == "5m"
                    or self.horizon is Horizon.SWING and params["interval"] == "1h"):
                limit -= 1
        rows = [kline(end - duration*(limit-i), duration)
                for i in range(limit)]
        if params["interval"] in ("30m", "4h"):
            n = 6 if params["interval"] == "30m" else 4
            rows[0][5] = str(n*10)
            rows[0][7] = str(n*1000)
            if self.invalid_mode == "parent_current":
                rows[0][0] += duration
                rows[0][6] += duration
            if self.invalid_mode == "quote_discrepancy":
                rows[0][7] = str(n*1000 + 1)
        if self.invalid_mode == "duplicate_child" and params["interval"] in ("5m","1h"):
            if limit > 2 and ((self.horizon is Horizon.SWING and params["interval"] == "1h")
                              or (self.horizon is Horizon.INTRADAY and params["interval"] == "5m")):
                rows[-2] = rows[-3][:]
        if self.invalid_mode == "late_clock" and params["interval"] in ("30m", "4h"):
            meta["received_local_ms"] = int(ANCHOR.timestamp()*1000) - 60_000
        return rows, meta


class LiveProbeFixtureTests(unittest.TestCase):
    def probe(self, horizon=Horizon.INTRADAY, fake=None, **kw):
        getter = fake or FixtureTransport(horizon)
        return probe_once(horizon=horizon, symbol="BTCUSDT", getter=getter,
                          local_ms=lambda: NOW_MS + 1000, **kw)

    def test_intraday_real_core_mtf_identity_both_directions_e2e(self):
        fake = FixtureTransport()
        result = self.probe(fake=fake)
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["reconciliation"]["status"], "PASS")
        self.assertEqual(result["coverage"]["child_candles_fetched"], 6)
        self.assertEqual(result["coverage"]["core_5m_candles"], 21)
        self.assertEqual(result["measurements"]["physical_http_attempts"], 6)
        self.assertEqual(fake.physical, 6)
        self.assertEqual(set(result["research_metrics"]), {"UP", "DOWN"})
        self.assertEqual(len(result["research_events"]), 2)
        self.assertTrue(all(not e["publishable"] and e["signal_id"] is None
                            for e in result["research_events"]))
        self.assertEqual(result["candidate"]["status"], "ELIGIBLE")
        self.assertIsNone(result["candidate"]["score"])
        self.assertIsNone(result["score"])
        self.assertFalse(result["source_publication_time_known"])
        self.assertEqual(result["signed_parent_minus_children_deltas"]["quote_volume"], "0")
        self.assertEqual(json.loads(json.dumps(result))["status"], "PASS")

    def test_swing_four_hour_core_and_four_one_hour_e2e(self):
        fake = FixtureTransport(Horizon.SWING)
        result = self.probe(Horizon.SWING, fake)
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["coverage"]["child_candles_fetched"], 4)
        self.assertEqual(result["coverage"]["core_5m_candles"], 21)
        self.assertEqual(result["measurements"]["physical_http_attempts"], 7)
        self.assertEqual(result["parent_frame"], "4h")
        self.assertEqual(result["reconciliation"]["parent_close_at"], ANCHOR.isoformat())
        self.assertEqual(set(result["research_metrics"]), {"UP", "DOWN"})

    def test_fixture_utc_alignment_and_inclusive_end(self):
        start = datetime(2026,10,28,11,30,tzinfo=UTC)
        rec = ANCHOR+timedelta(minutes=1)
        candle = parse_kline(kline(int(start.timestamp()*1000), 1_800_000),
                             "30m", rec)
        self.assertEqual(candle.open_at, start)
        self.assertEqual(candle.close_at, ANCHOR)
        self.assertEqual(candle.errors_at(rec), ())
        with self.assertRaisesRegex(LiveFailure, "TIME_SEMANTICS"):
            wrong = kline(int(start.timestamp()*1000), 1_800_000)
            wrong[6] += 1
            parse_kline(wrong,"30m",rec)

    def test_partial_parent_from_exchange_fails_closed(self):
        fake = FixtureTransport()
        fake.invalid_mode = "parent_current"
        result = self.probe(fake=fake)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("PARENT_ANCHOR_MISMATCH", result["reason"])
        self.assertEqual(result["research_events"], [])

    def test_missing_child_history_fails_closed(self):
        for horizon in Horizon:
            fake = FixtureTransport(horizon)
            fake.invalid_mode = "missing_child"
            result = self.probe(horizon, fake)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("COVERAGE_MISSING", result["reason"])
            self.assertEqual(result["research_events"], [])

    def test_duplicate_child_fails_integrity_and_does_not_emit(self):
        for horizon in Horizon:
            fake = FixtureTransport(horizon)
            fake.invalid_mode = "duplicate_child"
            result = self.probe(horizon, fake)
            self.assertEqual(result["status"], "INVALID", result)
            self.assertIn("DUPLICATE_CHILD", result["reconciliation"]["reason_codes"])
            self.assertEqual(result["research_events"], [])
            self.assertEqual(result["research_metrics"], {})

    def test_child_stale_window_is_rejected_not_rebranded(self):
        class StaleChild(FixtureTransport):
            def __call__(self, path, params=None, *, on_attempt=None):
                rows, meta = super().__call__(path, params, on_attempt=on_attempt)
                if path == "/api/v3/klines" and params["interval"] == "1h":
                    for row in rows:
                        row[0] -= 3_600_000
                        row[6] -= 3_600_000
                return rows, meta
        fake = StaleChild(Horizon.SWING)
        result = self.probe(Horizon.SWING, fake)
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PARENT_CHILD_WINDOW_MISMATCH", result["reconciliation"]["reason_codes"])
        self.assertEqual(result["research_events"], [])

    def test_quote_volume_discrepancy_recorded_not_forgiven(self):
        for horizon in Horizon:
            fake = FixtureTransport(horizon)
            fake.invalid_mode = "quote_discrepancy"
            result = self.probe(horizon, fake)
            self.assertEqual(result["status"], "INVALID", result)
            self.assertIn("QUOTE_VOLUME_AGGREGATION_MISMATCH",
                          result["reconciliation"]["reason_codes"])
            self.assertEqual(result["signed_parent_minus_children_deltas"]["quote_volume"], "1")
            self.assertTrue(result["zero_tolerance_is_research_comparison_not_adopted_policy"])

    def test_late_receipt_and_future_parent_never_pass(self):
        fake = FixtureTransport()
        fake.invalid_mode = "late_clock"
        result = self.probe(fake=fake)
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("PARENT_NOT_CLOSED_OR_RECEIPT_ORDER",
                      result["reconciliation"]["reason_codes"])
        self.assertEqual(result["research_events"], [])

    def test_spot_universe_symbol_mismatch_fails_closed(self):
        fake = FixtureTransport()
        result = probe_once(horizon=Horizon.INTRADAY, symbol="ETHUSDT", getter=fake,
                            local_ms=lambda: NOW_MS + 1000)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("SPOT_SYMBOL_MISMATCH", result["reason"])
        self.assertEqual(result["measurements"]["physical_http_attempts"], 4)

    def test_retry_attempts_counted_and_bootstrap_failure_visible(self):
        fake = FixtureTransport()
        fake.fail_path = "/api/v3/klines"
        result = self.probe(fake=fake)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["measurements"]["physical_http_attempts"], 6)
        self.assertEqual(result["measurements"]["logical_calls_succeeded"], 4)
        self.assertEqual(fake.physical, 6)

    def test_eighth_attempt_safety_stop_prevents_ninth(self):
        # The fixture simulates actual retries with four hooks per GET, forcing
        # refusal of any ninth network send before the transport can issue it.
        class Retrying(FixtureTransport):
            def __call__(self, path, params=None, *, on_attempt=None):
                for _ in range(3):
                    on_attempt(path)
                    self.physical += 1
                return super().__call__(path, params, on_attempt=on_attempt)
        fake = Retrying()
        result = self.probe(fake=fake)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["measurements"]["physical_http_attempts"], 8)
        self.assertEqual(fake.physical, 8)
        self.assertIn("BUDGET_EXHAUSTED", result["reason"])

    def test_pre_attempt_soft_guard_blocks_before_send(self):
        ticks = iter([0, 61, 61, 61, 61])
        fake = FixtureTransport()
        result = self.probe(fake=fake, monotonic=lambda: next(ticks))
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["measurements"]["physical_http_attempts"], 0)
        self.assertIn("SOFT_PRE_REQUEST_GUARD", result["reason"])

    def test_v1_unchanged_research_semantics(self):
        baseline = score_v1_partial(Decimal("0"), Decimal("1"), Decimal("0"))
        self.assertEqual(baseline["version"], "V1_PARTIAL_RESEARCH_ONLY")
        self.assertIsNone(baseline["total"])
        self.assertEqual(baseline["status"], "SCORE_UNAVAILABLE")


class PureResearchMetricTests(unittest.TestCase):
    def bars(self, flat=False, zero_volume=False):
        opened = datetime(2026, 10, 28, 11, 30, tzinfo=UTC)
        end = opened + timedelta(minutes=30)
        receipt = end+timedelta(minutes=1)
        opts = dict(open="100", high="100" if flat else "102",
                    low="100" if flat else "99", close="100" if flat else "101",
                    base_volume="0" if zero_volume else "60",
                    quote_volume="0" if zero_volume else "6000")
        parent = CandleWindow("30m",opened,end,receipt,receipt,SOURCE_ID,**opts)
        children=[]
        for i in range(6):
            a=opened+timedelta(minutes=5*i)
            child_opts = {**opts, "base_volume": "0" if zero_volume else "10",
                          "quote_volume": "0" if zero_volume else "1000"}
            children.append(CandleWindow("5m",a,a+timedelta(minutes=5),
                                         receipt,receipt,SOURCE_ID,**child_opts))
        return parent,children,receipt

    def test_up_down_symmetric_without_score(self):
        p,cs,d = self.bars()
        up={m.name:m for m in describe(p,cs,direction=Direction.UP,decision_at=d)}
        down={m.name:m for m in describe(p,cs,direction=Direction.DOWN,decision_at=d)}
        self.assertEqual(up["DIRECTIONAL_PARENT_CLOSE_LOCATION"].value,
                         Decimal(2)/Decimal(3))
        self.assertEqual(down["DIRECTIONAL_PARENT_CLOSE_LOCATION"].value,
                         Decimal(1)/Decimal(3))
        self.assertEqual(up["SIGNED_PARENT_BODY_FRACTION"].value,
                         -down["SIGNED_PARENT_BODY_FRACTION"].value)
        self.assertEqual(up["SIGNED_CHILD_NET_TO_PATH"].value,
                         -down["SIGNED_CHILD_NET_TO_PATH"].value)
        self.assertEqual(up["ABS_PARENT_BODY_FRACTION"].value,
                         down["ABS_PARENT_BODY_FRACTION"].value)
        self.assertEqual(up["SECOND_HALF_QUOTE_VOLUME_SHARE"].value, Decimal("0.5"))
        self.assertEqual(up["DIRECTION_FAVORABLE_QUOTE_VOLUME_SHARE"].value, 1)
        for m in up.values():
            self.assertEqual(m.status,"RESEARCH_METRIC_UNAPPROVED")
            self.assertEqual(m.version, VERSION)
            self.assertEqual(m.source_id, SOURCE_ID)
            self.assertEqual(m.available_at, d)
            self.assertNotIn("score", m.as_dict())

    def test_zero_range_path_and_volume_explicit_missing(self):
        p,cs,d=self.bars(flat=True,zero_volume=True)
        result={m.name:m for m in describe(p,cs,direction=Direction.DOWN,decision_at=d)}
        for field in ("DIRECTIONAL_PARENT_CLOSE_LOCATION","SIGNED_PARENT_BODY_FRACTION",
                      "ABS_PARENT_BODY_FRACTION","ADVERSE_WICK_FRACTION",
                      "SIGNED_CHILD_NET_TO_PATH","SECOND_HALF_QUOTE_VOLUME_SHARE",
                      "DIRECTION_FAVORABLE_QUOTE_VOLUME_SHARE"):
            self.assertIsNone(result[field].value)
            self.assertEqual(result[field].missing_reason,"ZERO_DENOMINATOR")
        self.assertEqual(result["SECOND_MINUS_FIRST_QUOTE_VOLUME"].value, 0)

    def test_metric_rejects_future_and_mismatched_source(self):
        p,cs,d=self.bars()
        cs[0]=dataclasses.replace(cs[0], available_at=d+timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError,"METRIC_INPUT_NOT_PIT_VALID"):
            describe(p,cs,direction=Direction.UP,decision_at=d)
        cs[0]=dataclasses.replace(cs[0], available_at=d, source_id="ANOTHER")
        with self.assertRaisesRegex(ValueError,"METRIC_INPUT_NOT_PIT_VALID"):
            describe(p,cs,direction=Direction.UP,decision_at=d)
        with self.assertRaisesRegex(ValueError,"DIRECTION_ENUM_REQUIRED"):
            describe(p,cs,direction="UP",decision_at=d)

    def test_metric_contract_rejects_unapproved_status_or_nan(self):
        p,cs,d=self.bars()
        m=describe(p,cs,direction=Direction.UP,decision_at=d)[0]
        with self.assertRaisesRegex(ValueError, "METRIC_APPROVAL_NOT_AUTHORIZED"):
            dataclasses.replace(m,status="PRODUCTION_APPROVED")
        with self.assertRaisesRegex(ValueError, "METRIC_MISSINGNESS_NOT_EXPLICIT"):
            dataclasses.replace(m,value=None)
        with self.assertRaisesRegex(ValueError, "non-finite"):
            dataclasses.replace(m,value="NaN")

    def test_zero_absolute_tolerance_source_contract(self):
        p,cs,d=self.bars()
        tol=ReconciliationTolerance(0,0,0,"03B1_EXACT_FIXTURE_ONLY")
        self.assertEqual(reconcile(p,cs,d,tolerance=tol).status,"PASS")
        mismatched=dataclasses.replace(p,base_volume=p.base_volume+Decimal("0.01"))
        rec=reconcile(mismatched,cs,d,tolerance=tol)
        self.assertIn("BASE_VOLUME_AGGREGATION_MISMATCH",rec.reason_codes)
        self.assertEqual(deviations(mismatched,cs)["base_volume"], "0.01")


if __name__=="__main__":
    unittest.main()
