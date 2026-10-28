"""Opt-in, read-only Binance Spot LIVE research smoke, using public market-data endpoints.

Run ONLY with --live; no scheduler, storage, credentials, Telegram, orders or secrets.
Only one/two explicit USDT spot symbols; stdlib HTTP GET only.
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .core import Candle, MarketSnapshot, build_candidate, decimal

BASE = "https://data-api.binance.vision"
ALLOW_PATHS = frozenset({
    "/api/v3/time", "/api/v3/exchangeInfo", "/api/v3/klines",
    "/api/v3/ticker/24hr", "/api/v3/ticker/bookTicker",
})
FIVE_MS = 300000
MAX_ATTEMPTS = 2
MAX_RETRY_AFTER_S = 3.0
HTTP_TIMEOUT_S = 6.0


class LiveBlocked(RuntimeError):
    """Connectivity, geographic denial, or provider rate block."""


class LiveFailure(RuntimeError):
    """Invalid response or failed mandatory research quality contract."""


def timestamp(ms: float | int) -> datetime:
    return datetime.fromtimestamp(float(ms) / 1000, tz=timezone.utc)


def get_json(path: str, params: dict[str, str] | None = None) -> tuple[object, dict]:
    if path not in ALLOW_PATHS:
        raise ValueError("UNAUTHORIZED_ENDPOINT")
    url = BASE + path + (("?" + urlencode(params)) if params else "")
    for attempt in range(MAX_ATTEMPTS):
        t0 = time.time() * 1000
        started = time.perf_counter()
        try:
            req = Request(url, headers={"Accept": "application/json", "User-Agent": "ZS-SMART-GATE-research-smoke/1"})
            with urlopen(req, timeout=HTTP_TIMEOUT_S) as response:
                status = response.status
                # Full public universe payloads are larger than single-symbol smoke
                # responses; keep a hard finite per-endpoint response-size ceiling.
                max_bytes = (8_000_000 if not params and path in (
                    "/api/v3/exchangeInfo", "/api/v3/ticker/24hr",
                    "/api/v3/ticker/bookTicker") else 2_000_000)
                body = response.read(max_bytes + 1)
                received_ms = time.time() * 1000
                if len(body) > max_bytes:
                    raise LiveFailure("OVERSIZED_HTTP_RESPONSE")
                if status != 200:
                    raise LiveFailure("HTTP_STATUS_" + str(status))
                try:
                    payload = json.loads(body)
                except (ValueError, UnicodeError) as exc:
                    raise LiveFailure("INVALID_JSON") from exc
                headers = response.headers
                usage = headers.get("X-MBX-USED-WEIGHT-1M")
                return payload, {
                    "path": path, "http_status": status, "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "t0_local_ms": round(t0), "received_local_ms": round(received_ms),
                    "used_weight_1m": usage if usage is not None and str(usage).isdigit() else None,
                }
        except HTTPError as exc:
            if exc.code in (418, 429):
                retry_raw = exc.headers.get("Retry-After", "") if exc.headers else ""
                try:
                    delay = float(retry_raw)
                except (ValueError, TypeError):
                    delay = 1.0
                if exc.code == 429 and attempt + 1 < MAX_ATTEMPTS and 0 <= delay <= MAX_RETRY_AFTER_S:
                    time.sleep(delay)
                    continue
                raise LiveBlocked("BINANCE_RATE_LIMIT_" + str(exc.code)) from exc
            if exc.code >= 500 and attempt + 1 < MAX_ATTEMPTS:
                time.sleep(0.25)
                continue
            raise LiveFailure("HTTP_" + str(exc.code)) from exc
        except (URLError, TimeoutError, socket.timeout, OSError) as exc:
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(0.25)
                continue
            raise LiveBlocked("NETWORK_UNAVAILABLE_" + type(exc).__name__) from exc
    raise LiveBlocked("RETRY_BUDGET_EXHAUSTED")


def to_candles(klines: object, received_at: datetime) -> list[Candle]:
    """Binance kline index 6 is inclusive end_ms; contract close_at is exclusive."""
    if not isinstance(klines, list):
        raise LiveFailure("KLINES_SCHEMA")
    receipt_ms = int(received_at.timestamp() * 1000)
    completed = []
    for item in klines:
        if not isinstance(item, list) or len(item) < 11:
            raise LiveFailure("KLINES_SCHEMA")
        try:
            open_ms, inclusive_close_ms = int(item[0]), int(item[6])
            if open_ms % FIVE_MS != 0 or inclusive_close_ms != open_ms + FIVE_MS - 1:
                raise LiveFailure("KLINE_TIMESTAMP_SEMANTICS")
            if open_ms + FIVE_MS > receipt_ms:
                continue  # Current forming 5m candle is never an input.
            completed.append(Candle(
                open_at=timestamp(open_ms),
                close_at=timestamp(open_ms + FIVE_MS),
                received_at=received_at, available_at=received_at,
                open=decimal(item[1]), high=decimal(item[2]),
                low=decimal(item[3]), close=decimal(item[4]),
                base_volume=decimal(item[5]), quote_volume=decimal(item[7])))
        except (ValueError, TypeError, OverflowError, IndexError) as exc:
            raise LiveFailure("INVALID_KLINE_FIELDS") from exc
    if len(completed) < 21:
        raise LiveFailure("INSUFFICIENT_COMPLETED_5M_KLINES")
    return completed[-21:]


def require_dict(value: object, keys: tuple[str, ...], code: str) -> dict:
    if not isinstance(value, dict) or any(key not in value for key in keys):
        raise LiveFailure(code)
    return value


def is_spot_enabled(info: dict) -> bool:
    explicit = info.get("isSpotTradingAllowed")
    if isinstance(explicit, bool):
        return explicit
    perms = info.get("permissions")
    if isinstance(perms, list):
        return "SPOT" in perms
    sets = info.get("permissionSets")
    if isinstance(sets, list) and all(isinstance(group, list) for group in sets):
        return any("SPOT" in group for group in sets)
    raise LiveFailure("SPOT_PERMISSION_MISSING")


def run_live(symbol: str = "BTCUSDT") -> dict:
    if not re.fullmatch(r"[A-Z0-9]{3,16}USDT", symbol):
        raise ValueError("ONLY_EXPLICIT_USDT_SYMBOLS_SUPPORTED")
    begin = time.perf_counter()
    server, clock = get_json("/api/v3/time")
    server = require_dict(server, ("serverTime",), "TIME_SCHEMA")
    try:
        server_ms = int(server["serverTime"])
    except (ValueError, TypeError) as exc:
        raise LiveFailure("TIME_SCHEMA") from exc
    offset_ms = server_ms - (clock["t0_local_ms"] + clock["received_local_ms"]) / 2
    samples = [clock]
    info_doc, info_call = get_json("/api/v3/exchangeInfo", {"symbol": symbol})
    ticker, ticker_call = get_json("/api/v3/ticker/24hr", {"symbol": symbol})
    book, book_call = get_json("/api/v3/ticker/bookTicker", {"symbol": symbol})
    klines, kline_call = get_json("/api/v3/klines", {"symbol": symbol, "interval": "5m", "limit": "22"})
    samples.extend((info_call, ticker_call, book_call, kline_call))

    info_doc = require_dict(info_doc, ("symbols",), "EXCHANGE_INFO_SCHEMA")
    entries = info_doc["symbols"]
    if not isinstance(entries, list) or len(entries) != 1:
        raise LiveFailure("SYMBOL_NOT_UNIQUELY_FOUND")
    info = require_dict(entries[0], ("symbol", "quoteAsset", "status"), "SYMBOL_SCHEMA")
    ticker = require_dict(ticker, ("symbol", "quoteVolume"), "TICKER_24H_SCHEMA")
    book = require_dict(book, ("symbol", "bidPrice", "askPrice"), "BOOK_SCHEMA")
    if any(value["symbol"] != symbol for value in (info, ticker, book)):
        raise LiveFailure("SYMBOL_MISMATCH")

    # No source quote timestamp is claimed: snapshot time is the latest
    # endpoint *receipt*, adjusted by the measured public-server clock offset.
    market_received_ms = max(x["received_local_ms"] for x in (info_call, ticker_call, book_call))
    market = MarketSnapshot(
        symbol=symbol, quote_asset=info["quoteAsset"],
        spot_enabled=is_spot_enabled(info), trading_status=info["status"],
        quote_volume_24h=decimal(ticker["quoteVolume"]),
        bid=decimal(book["bidPrice"]), ask=decimal(book["askPrice"]),
        observed_at=timestamp(market_received_ms + offset_ms))
    candle_received_at = timestamp(kline_call["received_local_ms"] + offset_ms)
    candles = to_candles(klines, candle_received_at)
    decision_at = timestamp(time.time() * 1000 + offset_ms)
    candidate = build_candidate(market, candles, decision_at)
    if candidate.status != "ELIGIBLE":
        raise LiveFailure("RESEARCH_QUALITY_" + candidate.status + "_"
                          + ",".join(candidate.eligibility_reasons + candidate.candle_errors))
    if candidate.rvol_base_20 is None or candidate.rvol_quote_20 is None:
        raise LiveFailure("LIVE_RVOL_NOT_AVAILABLE")
    return {
        "verification": "BINANCE_LIVE_PUBLIC_READ_ONLY", "status": "PASS",
        "symbol": symbol, "host": BASE, "request_count": len(samples),
        "server_time_utc": timestamp(server_ms).isoformat(),
        "clock_offset_ms": round(offset_ms, 2),
        "clock_rtt_ms": round(clock["received_local_ms"] - clock["t0_local_ms"], 2),
        "market_snapshot_observed_at": market.observed_at.isoformat(),
        "last_closed_candle_exclusive_utc": candles[-1].close_at.isoformat(),
        "first_open_candle_utc": candles[0].open_at.isoformat(),
        "closed_candle_count": len(candles),
        "candle_source_semantics": "Binance closeTime inclusive; local close_at exclusive +1ms",
        "decision_at": decision_at.isoformat(),
        "market_24h_quote_volume": str(market.quote_volume_24h),
        "price_bid": str(market.bid), "price_ask": str(market.ask),
        "candidate": candidate.as_dict(),
        "http": [{k: v for k, v in x.items() if k in ("path", "http_status", "latency_ms", "used_weight_1m")} for x in samples],
        "cycle_ms": round((time.perf_counter() - begin) * 1000, 2),
        "limitations": ["single-symbol bounded sample only", "no source publication time for book/ticker",
                        "not market-wide continuous scanning", "not prediction/telegram/storage verification"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manual opt-in Binance public Spot smoke")
    parser.add_argument("--live", action="store_true", help="explicitly allow public network GET")
    parser.add_argument("--symbol", default="BTCUSDT")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("Live requests require explicit --live")
    try:
        out = run_live(args.symbol)
    except LiveBlocked as exc:
        out = {"verification": "BINANCE_LIVE_PUBLIC_READ_ONLY", "symbol": args.symbol,
               "status": "BLOCKED", "reason": str(exc), "utc": datetime.now(timezone.utc).isoformat()}
        print(json.dumps(out, sort_keys=True))
        return 2
    except (LiveFailure, ValueError) as exc:
        out = {"verification": "BINANCE_LIVE_PUBLIC_READ_ONLY", "symbol": args.symbol,
               "status": "FAIL", "reason": str(exc), "utc": datetime.now(timezone.utc).isoformat()}
        print(json.dumps(out, sort_keys=True))
        return 1
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
