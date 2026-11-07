"""PM 6707403159: strictly offline, synthetic-only Stage03 source contracts.

These contracts validate semantic identity and causal source receipts. They
do not authorize Binance connections, attest independent clock events,
approve the definition of 'full impulse', or qualify a market signal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Sequence

from .stage03a_contracts import Direction, Horizon
from .stage03_r2_offline import (
    Candle, ClockWitness, Market, SourceReceipt, Unavailable, asof, liquidity,
    number, utc,
)

VERSION = "ZS03_R2_SOURCE_CONTRACT_OFFLINE_UNAPPROVED_V1"
MODES = frozenset(("CONTINUATION", "REVERSAL"))


class ImpulseState(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


def _identifier(value: str, *, reason: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise Unavailable(reason)


@dataclass(frozen=True)
class VersionedFullImpulsePredicate:
    predicate_id: str
    version: str
    definition_sha256: str
    timeframe: str
    direction: Direction
    horizon: Horizon
    mode: str
    definition_status: str = "UNAPPROVED"

    def __post_init__(self) -> None:
        _identifier(self.predicate_id, reason="IMPULSE_PREDICATE_ID_MISSING")
        _identifier(self.version, reason="IMPULSE_PREDICATE_VERSION_MISSING")
        if not isinstance(self.definition_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.definition_sha256
        ):
            raise Unavailable("IMPULSE_DEFINITION_SHA_INVALID")
        if (self.timeframe != "5m" or not isinstance(self.direction, Direction)
                or not isinstance(self.horizon, Horizon) or self.mode not in MODES):
            raise Unavailable("IMPULSE_PREDICATE_SCOPE_INVALID")
        # No caller-supplied boolean or arbitrary metadata can grant approval.
        if self.definition_status != "UNAPPROVED":
            raise Unavailable("IMPULSE_DEFINITION_APPROVAL_NOT_AUTHORIZED")


@dataclass(frozen=True)
class CausalImpulseObservation:
    open_at: datetime
    close_at: datetime
    observed_at: datetime
    received_at: datetime
    available_at: datetime
    decision_at: datetime
    source_id: str
    state: ImpulseState

    def __post_init__(self) -> None:
        for name in ("open_at", "close_at", "observed_at", "received_at",
                     "available_at", "decision_at"):
            object.__setattr__(self, name, utc(getattr(self, name)))
        if not isinstance(self.state, ImpulseState):
            raise Unavailable("FULL_IMPULSE_STATE_UNKNOWN_OR_INVALID")
        if not isinstance(self.source_id, str) or not self.source_id.startswith("SYNTHETIC:"):
            raise Unavailable("FULL_IMPULSE_SOURCE_UNTRUSTED")
        if not (self.open_at < self.close_at <= self.observed_at
                <= self.received_at <= self.available_at <= self.decision_at):
            raise Unavailable("FULL_IMPULSE_RECEIPT_ORDER_INVALID")


def inspect_full_impulse_trace(
    *, definition: VersionedFullImpulsePredicate | None,
    trace: Sequence[CausalImpulseObservation] | None,
    candles: Sequence[Candle],
    direction: Direction,
    horizon: Horizon,
    mode: str,
    decision_at: datetime,
    witness: ClockWitness,
) -> dict:
    """Validate a 39-history + 6-child 5m trace without asserting predicate truth.

    The diagnostic accepts explicitly known TRUE/FALSE observations yet cannot
    promote them to an *approved* full-impulse predicate. Unknown is not False.
    """
    decision_at = utc(decision_at)
    if definition is None or trace is None:
        raise Unavailable("FULL_IMPULSE_DEFINITION_OR_TRACE_MISSING")
    if not isinstance(definition, VersionedFullImpulsePredicate):
        raise Unavailable("FULL_IMPULSE_PREDICATE_CONTRACT_REQUIRED")
    if (definition.direction is not direction or definition.horizon is not horizon
            or definition.mode != mode):
        raise Unavailable("FULL_IMPULSE_SCOPE_MISMATCH")
    if len(candles) != 45 or len(trace) != len(candles):
        raise Unavailable("FULL_IMPULSE_TRACE_LENGTH_MISMATCH")
    if any(not isinstance(x, CausalImpulseObservation) for x in trace):
        raise Unavailable("FULL_IMPULSE_TRACE_TYPE_INVALID")
    previous_close = None
    states: list[str] = []
    for bar, item in zip(candles, trace):
        if (bar.source_id != item.source_id or bar.open_at != item.open_at
                or bar.close_at != item.close_at
                or item.received_at < bar.received_at
                or item.available_at < bar.available_at
                or item.decision_at != decision_at):
            raise Unavailable("FULL_IMPULSE_TRACE_CANDLE_OR_RECEIPT_MISMATCH")
        if previous_close is not None and item.open_at != previous_close:
            raise Unavailable("FULL_IMPULSE_TRACE_GAP")
        asof(item.available_at, decision_at, witness)
        states.append(item.state.value)
        previous_close = item.close_at
    if "UNKNOWN" in states:
        raise Unavailable("FULL_IMPULSE_TRACE_UNKNOWN")
    return {
        "contract": VERSION,
        "predicate_id": definition.predicate_id,
        "predicate_version": definition.version,
        "definition_sha256": definition.definition_sha256,
        "definition_status": "UNAPPROVED",
        "trace_state": "COMPLETE_CAUSAL_SYNTHETIC_UNAPPROVED",
        "observations": len(trace),
        "full_impulse_event_approved": False,
        "n03_status": "UNAVAILABLE",
        "reason": "FULL_IMPULSE_DEFINITION_UNAPPROVED",
    }


@dataclass(frozen=True)
class BookTickerPacket:
    symbol: str
    quote_asset: str
    trading_status: str
    spot_enabled: bool
    bid: Decimal
    ask: Decimal
    receipt: SourceReceipt

    def __post_init__(self) -> None:
        _identifier(self.symbol, reason="BOOK_SYMBOL_MISSING")
        if not isinstance(self.receipt, SourceReceipt):
            raise Unavailable("BOOK_SOURCE_RECEIPT_REQUIRED")
        if type(self.spot_enabled) is not bool:
            raise Unavailable("BOOK_SPOT_ELIGIBILITY_UNKNOWN")
        object.__setattr__(self, "bid", number(self.bid))
        object.__setattr__(self, "ask", number(self.ask))


@dataclass(frozen=True)
class Ticker24Packet:
    symbol: str
    quote_asset: str
    quote_volume: Decimal
    volume_unit: str
    window: str
    receipt: SourceReceipt

    def __post_init__(self) -> None:
        _identifier(self.symbol, reason="TICKER_SYMBOL_MISSING")
        if not isinstance(self.receipt, SourceReceipt):
            raise Unavailable("TICKER_SOURCE_RECEIPT_REQUIRED")
        object.__setattr__(self, "quote_volume", number(self.quote_volume))


def market_from_explicit_packets(
    *, book: BookTickerPacket, ticker: Ticker24Packet,
    decision_at: datetime, witness: ClockWitness
) -> Market:
    """Pure adapter; the caller provides TWO independent synthetic receipts.

    No atomicity is inferred between bookTicker and rolling 24h ticker. The
    real-source data path remains entirely disabled; this is not a network API.
    """
    if not isinstance(book, BookTickerPacket) or not isinstance(ticker, Ticker24Packet):
        raise Unavailable("BOOK_AND_TICKER_TYPED_PACKETS_REQUIRED")
    if (book.symbol != ticker.symbol or book.quote_asset != ticker.quote_asset
            or book.quote_asset != "USDT"):
        raise Unavailable("BOOK_TICKER_SYMBOL_OR_QUOTE_CONFLICT")
    if not book.spot_enabled or book.trading_status != "TRADING":
        raise Unavailable("BOOK_SYMBOL_NOT_SPOT_TRADING")
    if ticker.volume_unit != "USDT" or ticker.window != "ROLLING_24H":
        raise Unavailable("TICKER_24H_QUOTE_UNIT_OR_WINDOW_INVALID")
    if not isinstance(witness, ClockWitness):
        raise Unavailable("SYNTHETIC_CLOCK_WITNESS_REQUIRED")
    market = Market(
        book.receipt, ticker.receipt, book.bid, book.ask, ticker.quote_volume,
        spot_usdt_trading=True, quote_asset=book.quote_asset,
        trading_status=book.trading_status, ticker24_unit=ticker.volume_unit,
        ticker24_window=ticker.window,
    )
    # Conservative independent as-of/TTL and arithmetic guards, no new formula.
    liquidity(market, decision_at, witness)
    return market


@dataclass(frozen=True)
class ModeSourceEvidence:
    mode: str
    direction: Direction
    horizon: Horizon
    mode_source: str
    mode_version: str
    source_id: str
    context_close_at: datetime
    observed_at: datetime
    received_at: datetime
    available_at: datetime
    decision_at: datetime

    def __post_init__(self) -> None:
        for name in ("context_close_at", "observed_at", "received_at",
                     "available_at", "decision_at"):
            object.__setattr__(self, name, utc(getattr(self, name)))
        if self.mode not in MODES or not isinstance(self.direction, Direction) or not isinstance(self.horizon, Horizon):
            raise Unavailable("MODE_SCOPE_INVALID")
        _identifier(self.mode_source, reason="MODE_SOURCE_MISSING")
        _identifier(self.mode_version, reason="MODE_VERSION_MISSING")
        if not isinstance(self.source_id, str) or not self.source_id.startswith("SYNTHETIC:"):
            raise Unavailable("MODE_CAUSAL_SOURCE_REQUIRED")
        if not (self.context_close_at <= self.observed_at <= self.received_at
                <= self.available_at <= self.decision_at):
            raise Unavailable("MODE_RECEIPT_ORDER_INVALID")


def require_prior_mode(
    evidence: ModeSourceEvidence | None, *,
    mode: str, direction: Direction, horizon: Horizon,
    parent: Candle, decision_at: datetime, witness: ClockWitness,
) -> dict:
    """Require an *independently supplied* synthetic mode before parent open.

    N10's direction/context must never generate a mode or CHoCH.
    """
    if not isinstance(evidence, ModeSourceEvidence):
        raise Unavailable("MODE_SOURCE_EVIDENCE_MISSING")
    if (evidence.mode != mode or evidence.direction is not direction
            or evidence.horizon is not horizon
            or evidence.decision_at != utc(decision_at)):
        raise Unavailable("MODE_SOURCE_SCOPE_OR_DECISION_MISMATCH")
    if evidence.context_close_at > parent.open_at:
        raise Unavailable("MODE_CONTEXT_AFTER_PARENT_OPEN")
    asof(evidence.available_at, parent.open_at, witness)
    return {
        "mode": evidence.mode, "mode_source": evidence.mode_source,
        "mode_version": evidence.mode_version,
        "source_id": evidence.source_id,
        "context_close_at": evidence.context_close_at.isoformat(),
        "available_at": evidence.available_at.isoformat(),
        "status": "SYNTHETIC_ASOF_CHECKED_NOT_REAL_PIT",
    }
