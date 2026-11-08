"""One-source closed-window -> Stage03 R2/03A research bridge, offline only.

The input carries BOTH base and quote volumes. They are never inferred from
prices, guessed, or copied across units. Only source-labelled synthetic fixtures
are accepted here; this is no real-market PIT admission, score or publication.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, Sequence

from .core import Candle as CoreCandle, MarketSnapshot
from .mtf_contracts import CandleWindow, ReconciliationTolerance
from .stage03a_contracts import Direction, Horizon
from .stage03_r2_offline import (
    Candle, ClockWitness, Unavailable, asof, utc,
)
from .stage03_r2_functional import stage03_r2_functional_e2e
from .stage03_r2_n03_provisional import derive_prior_mode_from_4h
from .stage03_r2_source_contract import (
    BookTickerPacket, Ticker24Packet, ModeSourceEvidence,
    market_from_explicit_packets,
)

_FRAMES = {Horizon.INTRADAY: ("30m", "5m", 6),
           Horizon.SWING: ("4h", "1h", 4)}


def _closed(
    bar: CandleWindow, *, frame: str, source_id: str,
    decision_at: datetime, witness: ClockWitness,
) -> Candle:
    if not isinstance(bar, CandleWindow) or bar.timeframe != frame:
        raise Unavailable("BUNDLE_TYPED_FRAME_REQUIRED:" + frame)
    if not source_id.startswith("SYNTHETIC:") or bar.source_id != source_id:
        raise Unavailable("BUNDLE_CANDLE_SOURCE_MISMATCH:" + frame)
    invalid = bar.errors_at(decision_at)
    if invalid:
        raise Unavailable("BUNDLE_CANDLE_INVALID:" + frame + ":" + ",".join(invalid))
    asof(bar.available_at, decision_at, witness)
    return Candle(bar.open_at, bar.close_at, bar.received_at,
                  bar.available_at, bar.open, bar.high, bar.low,
                  bar.close, bar.quote_volume, source_id=bar.source_id)


def _core(bar: CandleWindow) -> CoreCandle:
    """Preserve measured base/quote quantities independently, without conversion."""
    return CoreCandle(
        bar.open_at, bar.close_at, bar.received_at, bar.available_at,
        bar.open, bar.high, bar.low, bar.close,
        bar.base_volume, bar.quote_volume,
    )


def stage03_r2_from_closed_bundle(
    *, symbol: str, horizon: Horizon, direction: Direction, mode: str,
    parent: CandleWindow, children: Sequence[CandleWindow],
    core_5m: Sequence[CandleWindow],
    context: Mapping[str, Sequence[CandleWindow]],
    book: BookTickerPacket, ticker24: Ticker24Packet,
    witness: ClockWitness, decision_at: datetime,
    tolerance: ReconciliationTolerance, event_discriminator: str,
    mode_source_evidence: ModeSourceEvidence | None = None,
    prior_mode_4h: Sequence[CandleWindow] | None = None,
    operational_n03_5m: Sequence[CandleWindow] | None = None,
) -> dict:
    """Run both original contracts from ONE immutable closed synthetic input.

    The independent 4h prior mode is derived ONLY if explicitly requested;
    it is never inferred from N10 daily/weekly context. Unapproved N03 stays
    unavailable. A synthetic research key cannot become a signal ID.
    """
    if not isinstance(horizon, Horizon) or not isinstance(direction, Direction):
        raise Unavailable("BUNDLE_HORIZON_DIRECTION_REQUIRED")
    if not isinstance(witness, ClockWitness):
        raise Unavailable("BUNDLE_CLOCK_WITNESS_REQUIRED")
    if not isinstance(tolerance, ReconciliationTolerance):
        raise Unavailable("BUNDLE_TOLERANCE_REQUIRED")
    if not isinstance(context, Mapping):
        raise Unavailable("BUNDLE_CONTEXT_MAPPING_REQUIRED")
    if not isinstance(parent, CandleWindow):
        raise Unavailable("BUNDLE_PARENT_WINDOW_REQUIRED")
    decision_at = utc(decision_at)
    source_id = parent.source_id
    frame, child_frame, count = _FRAMES[horizon]
    raw_parent = _closed(parent, frame=frame, source_id=source_id,
                         decision_at=decision_at, witness=witness)
    if not isinstance(children, (tuple, list)) or len(children) != count:
        raise Unavailable("BUNDLE_CHILD_COUNT_MISMATCH")
    raw_children = tuple(_closed(
        b, frame=child_frame, source_id=source_id,
        decision_at=decision_at, witness=witness) for b in children)
    if not isinstance(core_5m, (tuple, list)) or len(core_5m) != 21:
        raise Unavailable("BUNDLE_CORE_21_CLOSED_5M_REQUIRED")
    for bar in core_5m:
        _closed(bar, frame="5m", source_id=source_id,
                decision_at=decision_at, witness=witness)
    core = tuple(_core(bar) for bar in core_5m)
    # Preserve the direct source link between Stage01's base+quote volumes and
    # the separate R2 quote-only parent/children; no reconstructed base volume.
    if horizon is Horizon.INTRADAY and tuple(core_5m[-count:]) != tuple(children):
        raise Unavailable("BUNDLE_CORE_CHILD_SOURCE_OR_BASE_VOLUME_MISMATCH")
    raw_context: dict[str, tuple[Candle, ...]] = {}
    for key, bars in context.items():
        frame_name = "4h" if key == "structure4h" else key
        if frame_name not in ("5m", "30m", "1h", "4h", "1d", "1w"):
            raise Unavailable("BUNDLE_CONTEXT_FRAME_UNKNOWN")
        if not isinstance(bars, (tuple, list)):
            raise Unavailable("BUNDLE_CONTEXT_SEQUENCE_REQUIRED")
        raw_context[key] = tuple(_closed(
            b, frame=frame_name, source_id=source_id,
            decision_at=decision_at, witness=witness) for b in bars)
    if horizon is Horizon.INTRADAY:
        history = context.get("5m", ())
        if len(history) < 15 or tuple(history[-15:]) != tuple(core_5m[:15]):
            raise Unavailable("BUNDLE_CORE_5M_CONTEXT_NOT_IDENTICAL")

    if prior_mode_4h is not None and mode_source_evidence is not None:
        raise Unavailable("BUNDLE_TWO_MODE_AUTHORITIES_FORBIDDEN")
    if prior_mode_4h is not None:
        if len(prior_mode_4h) < 32:
            raise Unavailable("BUNDLE_PRIOR_MODE_32_BARS_REQUIRED")
        mode_bars = tuple(_closed(
            b, frame="4h", source_id=source_id,
            decision_at=parent.open_at, witness=witness) for b in prior_mode_4h)
        mode_source_evidence = derive_prior_mode_from_4h(
            history=mode_bars, direction=direction, horizon=horizon,
            parent_open_at=parent.open_at, decision_at=decision_at,
            witness=witness)
        if mode_source_evidence.mode != mode:
            raise Unavailable("BUNDLE_INDEPENDENT_MODE_CONFLICT")
    if (mode_source_evidence is not None
            and mode_source_evidence.source_id != source_id):
        raise Unavailable("BUNDLE_PRIOR_MODE_SOURCE_MISMATCH")

    if not isinstance(ticker24, Ticker24Packet) or ticker24.base_volume is None:
        raise Unavailable("BUNDLE_24H_BASE_VOLUME_EXPLICIT_REQUIRED")
    market = market_from_explicit_packets(
        book=book, ticker=ticker24, decision_at=decision_at, witness=witness)
    if book.symbol != symbol:
        raise Unavailable("BUNDLE_MARKET_SYMBOL_MISMATCH")
    # A decision-time composite view, explicitly NOT an atomic book+24h tick.
    snapshot = MarketSnapshot(
        symbol, market.quote_asset, market.spot_usdt_trading,
        market.trading_status, market.quote_24h, market.bid, market.ask,
        decision_at)
    n03 = None
    if operational_n03_5m is not None:
        n03 = tuple(_closed(
            b, frame="5m", source_id=source_id,
            decision_at=decision_at, witness=witness) for b in operational_n03_5m)
    readiness = dict(
        symbol=symbol, horizon=horizon, direction=direction,
        parent=parent, children=tuple(children), core_5m=core,
        market=snapshot, decision_at=decision_at, tolerance=tolerance,
        event_discriminator=event_discriminator,
    )
    r2 = dict(
        horizon=horizon, direction=direction, mode=mode,
        parent=raw_parent, children=raw_children,
        context=raw_context, market=market,
        witness=witness, decision_at=decision_at,
    )
    return stage03_r2_functional_e2e(
        r2_inputs=r2, readiness_inputs=readiness,
        market_source_packets=(book, ticker24),
        mode_source_evidence=mode_source_evidence,
        operational_n03_5m=n03,
    )
