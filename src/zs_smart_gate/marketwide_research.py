"""ORDER006: explicit full-inventory research and symmetric directional hypotheses.

No scientific qualification registry, sender, scheduler or trading capability.
The frozen ORDER021 detector is preserved. Numerical hypotheses here are DEV only.
"""
from collections import Counter
from dataclasses import asdict
from datetime import timedelta
import re
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

from .binance_live import LiveFailure, is_spot_enabled, timestamp, to_candles
from .core import MarketSnapshot, check_eligibility, decimal, validate_candles
from .mtf_contracts import CandleWindow, DURATIONS, ReconciliationTolerance, reconcile
from .stage05_contracts import canonical, digest, parse_utc

VERSION = "ZS_MARKETWIDE_DIRECTIONAL_RESEARCH_V1"
FEED = "BINANCE_SPOT_PUBLIC_REST"
FRAMES = {"5m": 300000, "30m": 1800000, "1h": 3600000, "4h": 14400000}
STRATEGIES = MappingProxyType({
    "UP": "DEV_CLOSED_20_HIGH_BREAKOUT_V1",
    "DOWN": "DEV_CLOSED_20_LOW_BREAKDOWN_V1",
})
HYPOTHESIS = {
    "version": VERSION, "lookback": 20, "quote_volume_factor": "1.20",
    "transition": "FALSE_TO_TRUE", "max_age_seconds": 90,
    "scope": "DEVELOPMENT_HYPOTHESIS_NOT_APPROVED_SCIENTIFIC_POLICY",
    "strategies": dict(STRATEGIES),
}
POLICY_SHA256 = digest(canonical(HYPOTHESIS))
DETECTOR_SHA256 = digest(Path(__file__).read_bytes().replace(b"\r\n", b"\n"))
REAL_DIRECTION_POLICIES = MappingProxyType({"UP": None, "DOWN": None})


def _index(rows):
    result = {}
    for row in rows:
        symbol = row["symbol"]
        if not isinstance(symbol, str) or not symbol or symbol in result:
            raise ValueError("DUPLICATE_OR_INVALID_SYMBOL")
        result[symbol] = row
    return result


def inventory(receipts, decision_at, *, scope):
    """One row for every instrument returned by the supplied exchangeInfo."""
    if scope not in ("ALL_BINANCE_SPOT_INVENTORY", "RECORDED_BOUNDED_INVENTORY", "SYNTHETIC"):
        raise ValueError("INVENTORY_SCOPE_REQUIRED")
    if [r["path"] for r in receipts] != ["exchangeInfo", "ticker/24hr", "ticker/bookTicker"]:
        raise ValueError("INVENTORY_ENDPOINT_ORDER")
    if scope == "ALL_BINANCE_SPOT_INVENTORY" and (
            receipts[0]["params"] not in ({}, {"showPermissionSets": "false"})
            or any(r["params"] for r in receipts[1:])):
        raise ValueError("FULL_INVENTORY_CANNOT_USE_SYMBOL_FILTER")
    arrivals = [parse_utc(r["received_at"]) for r in receipts]
    decision = parse_utc(decision_at)
    if arrivals != sorted(arrivals) or not arrivals[-1] <= decision:
        raise ValueError("INVENTORY_AVAILABLE_AFTER_DECISION")
    listing = _index(receipts[0]["payload"]["symbols"])
    tickers, books = (_index(r["payload"]) for r in receipts[1:])
    if not 1 <= len(listing) <= 20000:
        raise ValueError("INVENTORY_RESOURCE_BOUND")
    rows = []
    for symbol, info in sorted(listing.items()):
        reasons = []
        market = None
        spot = is_spot_enabled(info)
        active = spot and info.get("status") == "TRADING"
        if not active:
            reasons.append("SPOT_NOT_TRADABLE")
        if info.get("quoteAsset") != "USDT":
            reasons.append("UNSUPPORTED_QUOTE_POLICY")
        if (not info.get("baseAsset") or not info.get("quoteAsset")
                or symbol != info.get("baseAsset", "") + info.get("quoteAsset", "")):
            reasons.append("ASSET_IDENTITY_MISSING")
        ticker, book = tickers.get(symbol), books.get(symbol)
        if ticker is None or book is None:
            reasons.append("MISSING_TICKER_OR_BOOK")
        else:
            try:
                age = (arrivals[1] - timestamp(int(ticker["closeTime"]))).total_seconds()
                if not 0 <= age <= 90 or (decision - arrivals[0]).total_seconds() > 90:
                    reasons.append("STALE_OR_FUTURE_INVENTORY")
                market = MarketSnapshot(symbol, info["quoteAsset"], spot, info["status"],
                                        ticker["quoteVolume"], book["bidPrice"], book["askPrice"],
                                        arrivals[1])
                # Existing USDT screen is a research scope filter, not qualification.
                if info["quoteAsset"] == "USDT":
                    reasons.extend(check_eligibility(market, decision))
            except (ValueError, TypeError, KeyError, OverflowError):
                reasons.append("INVALID_MARKET_DATA")
        market_data = None
        if market:
            market_data = asdict(market)
            for key in ("quote_volume_24h", "bid", "ask"):
                market_data[key] = str(market_data[key])
            market_data["observed_at"] = market.observed_at.isoformat()
        rows.append(dict(symbol=symbol, base=info.get("baseAsset"), quote=info.get("quoteAsset"),
                         active=active, eligible=not reasons, reasons=sorted(set(reasons)),
                         available_at=arrivals[-1].isoformat(), market=market_data))
    out = dict(version=VERSION, scope=scope, decision_at=decision_at,
               source_manifest_sha256=digest(canonical(receipts)), rows=rows,
               extra_tickers=sorted(set(tickers) - set(listing)),
               extra_books=sorted(set(books) - set(listing)))
    out["snapshot_sha256"] = digest(canonical(out))
    return out


