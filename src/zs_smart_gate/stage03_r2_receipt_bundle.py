"""Offline receipt-record entrypoint to existing Stage01/03A/R2 research.

Consumes an explicit, synthetic, closed source record. No network, implicit
clock, inferred quote/base volume, score, signal ID, or publishing capability.
This serializer boundary is NOT provenance or real point-in-time certification.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Mapping

from .mtf_contracts import CandleWindow, ReconciliationTolerance
from .stage03a_contracts import Direction, Horizon
from .stage03_r2_closed_bundle import stage03_r2_from_closed_bundle
from .stage03_r2_offline import ClockWitness, SourceReceipt, Unavailable, number
from .stage03_r2_source_contract import (
    BookTickerPacket, ticker24_from_public_fields,
)

SCHEMA = "ZS03_SYNTHETIC_CLOSED_RECEIPTS_V1"
_UTC_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)\Z")
_CANDLE_KEYS = frozenset((
    "timeframe", "open_at", "close_at", "received_at", "available_at",
    "source_id", "open", "high", "low", "close", "base_volume", "quote_volume",
))
_RECEIPT_KEYS = frozenset(("observed_at", "received_at", "available_at", "source_id"))
_CONTEXT_FRAMES = frozenset(("5m", "30m", "1h", "4h", "1d", "1w", "structure4h"))
_REQUIRED = frozenset((
    "schema", "symbol", "horizon", "direction", "mode", "parent",
    "children", "core_5m", "context", "book", "ticker24", "witness",
    "decision_at", "tolerance", "event_discriminator",
))
_OPTIONAL = frozenset(("prior_mode_4h", "operational_n03_5m"))


def _fields(value: object, expected: frozenset[str], label: str) -> Mapping:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise Unavailable("RECEIPT_RECORD_FIELDS_INVALID:" + label)
    return value


def _time(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not _UTC_ISO.fullmatch(value):
        raise Unavailable("RECEIPT_EXPLICIT_UTC_REQUIRED:" + label)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Unavailable("RECEIPT_EXPLICIT_UTC_INVALID:" + label) from exc
    if parsed.utcoffset() != timedelta(0):
        raise Unavailable("RECEIPT_EXPLICIT_UTC_REQUIRED:" + label)
    return parsed


def _decimal(value: object, label: str) -> Decimal:
    # Price/volume values in source JSON must be decimal STRINGS: no floats,
    # booleans, synthesized volume or lossy binary representations.
    if not isinstance(value, str) or not value.strip():
        raise Unavailable("RECEIPT_DECIMAL_STRING_REQUIRED:" + label)
    return number(value)


def _window(value: object) -> CandleWindow:
    d = _fields(value, _CANDLE_KEYS, "CANDLE")
    if not isinstance(d["timeframe"], str) or not isinstance(d["source_id"], str):
        raise Unavailable("RECEIPT_CANDLE_FRAME_OR_SOURCE_INVALID")
    return CandleWindow(
        d["timeframe"], _time(d["open_at"], "OPEN"),
        _time(d["close_at"], "CLOSE"),
        _time(d["received_at"], "RECEIVED"),
        _time(d["available_at"], "AVAILABLE"),
        d["source_id"],
        _decimal(d["open"], "OPEN_PRICE"),
        _decimal(d["high"], "HIGH_PRICE"),
        _decimal(d["low"], "LOW_PRICE"),
        _decimal(d["close"], "CLOSE_PRICE"),
        _decimal(d["base_volume"], "BASE_VOLUME"),
        _decimal(d["quote_volume"], "QUOTE_VOLUME"),
    )


def _sequence(value: object, label: str) -> tuple[CandleWindow, ...]:
    if not isinstance(value, (list, tuple)):
        raise Unavailable("RECEIPT_SEQUENCE_REQUIRED:" + label)
    return tuple(_window(x) for x in value)


def _receipt(value: object) -> SourceReceipt:
    d = _fields(value, _RECEIPT_KEYS, "SOURCE_RECEIPT")
    return SourceReceipt(
        _time(d["observed_at"], "OBSERVED"),
        _time(d["received_at"], "RECEIVED"),
        _time(d["available_at"], "AVAILABLE"), d["source_id"],
    )


def stage03_r2_from_closed_receipts(record: Mapping[str, object]) -> dict:
    """Single-call synthetic source rows -> typed contracts -> research result.

    Rejects incomplete or ambiguous original units and UTC receipts before
    invoking the existing Stage03 bridge. No score or source authenticity claim.
    """
    if not isinstance(record, Mapping) or not _REQUIRED <= set(record) or set(record) - (_REQUIRED | _OPTIONAL):
        raise Unavailable("RECEIPT_BUNDLE_SCHEMA_FIELDS_INVALID")
    if record["schema"] != SCHEMA:
        raise Unavailable("RECEIPT_BUNDLE_SCHEMA_VERSION_INVALID")
    try:
        horizon = Horizon(record["horizon"])
        direction = Direction(record["direction"])
    except (ValueError, TypeError) as exc:
        raise Unavailable("RECEIPT_BUNDLE_HORIZON_DIRECTION_INVALID") from exc
    if not isinstance(record["symbol"], str) or not record["symbol"].strip():
        raise Unavailable("RECEIPT_BUNDLE_SYMBOL_REQUIRED")
    if not isinstance(record["event_discriminator"], str) or not record["event_discriminator"].strip():
        raise Unavailable("RECEIPT_BUNDLE_EVENT_DISCRIMINATOR_REQUIRED")
    decision = _time(record["decision_at"], "DECISION")
    w = _fields(record["witness"], frozenset((
        "independent_reference", "uncertainty_seconds", "synthetic")), "WITNESS")
    if w["synthetic"] is not True:
        raise Unavailable("RECEIPT_REAL_CLOCK_UNSUPPORTED")
    witness = ClockWitness(
        w["independent_reference"],
        _decimal(w["uncertainty_seconds"], "CLOCK_UNCERTAINTY"),
        synthetic=True,
    )
    t = _fields(record["tolerance"], frozenset((
        "price", "base_volume", "quote_volume", "policy_id")), "TOLERANCE")
    tolerance = ReconciliationTolerance(
        _decimal(t["price"], "PRICE_TOLERANCE"),
        _decimal(t["base_volume"], "BASE_TOLERANCE"),
        _decimal(t["quote_volume"], "QUOTE_TOLERANCE"), t["policy_id"],
    )
    book = _fields(record["book"], frozenset((
        "symbol", "quote_asset", "trading_status", "spot_enabled", "bid", "ask", "receipt")), "BOOK")
    if type(book["spot_enabled"]) is not bool:
        raise Unavailable("RECEIPT_BOOK_SPOT_BOOLEAN_REQUIRED")
    typed_book = BookTickerPacket(
        book["symbol"], book["quote_asset"], book["trading_status"],
        book["spot_enabled"], _decimal(book["bid"], "BID"),
        _decimal(book["ask"], "ASK"), _receipt(book["receipt"]),
    )
    ticker = _fields(record["ticker24"], frozenset((
        "symbol", "quote_asset", "endpoint", "payload", "receipt")), "TICKER24")
    payload = ticker["payload"]
    if not isinstance(payload, Mapping) or any(
        key not in payload or not isinstance(payload[key], str)
        for key in ("symbol", "volume", "quoteVolume")
    ):
        raise Unavailable("RECEIPT_TICKER24_EXPLICIT_VOLUME_STRINGS_REQUIRED")
    typed_ticker = ticker24_from_public_fields(
        raw=payload, endpoint=ticker["endpoint"], symbol=ticker["symbol"],
        quote_asset=ticker["quote_asset"], receipt=_receipt(ticker["receipt"]),
    )
    context = record["context"]
    if not isinstance(context, Mapping) or any(key not in _CONTEXT_FRAMES for key in context):
        raise Unavailable("RECEIPT_BUNDLE_CONTEXT_INVALID")
    return stage03_r2_from_closed_bundle(
        symbol=record["symbol"], horizon=horizon, direction=direction,
        mode=record["mode"], parent=_window(record["parent"]),
        children=_sequence(record["children"], "CHILDREN"),
        core_5m=_sequence(record["core_5m"], "CORE_5M"),
        context={key: _sequence(bars, "CONTEXT:" + key)
                 for key, bars in context.items()},
        book=typed_book, ticker24=typed_ticker, witness=witness,
        decision_at=decision, tolerance=tolerance,
        event_discriminator=record["event_discriminator"],
        prior_mode_4h=(_sequence(record["prior_mode_4h"], "PRIOR_MODE")
                       if "prior_mode_4h" in record else None),
        operational_n03_5m=(_sequence(record["operational_n03_5m"], "N03")
                            if "operational_n03_5m" in record else None),
    )
