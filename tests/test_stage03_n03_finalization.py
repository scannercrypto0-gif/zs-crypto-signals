"""Targeted N03 V0.2 episode-selection and closure-missingness regressions.

Existing accepted N03 fixtures are imported only as builders, not re-run.
No network, live data, scoring, or Stage05 action.
"""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase

from test_stage03_r2_offline import BASE, candle, intraday
from test_stage03_r2_n03_provisional import bars_for, call_n03
from test_stage03_r2_functional import stage03_inputs
from test_stage03_r2_closed_bundle import sample
from test_stage03_r2_receipt_bundle import _record
from zs_smart_gate.stage03a_contracts import Direction, Horizon
from zs_smart_gate.stage03_r2_closure import stage03_c1c4_research_from_closed_receipts
from zs_smart_gate.stage03_r2_n03_provisional import (
    SELECTION_SPEC, SELECTION_SPEC_SHA256, SPEC_SHA256,
)


def two_episodes(direction, horizon):
    """A confirmed first pivot; a second pivot confirmed only on bar 88."""
    rows = list(bars_for(direction, horizon))
    for i in range(len(rows), 90):
        rows.append(candle(
            BASE + timedelta(minutes=5*i), 5,
            o="100", h="101", l="99", c="100", q="10",
        ))
    if direction is Direction.UP:
        updates = ((85, "102", "103", "99"),
                   (86, "103", "105", "99"),
                   (87, "102", "103", "99"))
    else:
        updates = ((85, "98", "101", "97"),
                   (86, "97", "101", "95"),
                   (87, "98", "101", "97"))
    for index, close, high, low in updates:
        rows[index] = replace(
            rows[index], c=D(close), h=D(high), l=D(low),
        )
    return tuple(rows)


class N03FinalizationOnly(TestCase):
    def test_later_nonoverlapping_onset_never_erases_earlier_completed_event(self):
        self.assertEqual(SELECTION_SPEC["base_spec_sha256"], SPEC_SHA256)
        self.assertEqual(
            SELECTION_SPEC_SHA256,
            "8c73afe1facb0f8f2e6945badfe8b323b999be8763f1355b26ae3cb50f2e25e2",
        )
        for direction in Direction:
            for horizon in Horizon:
                with self.subTest(direction=direction.value, horizon=horizon.value):
                    bars = two_episodes(direction, horizon)
                    before = call_n03(bars[:85], direction, horizon)
                    self.assertEqual(before["state"], "TRUE")
                    self.assertEqual(before["onset_index"], 25)
                    self.assertEqual(before["confirmation_index"], 28)

                    waiting = call_n03(bars[:88], direction, horizon)
                    self.assertEqual(waiting["state"], "FALSE")
                    self.assertEqual(waiting["reason"], "FALSE_NOT_YET_COMPLETED")
                    self.assertEqual(waiting["onset_index"], 85)
                    self.assertEqual(waiting["confirmation_index"], None)
                    self.assertEqual(waiting["event_available_at"], None)
                    self.assertEqual(waiting["completed_events"], [{
                        "onset_index": 25,
                        "confirmation_index": 28,
                        "event_available_at": bars[28].available_at.isoformat(),
                    }])
                    self.assertEqual(waiting["n03_status"], "UNAVAILABLE")

                    completed = call_n03(bars[:89], direction, horizon)
                    self.assertEqual(completed["state"], "TRUE")
                    self.assertEqual(completed["onset_index"], 85)
                    self.assertEqual(completed["confirmation_index"], 88)
                    self.assertEqual(completed["event_available_at"],
                                     bars[88].available_at.isoformat())
                    self.assertEqual(
                        [x["onset_index"] for x in completed["completed_events"]],
                        [25, 85],
                    )
                    self.assertEqual(
                        completed["completed_events"],
                        call_n03(bars, direction, horizon)["completed_events"],
                    )
                    self.assertFalse(completed["pre_move_credited"])
                    self.assertFalse(completed["real_pit_verified"])

    def test_pivot_confirmation_cannot_precede_right_bar_and_overlap_unknown(self):
        for direction in Direction:
            for horizon in Horizon:
                with self.subTest(direction=direction.value, horizon=horizon.value):
                    bars = two_episodes(direction, horizon)
                    # The second right candle is not in the as-of observation.
                    waiting = call_n03(bars[:88], direction, horizon)
                    self.assertEqual(waiting["state"], "FALSE")
                    self.assertEqual(waiting["false_semantics"],
                                     "NOT_COMPLETED_AS_OF_DECISION_NOT_FUTURE_IMPOSSIBILITY")
                    # Supplying that candle before its availability is UNKNOWN.
                    future = call_n03(
                        bars[:89], direction, horizon,
                        decision=bars[87].available_at,
                    )
                    self.assertEqual(future["state"], "UNKNOWN")
                    self.assertIsNone(future["event_available_at"])
                    # A second onset inside episode #1 is ambiguous, not an event.
                    overlap = list(bars_for(direction, horizon))
                    if direction is Direction.UP:
                        overlap[40] = replace(overlap[40], c=D(102), h=D(103))
                    else:
                        overlap[40] = replace(overlap[40], c=D(98), l=D(97))
                    ambiguous = call_n03(overlap, direction, horizon)
                    self.assertEqual(ambiguous["state"], "UNKNOWN")
                    self.assertEqual(ambiguous["reason"],
                                     "N03_OVERLAPPING_ONSET_EPISODES")
                    self.assertEqual(ambiguous["completed_events"], [{
                        "onset_index": 25,
                        "confirmation_index": 28,
                        "event_available_at": overlap[28].available_at.isoformat(),
                    }])

    def test_missing_n03_value_keeps_original_unavailable_reason(self):
        inputs = intraday()
        record = _record(sample(inputs, stage03_inputs(inputs)))
        packet = stage03_c1c4_research_from_closed_receipts(record)
        self.assertEqual(packet["status"], "RESEARCH_CANDIDATE")
        entry = next(x for x in packet["component_rows"]
                     if x["indicator"] == "N03")
        self.assertEqual(entry["status"], "UNAVAILABLE")
        self.assertIsNone(entry["value"])
        self.assertIn("N03", packet["unavailable_component_ids"])
        self.assertEqual(
            entry["reason_codes"],
            [packet["research"]["r2"]["missing_reasons"]["MOMENTUM_EARLY_TIMING"]],
        )
        self.assertEqual(packet["full_impulse_definition_status"], "UNAPPROVED")
        self.assertIsNone(packet["score"])
        self.assertIsNone(packet["signal_id"])
        self.assertFalse(packet["delivery_authorized"])
