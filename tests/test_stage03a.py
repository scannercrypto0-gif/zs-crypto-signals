"""STAGE-03A offline PIT, MTF, lifecycle, score/plan/structure and E2E gates.

No HTTP, no Telegram, no real signal issuance, and no production formulas.
"""
import dataclasses
import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from zs_smart_gate.core import Candle, MarketSnapshot, build_candidate, score_v1_partial
from zs_smart_gate.mtf_contracts import (
    CandleWindow, ReconciliationTolerance, available_closed_context, reconcile,
)
from zs_smart_gate.stage03a_contracts import (
    Direction, EventIdentity, Horizon, Lifecycle, LifecycleObservation,
    PITDecisionSnapshot, ResearchKeyRegistry, ResearchEvent, ResearchRevision,
    ScoreGroup, ScoreV2, StructureEvidence, SwingPivot, TradePlan,
    V2_GROUPS, V2_VERSION, bind_research_candidate, unavailable_score,
)

UTC = timezone.utc
T0 = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)
EXACT = ReconciliationTolerance(Decimal("0"), Decimal("0"), Decimal("0"),
                                policy_id="SAME_SOURCE_EXACT_FIXTURE_ONLY")


def window(frame, start, *, minutes=None, source="BINANCE:SPOT:REST",
           arrived_seconds=1, **changes):
    durations = {"5m": 5, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}
    end = start + timedelta(minutes=minutes or durations[frame])
    fields = dict(timeframe=frame, open_at=start, close_at=end,
                  received_at=end + timedelta(seconds=arrived_seconds),
                  available_at=end + timedelta(seconds=arrived_seconds),
                  source_id=source, open="100", high="102", low="99",
                  close="101", base_volume="10", quote_volume="1000")
    fields.update(changes)
    return CandleWindow(**fields)


def aligned(frame, childframe, count, start=T0):
    mins = {"5m": 5, "1h": 60}
    children = [window(childframe, start + timedelta(minutes=i * mins[childframe]))
                for i in range(count)]
    end = children[-1].close_at
    parent = window(frame, start,
                    received_at=end + timedelta(seconds=2),
                    available_at=end + timedelta(seconds=2),
                    open=children[0].open, close=children[-1].close,
                    high=max(c.high for c in children),
                    low=min(c.low for c in children),
                    base_volume=sum(c.base_volume for c in children),
                    quote_volume=sum(c.quote_volume for c in children))
    decision = end + timedelta(seconds=3)
    return parent, children, decision


def base_candidate(decision):
    end = T0 + timedelta(minutes=105)
    decision = max(decision, end + timedelta(seconds=5))
    candles = [Candle(
        T0 + timedelta(minutes=i*5), T0 + timedelta(minutes=(i+1)*5),
        end + timedelta(seconds=1), end + timedelta(seconds=1),
        Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"),
        Decimal("10"), Decimal("1000")) for i in range(21)]
    market = MarketSnapshot("BTCUSDT", "USDT", True, "TRADING",
                            Decimal("50000000"), Decimal("100"), Decimal("100.01"),
                            T0 + timedelta(minutes=1))
    return build_candidate(market, candles, decision)