def packet_from_receipts(item, receipts, *, boundary_ms, decision_at, scope, clock_status):
    """Bind symbol, requested endpoint/anchor, exact response rows and arrival times."""
    if len(receipts) != 4:
        raise ValueError("FOUR_TIMEFRAME_RECEIPTS_REQUIRED")
    frames = {}
    for receipt in receipts:
        params = receipt["params"]
        frame = params["interval"]
        if frame not in FRAMES or frame in frames:
            raise ValueError("FRAME_INVALID_OR_DUPLICATED")
        end = boundary_ms // FRAMES[frame] * FRAMES[frame]
        expected = dict(symbol=item["symbol"], interval=frame,
                        endTime=str(end - 1), limit=str(len(receipt["payload"])) if frame == "5m" else "1")
        if receipt["path"] != "klines" or params != expected:
            raise ValueError("SYMBOL_OR_FRAME_REQUEST_BINDING")
        frames[frame] = dict(rows=receipt["payload"], received_at=receipt["received_at"],
                             payload_sha256=digest(canonical(receipt["payload"])))
    return dict(symbol=item["symbol"], boundary_ms=boundary_ms, market=item["market"],
                frames=frames, decision_at=decision_at, source_scope=scope,
                source_manifest_sha256=digest(canonical(receipts)), clock_status=clock_status)


def _window(frame, row, received):
    period = FRAMES[frame]
    if len(row) < 11 or type(row[0]) is not int or type(row[6]) is not int:
        raise ValueError("INVALID_CANDLE_SCHEMA")
    if row[0] % period or row[6] + 1 != row[0] + period:
        raise ValueError("CANDLE_BOUNDARY_INVALID")
    return CandleWindow(frame, timestamp(row[0]), timestamp(row[6] + 1), received, received,
                        FEED, *row[1:6], row[7])


def _joined(packet):
    decision = parse_utc(packet["decision_at"])
    boundary = packet["boundary_ms"]
    if type(boundary) is not int or boundary % FRAMES["30m"]:
        raise ValueError("PARENT_BOUNDARY_INVALID")
    if set(packet["frames"]) != set(FRAMES):
        raise ValueError("MISSING_FRAME")
    windows = {}
    for frame, row in packet["frames"].items():
        if digest(canonical(row["rows"])) != row["payload_sha256"]:
            raise ValueError("SOURCE_PAYLOAD_HASH_MISMATCH")
        expected = 22 if frame == "5m" else 1
        if len(row["rows"]) != expected:
            raise ValueError("INSUFFICIENT_HISTORY")
        received = parse_utc(row["received_at"])
        windows[frame] = tuple(_window(frame, bar, received) for bar in row["rows"])
        if any(bar.errors_at(decision) for bar in windows[frame]):
            raise ValueError("FORMING_FUTURE_OR_INVALID_CANDLE")
        last = windows[frame][-1]
        if int(last.close_at.timestamp() * 1000) != boundary // FRAMES[frame] * FRAMES[frame]:
            raise ValueError("WRONG_CLOSED_ANCHOR")
        if decision - last.close_at >= DURATIONS[frame] + timedelta(seconds=90):
            raise ValueError("STALE_CONTEXT")
    bars = windows["5m"]
    if (decision - bars[-1].close_at).total_seconds() > 90:
        raise ValueError("STALE_TRIGGER_BOUNDARY")
    if any(b.close_at != a.open_at for b, a in zip(bars, bars[1:])):
        raise ValueError("CANDLE_GAP")
    children = bars[-6:]
    parent = windows["30m"][0]
    joined = reconcile(parent, children, decision,
                       tolerance=ReconciliationTolerance(0, 0, 0, "EXACT_BINANCE_SPOT"))
    if joined.status != "PASS":
        raise ValueError("INCOMPLETE_OR_REPAINTED_PARENT")
    market_data = packet["market"]
    market = MarketSnapshot(**{**market_data, "observed_at": parse_utc(market_data["observed_at"])})
    if market.symbol != packet["symbol"] or check_eligibility(market, decision):
        raise ValueError("MARKET_INELIGIBLE_OR_MISMATCH")
    if not 0 <= (decision - market.observed_at).total_seconds() <= 90:
        raise ValueError("STALE_OR_FUTURE_MARKET")
    return windows, decision


