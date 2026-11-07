"""P0: compact independent arithmetic, causal negative and R2 research E2E tests."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from unittest import TestCase
from unittest.mock import patch
import socket
import urllib.request

from test_stage03_r2_offline import BASE, WITNESS, candle, falling_structure, intraday, swing
from test_stage03_r2_functional import stage03_inputs
from test_stage03_r2_source_contract import packet_pair
from zs_smart_gate.stage03a_contracts import Direction, Horizon
from zs_smart_gate.stage03_r2_offline import Unavailable
from zs_smart_gate.stage03_r2_functional import stage03_r2_functional_e2e
from zs_smart_gate.stage03_r2_source_contract import ModeSourceEvidence
from zs_smart_gate.stage03_r2_n03_provisional import (
    MODE_RULE_ID, PROPOSAL_SHA256, SPEC,
    derive_prior_mode_from_4h, evaluate_provisional_n03,
)


def mode_for(direction, horizon, parent_open, decision, name="CONTINUATION"):
    t = parent_open - timedelta(hours=4)
    return ModeSourceEvidence(
        name, direction, horizon, "SYNTHETIC:INDEPENDENT_PRE_PARENT_MODE",
        "SYNTHETIC:MODE_V1", "SYNTHETIC:MODE_INPUT",
        t, t + timedelta(seconds=1), t + timedelta(seconds=2),
        t + timedelta(seconds=3), decision,
    )


def bars_for(direction, horizon, variant="peak", onset=25):
    count = 45 if horizon is Horizon.INTRADAY else 80
    sign = 1 if direction is Direction.UP else -1
    rows = []
    for i in range(count):
        if i < onset:
            price = D(100)
        elif i == onset:
            price = D(100 + 2*sign)
        elif i == onset + 1:
            price = D(100 + 3*sign)
        elif i == onset + 2:
            price = D(100 + 2*sign)
        else:
            price = D(100)
        high, low = max(D(100), price)+1, min(D(100), price)-1
        if variant == "no_pivot" and i > onset:
            price = D(100) + sign*(D(2)+D(i-onset)/10)
            high, low = max(D(100),price)+1,min(D(100),price)-1
        if variant in ("peak","tie") and i == onset+1:
            if sign == 1: high = D(105)
            else: low = D(95)
        if variant == "tie" and i == onset+2:
            if sign == 1: high = D(105)
            else: low = D(95)
        rows.append(candle(
            BASE+timedelta(minutes=5*i), 5,
            o="100", h=str(high), l=str(low), c=str(price), q="10"))
    return tuple(rows)


def call_n03(rows, direction, horizon, decision=None, name="CONTINUATION", source=None):
    parent_open = BASE
    decision = decision or rows[-1].close_at + timedelta(seconds=20)
    proof = source or mode_for(direction, horizon, parent_open, decision, name)
    return evaluate_provisional_n03(
        bars=rows, direction=direction, horizon=horizon,
        mode=name, mode_evidence=proof,
        parent_open_at=parent_open, decision_at=decision, witness=WITNESS)


class P0OperationalN03Tests(TestCase):
    def test_frozen_hash_independent_arithmetic_and_both_directions_horizons(self):
        self.assertEqual(PROPOSAL_SHA256,
            "ae1b645897866eed435ba29c585e75265b36b89e47d3f16cb360d94be4afb4d8")
        self.assertFalse(SPEC["setup_v1_1_equivalent"])
        self.assertEqual(SPEC["horizons_episode_bars"], {"INTRADAY": 20, "SWING": 48})
        for h in Horizon:
            for d in Direction:
                with self.subTest(h=h.value, direction=d.value):
                    rows = bars_for(d,h)
                    got = call_n03(rows,d,h)
                    # Reference: 14 previous true ranges are all 2 USDT;
                    # q_onset = directional (102-100)/2 = 1 >= 0.5;
                    # pivot e=26, confirmed only at right-bar index 28;
                    # excursion abs(105-100)=5 >= 0.5*2=1.
                    prev = rows[24]
                    self.assertEqual(prev.h - prev.l, D(2))
                    self.assertEqual((1 if d is Direction.UP else -1) *
                        (rows[25].c - rows[22].c) / D(2), D(1))
                    self.assertEqual(got["state"], "TRUE")
                    self.assertEqual(got["onset_index"], 25)
                    self.assertEqual(got["confirmation_index"], 28)
                    self.assertEqual(got["event_available_at"],
                                     rows[28].available_at.isoformat())
                    self.assertEqual(got["n03_status"], "UNAVAILABLE")
                    self.assertFalse(got["pre_move_credited"])
                    self.assertFalse(got["real_pit_verified"])
                    self.assertEqual(call_n03(rows,d,h), got)

    def test_false_no_onset_expired_tie_and_pending(self):
        for h in Horizon:
            for d in Direction:
                with self.subTest(h=h.value,d=d.value):
                    no_onset = bars_for(d,h)
                    no_onset = tuple(replace(
                        b, c=D(100), h=D(101), l=D(99)) for b in no_onset)
                    self.assertEqual(call_n03(no_onset,d,h)["reason"],
                                     "FALSE_NO_ONSET")
                    self.assertEqual(call_n03(
                        bars_for(d,h,"no_pivot"),d,h)["reason"],
                        "FALSE_EXPIRED")
                    self.assertEqual(call_n03(
                        bars_for(d,h,"tie"),d,h)["state"], "FALSE")
        # First onset near end of a sufficiently long observed window:
        # a causal decision cannot use not-yet-closed confirmation bars.
        rows = bars_for(Direction.UP,Horizon.INTRADAY,onset=43)
        partial = call_n03(rows,Direction.UP,Horizon.INTRADAY)
        self.assertEqual(partial["state"],"FALSE")
        self.assertEqual(partial["reason"],"FALSE_NOT_YET_COMPLETED")

    def test_unknown_gap_late_source_or_unproved_mode(self):
        d,h=Direction.UP,Horizon.INTRADAY
        rows=bars_for(d,h)
        decision=rows[-1].close_at+timedelta(seconds=20)
        bad_source=list(rows)
        bad_source[27]=replace(rows[27],source_id="SYNTHETIC:OTHER")
        self.assertIn("SOURCE_ID_CONFLICT",call_n03(bad_source,d,h)["reason"])
        bad_late=list(rows)
        bad_late[28]=replace(rows[28],received_at=decision+timedelta(seconds=1),
                             available_at=decision+timedelta(seconds=2))
        self.assertEqual(call_n03(bad_late,d,h)["state"],"UNKNOWN")
        self.assertIn("PIT_AVAILABILITY",call_n03(bad_late,d,h)["reason"])
        bad_gap=list(rows)
        bad_gap[27]=replace(rows[27],open_at=rows[27].open_at+timedelta(seconds=1))
        self.assertEqual(call_n03(bad_gap,d,h)["state"],"UNKNOWN")
        parent=BASE
        bad_mode=mode_for(d,h,parent,decision)
        bad_mode=replace(bad_mode,available_at=parent+timedelta(seconds=1))
        self.assertEqual(call_n03(rows,d,h,source=bad_mode)["state"],"UNKNOWN")
        self.assertEqual(evaluate_provisional_n03(
            bars=rows,direction=d,horizon=h,mode="CONTINUATION",
            mode_evidence=None,parent_open_at=parent,decision_at=decision,
            witness=WITNESS)["state"],"UNKNOWN")

    def test_mode_4h_reproducible_from_prior_pivots_and_fail_closed(self):
        kw=swing()
        parent_open=kw["parent"].open_at
        history=falling_structure(parent_open-timedelta(hours=4))
        proof=derive_prior_mode_from_4h(
            history=history,direction=Direction.UP,horizon=Horizon.SWING,
            parent_open_at=parent_open,decision_at=kw["decision_at"],witness=WITNESS)
        self.assertEqual(proof.mode,"REVERSAL")
        self.assertEqual(proof.mode_source.split(":sha256:")[0],MODE_RULE_ID)
        self.assertEqual(proof,derive_prior_mode_from_4h(
            history=history,direction=Direction.UP,horizon=Horizon.SWING,
            parent_open_at=parent_open,decision_at=kw["decision_at"],witness=WITNESS))
        opposite=derive_prior_mode_from_4h(
            history=history,direction=Direction.DOWN,horizon=Horizon.SWING,
            parent_open_at=parent_open,decision_at=kw["decision_at"],witness=WITNESS)
        self.assertEqual(opposite.mode,"CONTINUATION")
        # All bars must really be available before parent open; no post hoc
        # knowledge can serve as regime provenance.
        late=list(history)
        late[-1]=replace(late[-1],received_at=parent_open+timedelta(seconds=1),
                         available_at=parent_open+timedelta(seconds=2))
        with self.assertRaisesRegex(Unavailable,"PIT_AVAILABILITY"):
            derive_prior_mode_from_4h(
                history=late,direction=Direction.UP,horizon=Horizon.SWING,
                parent_open_at=parent_open,decision_at=kw["decision_at"],witness=WITNESS)
        mismatch=list(history)
        mismatch[0]=replace(mismatch[0],source_id="SYNTHETIC:UNRELATED")
        with self.assertRaisesRegex(Unavailable,"MODE_SOURCE_ID_CONFLICT"):
            derive_prior_mode_from_4h(
                history=mismatch,direction=Direction.UP,horizon=Horizon.SWING,
                parent_open_at=parent_open,decision_at=kw["decision_at"],witness=WITNESS)

    def test_one_offline_e2e_diagnostic_never_becomes_score(self):
        x=intraday()
        y=stage03_inputs(x)
        rows=tuple(x["context"]["5m"][-39:])+tuple(x["children"])
        proof=mode_for(x["direction"],x["horizon"],x["parent"].open_at,x["decision_at"])
        with patch.object(socket,"create_connection",side_effect=AssertionError("NO_NETWORK")), \
             patch.object(urllib.request,"urlopen",side_effect=AssertionError("NO_NETWORK")):
            result=stage03_r2_functional_e2e(
                r2_inputs=x,readiness_inputs=y,market_source_packets=packet_pair(x),
                mode_source_evidence=proof,operational_n03_5m=rows)
        self.assertEqual(result["status"],"RESEARCH_CANDIDATE")
        self.assertEqual(result["n03_operational_proxy_review"]["state"],"FALSE")
        self.assertIsNone(result["r2"]["normalizers"]["MOMENTUM_EARLY_TIMING"])
        self.assertEqual(result["score_status"],"SCORE_UNAVAILABLE")
        self.assertIsNone(result["score"])
        self.assertIsNone(result["signal_id"])
        self.assertFalse(result["publishable"])
        self.assertEqual(result["market_requests"],0)