class MtfContractsTests(unittest.TestCase):
    def test_intraday_exact_six_and_pit(self):
        parent, children, decision = aligned("30m", "5m", 6)
        result = reconcile(parent, children, decision, tolerance=EXACT)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.child_count, 6)
        self.assertEqual(result.reason_codes, ())
        self.assertEqual(json.loads(json.dumps(result.as_dict()))["parent_timeframe"], "30m")

    def test_swing_exact_four_and_pit(self):
        parent, children, decision = aligned("4h", "1h", 4)
        result = reconcile(parent, children, decision, tolerance=EXACT)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.child_count, 4)

    def test_missing_child(self):
        parent, children, decision = aligned("30m", "5m", 6)
        result = reconcile(parent, children[:-1], decision, tolerance=EXACT)
        self.assertIn("CHILD_COUNT_MISMATCH", result.reason_codes)

    def test_duplicate_child(self):
        parent, children, decision = aligned("30m", "5m", 6)
        children[2] = children[1]
        result = reconcile(parent, children, decision, tolerance=EXACT)
        self.assertIn("DUPLICATE_CHILD", result.reason_codes)
        self.assertIn("GAP_OR_OVERLAP_OR_OUT_OF_ORDER", result.reason_codes)

    def test_mixed_source_unverified(self):
        parent, children, decision = aligned("30m", "5m", 6)
        children[1] = dataclasses.replace(children[1], source_id="OTHER")
        self.assertIn("MIXED_SOURCES_UNVERIFIED",
                      reconcile(parent, children, decision, tolerance=EXACT).reason_codes)

    def test_unclosed_parent_does_not_promote(self):
        parent, children, decision = aligned("30m", "5m", 6)
        self.assertIn("PARENT_FUTURE_OR_UNAVAILABLE_AT_DECISION", reconcile(
            parent, children, parent.close_at - timedelta(seconds=1),
            tolerance=EXACT).reason_codes)

    def test_late_child_does_not_promote(self):
        parent, children, decision = aligned("30m", "5m", 6)
        children[0] = dataclasses.replace(children[0],
            available_at=decision + timedelta(seconds=1))
        self.assertIn("CHILD_0_FUTURE_OR_UNAVAILABLE_AT_DECISION", reconcile(
            parent, children, decision, tolerance=EXACT).reason_codes)

    def test_parent_open_close_high_low_mismatches(self):
        p, children, d = aligned("30m", "5m", 6)
        for name in ("open", "close", "high", "low"):
            change = {"open": "100.1", "close": "101.1", "high": "102.1",
                      "low": "98.9"}[name]
            bad = dataclasses.replace(p, **{name: Decimal(change)})
            self.assertIn(name.upper() + "_AGGREGATION_MISMATCH",
                reconcile(bad, children, d, tolerance=EXACT).reason_codes)

    def test_base_and_quote_volume_mismatches(self):
        p, children, d = aligned("30m", "5m", 6)
        for name in ("base_volume", "quote_volume"):
            bad = dataclasses.replace(p, **{name: getattr(p, name) + 1})
            self.assertIn(name.upper() + "_AGGREGATION_MISMATCH",
                reconcile(bad, children, d, tolerance=EXACT).reason_codes)

    def test_explicit_same_source_tolerance(self):
        p, children, d = aligned("30m", "5m", 6)
        changed = dataclasses.replace(p, base_volume=p.base_volume+Decimal("0.01"))
        self.assertEqual(reconcile(changed, children, d, tolerance=EXACT).status, "INVALID")
        tol = ReconciliationTolerance("0", "0.01", "0", "FIXTURE_0.01")
        self.assertEqual(reconcile(changed, children, d, tolerance=tol).status, "PASS")
        with self.assertRaisesRegex(ValueError, "NEGATIVE_TOLERANCE"):
            ReconciliationTolerance(-1, 0, 0, "bad")

    def test_bad_child_frame_and_gap(self):
        p, children, d = aligned("30m", "5m", 6)
        children[3] = dataclasses.replace(children[3], timeframe="1h")
        result = reconcile(p, children, d, tolerance=EXACT)
        self.assertIn("CHILD_TIMEFRAME_MISMATCH", result.reason_codes)
        children[3] = dataclasses.replace(children[3], timeframe="5m",
             open_at=children[3].open_at + timedelta(minutes=5),
             close_at=children[3].close_at + timedelta(minutes=5))
        result = reconcile(p, children, d, tolerance=EXACT)
        self.assertIn("GAP_OR_OVERLAP_OR_OUT_OF_ORDER", result.reason_codes)

    def test_utc_rollover_alignment(self):
        start = datetime(2026, 10, 28, 23, 30, tzinfo=UTC)
        p, children, d = aligned("30m", "5m", 6, start)
        self.assertEqual(p.close_at.date().day, 29)
        self.assertEqual(reconcile(p, children, d, tolerance=EXACT).status, "PASS")
        with self.assertRaisesRegex(ValueError, "timestamp must be timezone-aware"):
            dataclasses.replace(p, open_at=datetime(2026, 10, 28))

    def test_unaligned_and_invalid_ohlcv(self):
        p, children, d = aligned("30m", "5m", 6)
        bad = dataclasses.replace(children[0], open_at=children[0].open_at+timedelta(minutes=1))
        self.assertIn("INVALID_UTC_ALIGNMENT", bad.errors_at(d))
        self.assertIn("INVALID_DURATION", bad.errors_at(d))
        self.assertIn("INVALID_OHLC", dataclasses.replace(p, low=Decimal("105")).errors_at(d))
        self.assertIn("INVALID_VOLUME", dataclasses.replace(p, quote_volume=-1).errors_at(d))

    def test_context_only_latest_closed_available(self):
        d = T0 + timedelta(hours=5)
        older = window("1h", T0)
        known = window("1h", T0+timedelta(hours=1))
        late = window("1h", T0+timedelta(hours=2),
                      available_at=d+timedelta(minutes=1))
        future = window("1h", T0+timedelta(hours=5))
        self.assertEqual(available_closed_context([older, future, late, known],
                         timeframe="1h", decision_at=d), known)
        self.assertIsNone(available_closed_context([future], timeframe="1h", decision_at=d))
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_CONTEXT"):
            available_closed_context([], timeframe="8h", decision_at=d)

    def test_weekly_monday_close_and_availability(self):
        monday = datetime(2026, 10, 26, 0, 0, tzinfo=UTC)
        weekly = window("1w", monday, minutes=7*24*60)
        self.assertEqual(weekly.errors_at(weekly.close_at+timedelta(seconds=2)), ())
        self.assertIsNone(available_closed_context(
            [weekly], timeframe="1w", decision_at=monday+timedelta(days=3)))
        self.assertEqual(available_closed_context(
            [weekly], timeframe="1w",
            decision_at=weekly.close_at+timedelta(seconds=2)), weekly)

    def test_weekly_context_rejects_incomplete_future(self):
        d = T0 + timedelta(days=1)
        future = window("1w", T0, minutes=7*24*60)
        self.assertIsNone(available_closed_context([future], timeframe="1w", decision_at=d))