def _predicate(bars, direction):
    history, last = bars[:-1], bars[-1]
    mean = sum((b.quote_volume for b in history), Decimal(0)) / 20
    if mean <= 0:
        raise ValueError("VOLUME_BASELINE_MISSING")
    price = (last.close > max(b.high for b in history) and last.close > last.open
             if direction == "UP" else
             last.close < min(b.low for b in history) and last.close < last.open)
    return price and last.quote_volume >= Decimal("1.20") * mean


def evaluate(packet):
    """Both research paths share identical source and context admission."""
    identity = dict(version=VERSION, symbol=packet.get("symbol"),
                    boundary_ms=packet.get("boundary_ms"), source_scope=packet.get("source_scope"))
    common = dict(signal_id=None, publishable=False, qualification="QV1_REAL_POLICY_BLOCKED",
                  detector_sha256=DETECTOR_SHA256,
                  policy_sha256=POLICY_SHA256, input_sha256=digest(canonical(packet)),
                  source_manifest_sha256=packet.get("source_manifest_sha256"))
    try:
        windows, _ = _joined(packet)
        bars = windows["5m"]
        # Existing parser/validator is reused for both 21-bar windows.
        frame = packet["frames"]["5m"]
        received = parse_utc(frame["received_at"])
        for raw in (frame["rows"][:-1], frame["rows"]):
            if validate_candles(to_candles(raw, received), parse_utc(packet["decision_at"])):
                raise ValueError("INVALID_CANDLE_WINDOW")
        rows = []
        for direction in STRATEGIES:
            before = _predicate(bars[:-1], direction)
            current = _predicate(bars[1:], direction)
            trigger = current and not before
            status = "CANDIDATE_SHADOW_ONLY" if trigger else "NO_TRIGGER"
            reason = ("CLOSED_CAUSAL_TRIGGER" if trigger else
                      "NO_FALSE_TO_TRUE_TRANSITION" if current else "NO_BREAKOUT_OR_BREAKDOWN")
            clock_pair = (packet.get("source_scope"), packet.get("clock_status"))
            if clock_pair not in (
                    ("SYNTHETIC_TEST_ONLY", "SYNTHETIC_TEST_CLOCK"),
                    ("RECORDED_PUBLIC_SPOT", "RECORDED_CONDITIONAL_BRACKET"),
                    ("PUBLIC_SPOT_CONDITIONAL_RESEARCH", "OPERATIONAL_TIME_ACCEPTED")):
                status, reason = "QUALIFICATION_BLOCKED", "CLOCK_UNVERIFIED"
            rows.append({**common, "direction": direction, "status": status, "reason": reason,
                         "source_validated": True, "detector_trigger": trigger,
                         "direction_policy_sha256": REAL_DIRECTION_POLICIES[direction],
                         "event_id": digest(canonical({**identity, "direction": direction})),
                         "strategy": STRATEGIES[direction]})
        return rows
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, LiveFailure) as exc:
        code = str(exc) if re.fullmatch(r"[A-Z_]{3,64}", str(exc)) else "SOURCE_JOIN_OR_FRESHNESS_INVALID"
        return [{**common, "direction": direction, "status": "DATA_INVALID",
                 "reason": code, "source_validated": False,
                 "event_id": digest(canonical({**identity, "direction": direction}))}
                for direction in STRATEGIES]


def directional_return(entry, exit_price, direction):
    """Analytical sign convention only. No execution or short-selling authority."""
    if direction not in STRATEGIES or decimal(entry) <= 0 or decimal(exit_price) <= 0:
        raise ValueError("INVALID_DIRECTION_OR_PRICE")
    return (decimal(exit_price) / decimal(entry) - 1) * (1 if direction == "UP" else -1)
