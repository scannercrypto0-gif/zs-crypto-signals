"""P0 Stage03: versioned, falsifiable 5m-pivot operational impulse proxy.

Owner directive 6707985618 delegates operational choices, NOT actual source
evidence, predictive confirmation, production scoring or trading. Synthetic
only; separate from frozen Setup v1.1 and the approved production N03 gate.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Sequence

from .stage03a_contracts import Direction, Horizon
from .stage03_r2_offline import (
    Candle, ClockWitness, Unavailable, asof, atr14_prev, check_bars,
    confirmed_pivots, utc,
)
from .stage03_r2_source_contract import (
    ImpulseState, ModeSourceEvidence, require_prior_mode,
)

SPEC = json.loads("{\"completion\":{\"event_time\":\"available_at_of_second_right_confirmation_bar\",\"excursion_atr_min\":\"0.5\",\"last_confirming_bar\":\"at_most_onset_plus_horizon_minus_1\",\"left_bars\":2,\"pivot\":\"UP strict higher high than all four adjacent highs; DOWN strict lower low than all four adjacent lows\",\"reference_atr\":\"ATR14_previous_at_onset\",\"reference_price\":\"close_at_onset_minus_3\",\"right_bars\":2,\"tie\":\"no_pivot\"},\"directions\":[\"UP\",\"DOWN\"],\"false_semantics\":\"NOT_COMPLETED_AS_OF_DECISION_NOT_PREDICTION\",\"horizons_episode_bars\":{\"INTRADAY\":20,\"SWING\":48},\"input_timeframe\":\"5m\",\"missing\":\"UNKNOWN_if_gap_late_source_mismatch_missing_mode_clock_or_unresolved_overlap\",\"mode_rule\":\"supplied_independently_prior_to_parent_open\",\"modes\":[\"CONTINUATION\",\"REVERSAL\"],\"onset\":{\"atr_period\":14,\"crossing\":\"q_previous<0.5 and q_current>=0.5\",\"momentum_closes\":3,\"threshold_atr\":\"0.5\"},\"predicate_id\":\"ZS03_FULL_IMPULSE_5M_CONFIRMED_PIVOT\",\"setup_v1_1_equivalent\":false,\"version\":\"PROPOSAL_V0_1_UNAPPROVED\"}")
SPEC_SHA256 = "ae1b645897866eed435ba29c585e75265b36b89e47d3f16cb360d94be4afb4d8"
if hashlib.sha256(json.dumps(
        SPEC, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
).encode("utf-8")).hexdigest() != SPEC_SHA256:
    raise RuntimeError("ZS03_IMPULSE_SPEC_SHA_MISMATCH")

MODE_RULE_ID = "ZS03_PRIOR_CONFIRMED_4H_PIVOT_MODE"
MODE_RULE_VERSION = "V0_1_OPS_CANDIDATE_NO_REAL_PIT"


def derive_prior_mode_from_4h(
    *, history: Sequence[Candle], direction: Direction, horizon: Horizon,
    parent_open_at: datetime, decision_at: datetime, witness: ClockWitness,
) -> ModeSourceEvidence:
    """Independently derive and fingerprint mode from PRE-parent 4h pivots.

    Requires two confirmed highs and lows, 32 strictly contiguous 4h bars,
    all CLOSED and RECEIVED with conservative clock guard *before* parent open.
    N10 daily/weekly context never enters the derivation.
    """
    if not isinstance(direction, Direction) or not isinstance(horizon, Horizon):
        raise Unavailable("MODE_SCOPE_INVALID")
    if not isinstance(witness, ClockWitness):
        raise Unavailable("MODE_CLOCK_WITNESS_MISSING")
    if len(history) < 32 or any(not isinstance(b, Candle) for b in history):
        raise Unavailable("MODE_32_TYPED_4H_REQUIRED")
    parent_open_at = utc(parent_open_at)
    decision_at = utc(decision_at)
    if not parent_open_at < decision_at:
        raise Unavailable("MODE_PARENT_DECISION_ORDER")
    if len({b.source_id for b in history}) != 1:
        raise Unavailable("MODE_SOURCE_ID_CONFLICT")
    check_bars(history, parent_open_at, witness, timedelta(hours=4))
    if (history[-1].close_at >= parent_open_at
            or parent_open_at - history[-1].close_at > timedelta(hours=8)):
        raise Unavailable("MODE_NOT_PRIOR_TO_PARENT")
    pivots = confirmed_pivots(history, parent_open_at, witness=witness)
    highs = [p for p in pivots if p.kind == "HIGH"]
    lows = [p for p in pivots if p.kind == "LOW"]
    if len(highs) < 2 or len(lows) < 2:
        raise Unavailable("MODE_CONFIRMED_PIVOTS_MISSING")
    rising = highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price
    falling = highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price
    if rising == falling:
        raise Unavailable("MODE_STRUCTURE_UNDEFINED_OR_MIXED")
    same_direction = rising if direction is Direction.UP else falling
    mode = "CONTINUATION" if same_direction else "REVERSAL"
    proof = {
        "rule": MODE_RULE_ID, "version": MODE_RULE_VERSION,
        "source_id": history[0].source_id,
        "direction": direction.value, "horizon": horizon.value,
        "parent_open": parent_open_at.isoformat(), "mode": mode,
        "pivots": [highs[-2].level_id, highs[-1].level_id,
                   lows[-2].level_id, lows[-1].level_id],
        "bars": [[b.open_at.isoformat(), b.close_at.isoformat(),
                  b.received_at.isoformat(), b.available_at.isoformat(),
                  str(b.o), str(b.h), str(b.l), str(b.c), str(b.q)]
                 for b in history],
    }
    digest = hashlib.sha256(json.dumps(
        proof, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    result = ModeSourceEvidence(
        mode=mode, direction=direction, horizon=horizon,
        mode_source=MODE_RULE_ID + ":sha256:" + digest,
        mode_version=MODE_RULE_VERSION, source_id=history[0].source_id,
        context_close_at=history[-1].close_at,
        observed_at=history[-1].close_at,
        received_at=max(b.received_at for b in history),
        available_at=max(b.available_at for b in history),
        decision_at=decision_at,
    )
    # Exact future-independent guard; a valid mode is not computed from N10.
    require_prior_mode(
        result, mode=mode, direction=direction, horizon=horizon,
        parent=history[-1].__class__(
            parent_open_at, decision_at, decision_at, decision_at,
            Decimal(1), Decimal(1), Decimal(1), Decimal(1), Decimal(0)),
        decision_at=decision_at, witness=witness,
    )
    return result


def evaluate_provisional_n03(
    *, bars: Sequence[Candle], direction: Direction, horizon: Horizon,
    mode: str, mode_evidence: ModeSourceEvidence | None,
    parent_open_at: datetime, decision_at: datetime, witness: ClockWitness,
) -> dict:
    """Tri-state operational *proxy*, distinct from source-qualified N03.

    TRUE only on full strict 2+2 pivot availability. FALSE means no
    completion yet as of the provided decision, NOT future impossibility.
    Missing/late/unknown/overlap => UNKNOWN. No N03/pre-move points.
    """
    result = {
        "schema": "ZS03_N03_OPERATIONAL_PROXY_V0_1",
        "predicate_id": SPEC["predicate_id"], "definition_sha256": SPEC_SHA256,
        "state": ImpulseState.UNKNOWN.value, "reason": "NOT_EVALUATED",
        "onset_index": None, "confirmation_index": None,
        "event_available_at": None, "episode_expires_at_index": None,
        "n03_status": "UNAVAILABLE", "pre_move_credited": False,
        "source_validated": False, "real_pit_verified": False,
    }
    try:
        if (not isinstance(direction, Direction) or not isinstance(horizon, Horizon)
                or mode not in ("CONTINUATION", "REVERSAL")):
            raise Unavailable("N03_SCOPE_INVALID")
        if not isinstance(witness, ClockWitness):
            raise Unavailable("N03_CLOCK_MISSING")
        parent_open_at, decision_at = utc(parent_open_at), utc(decision_at)
        if parent_open_at >= decision_at:
            raise Unavailable("N03_PARENT_DECISION_INVALID")
        if (not isinstance(mode_evidence, ModeSourceEvidence)
                or mode_evidence.mode != mode
                or mode_evidence.direction is not direction
                or mode_evidence.horizon is not horizon
                or mode_evidence.decision_at != decision_at):
            raise Unavailable("N03_PRIOR_MODE_MISSING_OR_CONFLICT")
        asof(mode_evidence.available_at, parent_open_at, witness)
        n = SPEC["horizons_episode_bars"][horizon.value]
        if len(bars) < n + 19 or any(not isinstance(b, Candle) for b in bars):
            raise Unavailable("N03_5M_HISTORY_OR_WARMUP_MISSING")
        if len({b.source_id for b in bars}) != 1:
            raise Unavailable("N03_SOURCE_ID_CONFLICT")
        check_bars(bars, decision_at, witness, timedelta(minutes=5))
        if any(a.available_at > b.available_at for a,b in zip(bars[:-1], bars[1:])):
            raise Unavailable("N03_RECEIPT_ORDER_CONFLICT")
        d = Decimal(1) if direction is Direction.UP else Decimal(-1)
        theta = Decimal(SPEC["onset"]["threshold_atr"])
        excursion = Decimal(SPEC["completion"]["excursion_atr_min"])
        def q(i: int) -> Decimal:
            return d * (bars[i].c - bars[i-3].c) / atr14_prev(bars[:i])
        # ATR(j-1) needs 15 prior closed bars, and 3-momentum closes.
        crossings = [j for j in range(19, len(bars))
                     if q(j-1) < theta <= q(j)]
        if not crossings:
            result.update(state=ImpulseState.FALSE.value, reason="FALSE_NO_ONSET")
            return result
        j = crossings[0]
        for nxt in crossings[1:]:
            if nxt < j+n:
                raise Unavailable("N03_OVERLAPPING_ONSET_EPISODES")
            j = nxt
        expiry = j+n-1
        result.update(onset_index=j, episode_expires_at_index=expiry)
        base, atr = bars[j-3].c, atr14_prev(bars[:j])
        # The rightmost confirming candle must lie inside the episode horizon.
        for e in range(j, min(expiry-2, len(bars)-3)+1):
            extreme = bars[e].h if direction is Direction.UP else bars[e].l
            neighbors = [bars[k].h if direction is Direction.UP else bars[k].l
                         for k in (e-2,e-1,e+1,e+2)]
            strict = (all(extreme > p for p in neighbors) if direction is Direction.UP
                      else all(extreme < p for p in neighbors))
            if strict and d*(extreme-base) >= excursion*atr:
                result.update(
                    state=ImpulseState.TRUE.value,
                    reason="TRUE_CONFIRMED_LOCAL_PIVOT_OPERATIONAL_ONLY",
                    confirmation_index=e+2,
                    event_available_at=bars[e+2].available_at.isoformat(),
                )
                return result
        result.update(
            state=ImpulseState.FALSE.value,
            reason=("FALSE_EXPIRED" if len(bars)-1 >= expiry
                    else "FALSE_NOT_YET_COMPLETED"),
        )
    except (Unavailable, TypeError, ValueError, IndexError, ZeroDivisionError) as exc:
        result.update(
            state=ImpulseState.UNKNOWN.value,
            reason=str(exc) if isinstance(exc, Unavailable) else "N03_INVALID_INPUT",
        )
    return result