class SchemaAndIdentityTests(unittest.TestCase):
    def key(self, **kwargs):
        p = dict(symbol="BTCUSDT", direction=Direction.UP, horizon=Horizon.INTRADAY,
                 setup_type="RESEARCH_CONTINUATION", decision_candle_close_at=T0+timedelta(minutes=30),
                 rule_version="03A_NOT_QUALIFIED", event_discriminator="candidate-A")
        p.update(kwargs)
        return EventIdentity.research_key(**p)

    def test_key_stable_retry_vs_independent_event(self):
        a, b = self.key(), self.key()
        self.assertEqual(a.detection_event_key, b.detection_event_key)
        registry = ResearchKeyRegistry()
        self.assertEqual(registry.observe(a), "NEW_RESEARCH_EVENT")
        self.assertEqual(registry.observe(b), "DUPLICATE_RETRY")
        newer = self.key(event_discriminator="candidate-B")
        self.assertNotEqual(a.detection_event_key, newer.detection_event_key)
        self.assertEqual(registry.observe(newer), "NEW_RESEARCH_EVENT")
        another_close = self.key(decision_candle_close_at=T0+timedelta(minutes=60))
        self.assertEqual(registry.observe(another_close), "NEW_RESEARCH_EVENT")
        self.assertEqual(a.as_dict()["signal_id"], None)

    def test_immutable_key_and_signal_id_not_issued(self):
        a = self.key()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            a.detection_event_key = "overwrite"
        with self.assertRaisesRegex(ValueError, "CANNOT_ASSIGN_SIGNAL_ID"):
            dataclasses.replace(a, signal_id="SG-FAKE")
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_EVENT_IDENTITY"):
            self.key(event_discriminator="")

    def test_lifecycle_enum_but_no_qualified_transition(self):
        self.assertEqual(Lifecycle.QUALIFIED_SIGNAL.value, "QUALIFIED_SIGNAL")
        self.assertEqual(Lifecycle.EARLY_WATCH.value, "EARLY_WATCH")
        p, cs, d = aligned("30m", "5m", 6)
        candidate = base_candidate(d)
        snap = reconcile(p, cs, candidate.decision_at, tolerance=EXACT)
        good = bind_research_candidate(candidate=candidate, identity=self.key(),
                                       reconciliation=snap, candidate_id="test-c-1")
        self.assertEqual(good.status, Lifecycle.RESEARCH_CANDIDATE)
        self.assertFalse(good.as_dict()["publishable"])
        self.assertIsNone(good.identity.signal_id)
        with self.assertRaisesRegex(ValueError, "NO_LIVE_SIGNAL"):
            dataclasses.replace(good, status=Lifecycle.QUALIFIED_SIGNAL)

    def test_raw_watch_contracts_not_qualified(self):
        for state in (Lifecycle.RAW_OBSERVATION, Lifecycle.EARLY_WATCH):
            record = LifecycleObservation(state, "BINANCE:SPOT:BTCUSDT",
                                          T0, T0+timedelta(seconds=1),
                                          ("OBSERVATION_ONLY",))
            self.assertEqual(record.status, state)
        with self.assertRaisesRegex(ValueError, "OBSERVATION_CANNOT_PUBLISH"):
            LifecycleObservation(Lifecycle.QUALIFIED_SIGNAL, "BINANCE:SPOT:BTCUSDT",
                                 T0, T0, ("INVALID",))
        with self.assertRaisesRegex(ValueError, "INVALID_OBSERVATION_AVAILABILITY"):
            LifecycleObservation(Lifecycle.EARLY_WATCH, "BINANCE:SPOT:BTCUSDT",
                                 T0, T0-timedelta(seconds=1), ("LATE",))

    def test_snapshot_future_receipt_rejected_without_any_signal(self):
        with self.assertRaisesRegex(ValueError, "PIT_SNAPSHOT_FUTURE"):
            PITDecisionSnapshot("SRC", T0, T0+timedelta(minutes=30),
                T0+timedelta(minutes=31), T0+timedelta(minutes=31),
                T0+timedelta(minutes=30, seconds=10))

    def test_full_candidate_through_v1_core_and_03a_contract_json(self):
        parent, children, decision = aligned("30m", "5m", 6)
        core = base_candidate(decision)
        self.assertEqual(core.status, "ELIGIBLE")
        self.assertEqual(core.score_status, "SCORE_UNAVAILABLE")
        mtf = reconcile(parent, children, core.decision_at, tolerance=EXACT)
        event = bind_research_candidate(candidate=core, identity=self.key(),
                                        reconciliation=mtf, candidate_id="core-candidate-1")
        blob = json.loads(json.dumps(event.as_dict(), sort_keys=True))
        self.assertEqual(blob["window"]["status"], "PASS")
        self.assertEqual(blob["status"], "RESEARCH_CANDIDATE")
        self.assertEqual(blob["snapshot"]["source_id"], "BINANCE:SPOT:REST")
        self.assertEqual(blob["snapshot"]["candle_close_at"], parent.close_at.isoformat())
        self.assertIsNone(blob["snapshot"]["source_publication_time"])
        self.assertEqual(blob["score"]["status"], "SCORE_UNAVAILABLE")
        self.assertEqual(blob["score"]["maximum"], 100)
        self.assertEqual(blob["candidate"]["status"], "ELIGIBLE")
        self.assertFalse(blob["delivery_authorized"])
        self.assertIsNone(blob["identity"]["signal_id"])

    def test_e2e_identity_must_match_decision_window_not_future_close(self):
        p, cs, d = aligned("30m", "5m", 6)
        candidate = base_candidate(d)
        rec = reconcile(p, cs, candidate.decision_at, tolerance=EXACT)
        with self.assertRaisesRegex(ValueError, "PIT_CANDIDATE_OR_WINDOW"):
            bind_research_candidate(
                candidate=candidate,
                identity=self.key(decision_candle_close_at=T0+timedelta(minutes=60)),
                reconciliation=rec, candidate_id="wrong-window")

    def test_full_swing_four_hour_end_to_end_contract_only(self):
        p, cs, d = aligned("4h", "1h", 4)
        core = base_candidate(d)
        self.assertEqual(core.status, "ELIGIBLE")
        rec = reconcile(p, cs, core.decision_at, tolerance=EXACT)
        self.assertEqual(rec.status, "PASS")
        identity = self.key(horizon=Horizon.SWING, direction=Direction.DOWN,
                            decision_candle_close_at=p.close_at,
                            setup_type="RESEARCH_REVERSAL")
        event = bind_research_candidate(candidate=core, identity=identity,
                                        reconciliation=rec, candidate_id="swing-candidate")
        serialized = json.loads(json.dumps(event.as_dict()))
        self.assertEqual(serialized["window"]["parent_timeframe"], "4h")
        self.assertEqual(serialized["identity"]["direction"], "DOWN")
        self.assertEqual(serialized["score"]["groups"][0]["maximum"], 35)
        self.assertEqual(serialized["status"], "RESEARCH_CANDIDATE")
        self.assertFalse(serialized["publishable"])
        self.assertIsNone(serialized["score"]["total"])

    def test_research_update_is_immutable_and_not_signal_publication(self):
        key = self.key()
        revision = ResearchRevision(key.detection_event_key, "core-1", 2,
                                    T0, T0+timedelta(minutes=5),
                                    ("NEW_RESEARCH_OBSERVATION",))
        self.assertEqual(revision.status, Lifecycle.RESEARCH_CANDIDATE)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            revision.revision = 3
        with self.assertRaisesRegex(ValueError, "INVALID_RESEARCH_REVISION"):
            dataclasses.replace(revision, revision=1)
        with self.assertRaisesRegex(ValueError, "NONMONOTONIC"):
            dataclasses.replace(revision, updated_at=T0)
        with self.assertRaisesRegex(ValueError, "CANNOT_PUBLISH_UPDATE"):
            dataclasses.replace(revision, status=Lifecycle.QUALIFIED_SIGNAL)

    def test_e2e_future_child_fails_without_signal(self):
        p, cs, d = aligned("30m", "5m", 6)
        core = base_candidate(d)
        cs[0] = dataclasses.replace(cs[0], available_at=core.decision_at+timedelta(seconds=1))
        bad = reconcile(p, cs, core.decision_at, tolerance=EXACT)
        event = bind_research_candidate(candidate=core, identity=self.key(),
                                        reconciliation=bad, candidate_id="late-1")
        self.assertEqual(event.status, Lifecycle.INVALID)
        self.assertIn("CHILD_0_FUTURE_OR_UNAVAILABLE_AT_DECISION", event.reason_codes)
        self.assertFalse(event.as_dict()["publishable"])

    def test_e2e_unavailable_core_not_promoted(self):
        p, cs, d = aligned("30m", "5m", 6)
        core = base_candidate(d)
        bad_core = dataclasses.replace(core, status="INELIGIBLE",
                                       eligibility_reasons=("LOW_24H_QUOTE_VOLUME",))
        evidence = reconcile(p, cs, bad_core.decision_at, tolerance=EXACT)
        event = bind_research_candidate(candidate=bad_core, identity=self.key(),
                                        reconciliation=evidence, candidate_id="invalid-core")
        self.assertEqual(event.status, Lifecycle.REJECTED)
        self.assertIn("LOW_24H_QUOTE_VOLUME", event.reason_codes)

    def test_wrong_identity_and_wrong_direction_rejected(self):
        p, cs, d = aligned("30m", "5m", 6)
        core = base_candidate(d)
        evidence = reconcile(p, cs, core.decision_at, tolerance=EXACT)
        e = bind_research_candidate(candidate=core, identity=self.key(),
                                    reconciliation=evidence, candidate_id="e1")
        with self.assertRaisesRegex(ValueError, "SCORE_HORIZON_DIRECTION"):
            dataclasses.replace(e, score=unavailable_score(Horizon.INTRADAY, Direction.DOWN))
        with self.assertRaisesRegex(ValueError, "PIT_CANDIDATE_OR_WINDOW"):
            dataclasses.replace(e, decision_at=core.decision_at+timedelta(seconds=1))

    def test_v2_group_maxes_for_both_horizons_directions(self):
        for horizon in Horizon:
            for direction in Direction:
                score = unavailable_score(horizon, direction)
                self.assertEqual(len(score.groups), 6)
                self.assertEqual(sum(x.maximum for x in score.groups), 100)
                self.assertIsNone(score.total)
                self.assertEqual(score.as_dict()["probability"], None)
                self.assertEqual(score.status, "SCORE_UNAVAILABLE")
                self.assertEqual(score.score_version, V2_VERSION[horizon])

    def test_low_score_component_not_a_gate_or_total(self):
        original = unavailable_score(Horizon.INTRADAY, Direction.DOWN)
        parts = list(original.groups)
        parts[0] = ScoreGroup(parts[0].name, parts[0].maximum,
                              raw_value="0", normalized_value="0", contribution="0",
                              missing_reason="RESEARCH_ONLY_PARTIAL")
        score = dataclasses.replace(original, groups=tuple(parts))
        self.assertIsNone(score.total)
        self.assertEqual(score.status, "SCORE_UNAVAILABLE")
        self.assertEqual(score.groups[0].contribution, 0)
        with self.assertRaisesRegex(ValueError, "CANNOT_ISSUE_NUMERIC"):
            dataclasses.replace(score, total=0, status="SCORE_AVAILABLE")

    def test_missing_score_no_redistribution_and_bad_weights(self):
        s = unavailable_score(Horizon.SWING, Direction.UP)
        self.assertEqual(s.groups[0].maximum, 35)
        self.assertTrue(all(g.contribution is None for g in s.groups))
        self.assertEqual(s.as_dict()["groups"][1]["contribution"], None)
        with self.assertRaisesRegex(ValueError, "GROUPS_OR_WEIGHTS"):
            dataclasses.replace(s, groups=tuple(list(s.groups[:-1]) + [
                ScoreGroup("LIQUIDITY_QUALITY", 7)]))
        with self.assertRaisesRegex(ValueError, "NORMALIZATION_OUT_OF_RANGE"):
            ScoreGroup("X", 10, normalized_value=Decimal("1.1"))
        with self.assertRaisesRegex(ValueError, "UNPROVEN_SCORE"):
            ScoreGroup("X", 10, contribution=Decimal("3"))

    def test_v1_frozen_research_regression_oracle(self):
        s = score_v1_partial(Decimal("0"), Decimal("1"), Decimal("0"))
        self.assertEqual(s["version"], "V1_PARTIAL_RESEARCH_ONLY")
        self.assertEqual(s["status"], "SCORE_UNAVAILABLE")
        self.assertIsNone(s["total"])
        self.assertEqual(Decimal(s["components"]["price_momentum_35"]), Decimal("0"))
        self.assertEqual(Decimal(s["components"]["volume_expansion_25"]), Decimal("0"))
        self.assertEqual(Decimal(s["components"]["liquidity_quality_10"]), Decimal("10"))

    def test_trade_plan_null_price_levels_and_down_spot(self):
        for direction, action in ((Direction.UP, "BUY_SPOT"),
                                  (Direction.DOWN, "SELL_OWNED_SPOT"),
                                  (Direction.DOWN, "OBSERVE_ONLY")):
            plan = TradePlan(None, direction, trade_action=action)
            data = json.loads(json.dumps(plan.as_dict()))
            self.assertEqual(data["plan_status"], "RESEARCH_ONLY")
            self.assertIsNone(data["tp1"])
            self.assertIsNone(data["entry_zone_low"])
            self.assertFalse(data["trade_ready"])
            self.assertTrue(data["manual_spot_only"])

    def test_trade_ready_futures_and_fake_levels_rejected(self):
        with self.assertRaisesRegex(ValueError, "TRADE_READY_REQUIRES"):
            TradePlan(None, Direction.UP, plan_status="TRADE_READY")
        with self.assertRaisesRegex(ValueError, "FUTURES_OR_AUTO"):
            TradePlan(None, Direction.DOWN, trade_action="SHORT_FUTURES")
        with self.assertRaisesRegex(ValueError, "UNVALIDATED_TRADE_LEVELS"):
            TradePlan(None, Direction.UP, tp1=Decimal("105"))
        with self.assertRaisesRegex(ValueError, "TRADE_DIRECTION_ACTION"):
            TradePlan(None, Direction.UP, trade_action="SELL_OWNED_SPOT")
        with self.assertRaisesRegex(ValueError, "RESEARCH_ONLY_REASONS"):
            TradePlan(None, Direction.UP, reason_codes=())

    def test_trade_plan_is_frozen_and_nonfinite_rejected(self):
        plan = TradePlan(None, Direction.UP, tick_size=Decimal("0.01"))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            plan.tp1 = Decimal("100")
        with self.assertRaisesRegex(ValueError, "non-finite"):
            TradePlan(None, Direction.UP, slippage_assumption="NaN")

    def test_pivot_lookahead_rejected(self):
        pivot = SwingPivot("p1", "4h", T0, T0+timedelta(hours=4),
                           T0+timedelta(hours=5), Decimal("105"), "HIGH", "SOURCE")
        self.assertFalse(pivot.known_at(T0+timedelta(hours=4)))
        with self.assertRaisesRegex(ValueError, "PIVOT_NOT_KNOWN_BEFORE_BREAK"):
            StructureEvidence("BOS", pivot, T0+timedelta(hours=4),
                              T0+timedelta(hours=4, seconds=1),
                              T0+timedelta(hours=4, seconds=2),
                              True, "UNVERIFIED_RESEARCH_CONTRACT")

    def test_pivot_timestamp_order_and_future_observation(self):
        with self.assertRaisesRegex(ValueError, "FUTURE_CONFIRMED"):
            SwingPivot("p1","4h", T0, T0+timedelta(hours=2),
                       T0+timedelta(hours=1), Decimal("105"), "HIGH","S")
        pivot = SwingPivot("p2", "4h", T0-timedelta(hours=8),
                           T0-timedelta(hours=4), T0-timedelta(hours=3),
                           Decimal("110"),"HIGH","S")
        valid = StructureEvidence("CHoCH", pivot, T0, T0+timedelta(seconds=1),
                                  T0+timedelta(seconds=2), True,
                                  "UNVERIFIED_RESEARCH_CONTRACT")
        self.assertEqual(valid.status, "UNVERIFIED_RESEARCH_CONTRACT")
        with self.assertRaisesRegex(ValueError, "STAGE_03A_CANNOT_CONFIRM"):
            dataclasses.replace(valid, status="CONFIRMED_BOS")
        with self.assertRaisesRegex(ValueError, "BREAK_FUTURE"):
            dataclasses.replace(valid, decision_at=T0)
        with self.assertRaisesRegex(ValueError, "BREAK_NOT_CLOSED"):
            dataclasses.replace(valid, confirmed_close=False)


if __name__ == "__main__":
    unittest.main()
