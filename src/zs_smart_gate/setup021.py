"""ORDER-021 Setup v1: one frozen, offline research detector.

Reuses the accepted Binance kline parser, bounded scanner inspection and core
candidate. This module imports no network service, sender, schedule or trader.
An internal DETECTED_SIGNAL is *not* a qualified or publishable trade signal.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import hashlib
import json
from statistics import median

from .binance_live import to_candles
from .core import MarketSnapshot, utc, validate_candles
from .scanner import UniverseItem, inspect_candles

VERSION = "ORDER021_SETUP_V1_FROZEN"
SOURCE = "BINANCE_SPOT_REST_5M_REPLAY"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
LOOKBACK = 20
VOLUME_FACTOR = Decimal("1.20")
MAX_RECEIPT_DELAY_SECONDS = 90
PARTITIONS = ("DEV", "OOS")
FIVE_MS = 300000
CONFIG = {
    "version": VERSION,
    "source": SOURCE,
    "symbols": list(SYMBOLS),
    "direction": "UP",
    "horizon": "INTRADAY_5M",
    "setup_id": "CLOSED_20_HIGH_BREAKOUT_QUOTE_VOLUME_1P20",
    "lookback_closed_bars": LOOKBACK,
    "quote_volume_factor": "1.20",
    "trigger": "close > previous_20_high AND close > open AND quote_volume >= 1.20 * previous_20_mean_quote_volume",
    "transition": "previous_predicate_FALSE_to_current_TRUE",
    "max_receipt_delay_seconds": MAX_RECEIPT_DELAY_SECONDS,
    "missing": "RESEARCH_CANDIDATE_ONLY",
    "score": "SCORE_UNAVAILABLE",
    "historical_pit": "HISTORICAL_PIT_UNVERIFIED",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


CONFIG_SHA256 = digest(CONFIG)


def _predicate(window):
    """21 validated closed candles: previous 20 vs final, never use future."""
    history, current = window[:-1], window[-1]
    if len(history) != LOOKBACK:
        raise ValueError("SETUP_LOOKBACK_NOT_MET")
    mean_quote = sum((x.quote_volume for x in history), Decimal(0)) / LOOKBACK
    if mean_quote <= 0:
        raise ValueError("VOLUME_BASELINE_MISSING")
    return (
        current.close > max(x.high for x in history)
        and current.close > current.open
        and current.quote_volume >= VOLUME_FACTOR * mean_quote
    )


def _candidate(symbol, partition, last_open_ms, reason, *, core_status="NOT_EVALUATED"):
    key = dict(version=VERSION, symbol=symbol, partition=partition, trigger_open_ms=last_open_ms)
    return {
        "contract_version": VERSION,
        "contract_sha256": CONFIG_SHA256,
        "partition": partition,
        "symbol": symbol,
        "direction": "UP",
        "horizon": "INTRADAY_5M",
        "status": "RESEARCH_CANDIDATE",
        "reason_codes": [reason],
        "core_status": core_status,
        "event_id": None,
        "row_key": digest(key),
        "score_status": "SCORE_UNAVAILABLE",
        "score": None,
        "probability": None,
        "publishable": False,
        "qualified": False,
        "historical_pit": "HISTORICAL_PIT_UNVERIFIED",
        "source": SOURCE,
    }


def evaluate(*, symbol, klines, market: MarketSnapshot, received_at, decision_at, partition):
    """Offline replay. 22 consecutive 5m bars allow two full 21-bar predicates.

    kline[6] is Binance's inclusive close millisecond. A forming/late bar
    must never silently fall back to the previous bar in to_candles().
    Arrival fields are replay metadata, NOT verified historical publication.
    """
    if partition not in PARTITIONS:
        raise ValueError("PARTITION_UNAUTHORIZED_OR_PROSPECTIVE_NOT_APPROVED")
    if symbol not in SYMBOLS:
        raise ValueError("SETUP_SYMBOL_NOT_ALLOWED")
    decision_at, received_at = utc(decision_at), utc(received_at)
    if not isinstance(klines, list) or len(klines) != LOOKBACK + 2:
        return _candidate(symbol, partition, None, "EXACTLY_22_CLOSED_BARS_REQUIRED")
    try:
        last_open_ms = int(klines[-1][0])
        last_close_ms = int(klines[-1][6]) + 1
    except (ValueError, TypeError, IndexError):
        return _candidate(symbol, partition, None, "INVALID_LAST_KLINE_TIMESTAMP")
    result = _candidate(symbol, partition, last_open_ms, "UNDETERMINED")
    if last_open_ms % FIVE_MS or last_close_ms != last_open_ms + FIVE_MS:
        result["reason_codes"] = ["KLINE_BOUNDARY_INVALID"]
        return result
    if (received_at > decision_at or
        last_close_ms > int(received_at.timestamp() * 1000) or
        last_close_ms > int(decision_at.timestamp() * 1000)):
        result["reason_codes"] = ["FORMING_OR_FUTURE_OR_NOT_YET_RECEIVED"]
        return result
    if (decision_at - received_at > timedelta(seconds=MAX_RECEIPT_DELAY_SECONDS) or
        received_at.timestamp() * 1000 - last_close_ms > MAX_RECEIPT_DELAY_SECONDS * 1000):
        result["reason_codes"] = ["STALE_OBSERVATION"]
        return result
    if market.symbol != symbol:
        result["reason_codes"] = ["MARKET_SYMBOL_MISMATCH"]
        return result
    try:
        old_window = to_candles(klines[:-1], received_at)
        now_window = to_candles(klines, received_at)
        errors = validate_candles(old_window, decision_at) + validate_candles(now_window, decision_at)
        if errors:
            result["reason_codes"] = ["INVALID_CANDLE_WINDOW"] + list(errors[:5])
            return result
        item = UniverseItem(symbol, "ELIGIBLE", (), "ORDER021_OFFLINE_ONLY", market)
        inspection = inspect_candles(item, klines, received_at, decision_at, 0.0)
        result["core_status"] = inspection.status
        if inspection.status != "PASS" or inspection.candidate is None:
            result["reason_codes"] = ["SCANNER_OR_CORE_REJECTED"] + list(inspection.reasons[:5])
            return result
        old_condition = _predicate(old_window)
        new_condition = _predicate(now_window)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        # Do not embed untrusted market source/body in a result.
        result["reason_codes"] = ["PARSER_OR_PREDICATE_REJECTED", type(exc).__name__]
        return result
    result["reason_codes"] = (["NO_BREAKOUT"] if not new_condition else
        ["NO_FALSE_TO_TRUE_TRANSITION"] if old_condition else ["CLOSED_CAUSAL_TRIGGER"])
    result["previous_condition"] = old_condition
    result["current_condition"] = new_condition
    if not new_condition or old_condition:
        return result
    event = {
        "contract_version": VERSION,
        "symbol": symbol,
        "direction": "UP",
        "horizon": "INTRADAY_5M",
        "setup_id": CONFIG["setup_id"],
        "trigger_closed_candle_time_ms": last_close_ms,
        "source_event_identity": f"{SOURCE}:{symbol}:5m:{last_open_ms}",
    }
    result["status"] = "DETECTED_SIGNAL"
    result["event_id"] = digest(event)
    result["event_identity_fields"] = event
    return result
