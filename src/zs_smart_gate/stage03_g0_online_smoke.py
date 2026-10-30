"""Opt-in, single-symbol public Binance GET -> scientific G0. Never scientific PIT."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import sys
import time
from typing import Callable

from .binance_live import (BASE, LiveBlocked, LiveFailure, get_json,
                           is_spot_enabled, require_dict, timestamp, to_candles)
from .core import MarketSnapshot, decimal
from .mtf_contracts import CandleWindow
from .scanner import (MAX_HTTP_REQUESTS, SOFT_PRE_REQUEST_GUARD_SECONDS,
                      STOP_USED_WEIGHT_1M)
from .stage03a_contracts import Direction, Horizon
from .stage03b1_live import CONFIG, EXACT, SOURCE_ID, parse_kline
from .stage03_offline_scientific_preflight import scientific_g0_preflight

VERSION = "STAGE03_PUBLIC_ONLINE_G0_SMOKE_V1"
SYMBOL = "BTCUSDT"
DAY_MS = 86400000
DURATIONS = {"5m": 300000, "30m": 1800000, "1h": 3600000,
             "4h": 14400000, "1d": DAY_MS, "1w": 7 * DAY_MS}
CONTEXT = {Horizon.INTRADAY: ("1h", "4h"), Horizon.SWING: ("1d", "1w")}


def closed_boundary(server_ms: int, frame: str) -> int:
    size = DURATIONS[frame]
    monday_offset = 4 * DAY_MS if frame == "1w" else 0
    return ((server_ms - monday_offset) // size) * size + monday_offset


def parse_context(row: object, frame: str, receipt: datetime) -> CandleWindow:
    if frame in ("1h", "4h"):
        return parse_kline(row, frame, receipt)
    if frame not in ("1d", "1w") or not isinstance(row, list) or len(row) < 11:
        raise LiveFailure("CONTEXT_SCHEMA_INVALID")
    try:
        start, inclusive_end = int(row[0]), int(row[6])
        size = DURATIONS[frame]
        if start != closed_boundary(start, frame) or inclusive_end != start + size - 1:
            raise LiveFailure("CONTEXT_CLOSE_OR_UTC_ALIGNMENT_INVALID")
        return CandleWindow(
            frame, timestamp(start), timestamp(start + size), receipt, receipt,
            SOURCE_ID, *[decimal(row[i]) for i in (1, 2, 3, 4, 5, 7)])
    except (ValueError, TypeError, IndexError, OverflowError) as exc:
        raise LiveFailure("CONTEXT_NUMERIC_FIELDS_INVALID") from exc


def probe_once(*, horizon: Horizon, symbol: str = SYMBOL,
               getter: Callable = get_json,
               local_ms: Callable[[], float] = lambda: time.time() * 1000,
               monotonic: Callable[[], float] = time.perf_counter) -> dict:
    """7 INTRADAY or 8 SWING nominal GETs; zero retries, <=8 actual attempts."""
    if not isinstance(horizon, Horizon) or symbol != SYMBOL:
        raise ValueError("ONLY_BTCUSDT_TYPED_HORIZON_ALLOWED")
    start = monotonic()
    attempts: list[dict] = []
    replies: list[dict] = []
    used_weight = None
    offset = None
    server_ms = None

    def report(status: str, reason: str | None = None) -> dict:
        elapsed = round((monotonic() - start) * 1000, 2)
        return {
            "version": VERSION, "status": status, "reason": reason,
            "symbol": symbol, "horizon": horizon.value, "host": BASE,
            "head_sha": os.environ.get("GITHUB_SHA"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "attempt_count": len(attempts), "attempt_budget": MAX_HTTP_REQUESTS,
            "attempts": attempts, "responses": replies,
            "elapsed_ms": elapsed,
            "soft_guard_seconds": SOFT_PRE_REQUEST_GUARD_SECONDS,
            "source_publication_time": None, "independent_utc_uncertainty_ms": None,
            "server_time_at_anchor": timestamp(server_ms).isoformat() if server_ms is not None else None,
            "estimated_server_offset_ms": round(offset, 2) if offset is not None else None,
            "scientific_g0": "NO_GO_PIT_UNVERIFIED",
            "qualification_status": "NOT_EVALUATED",
            "score_status": "SCORE_UNAVAILABLE", "score": None,
            "signal_id": None, "publishable": False, "delivery_authorized": False,
        }

    def read(path: str, params: dict | None = None):
        nonlocal used_weight
        descriptor = {"path": path, **{k: str(params[k]) for k in
                      ("symbol", "interval", "startTime", "endTime", "limit")
                      if params is not None and k in params}}
        once = False

        def on_attempt(attempt_path: str):
            nonlocal once
            if once:
                raise LiveBlocked("HTTP_RETRY_DISABLED")
            if path != attempt_path:
                raise LiveBlocked("GET_PATH_CHANGED")
            if len(attempts) >= MAX_HTTP_REQUESTS:
                raise LiveBlocked("MAX_EIGHT_ATTEMPTS")
            if monotonic() - start >= SOFT_PRE_REQUEST_GUARD_SECONDS:
                raise LiveBlocked("SOFT_DEADLINE_EXCEEDED")
            if used_weight is not None and used_weight >= STOP_USED_WEIGHT_1M:
                raise LiveBlocked("RATE_WEIGHT_STOP")
            once = True
            attempts.append(descriptor)
        data, meta = getter(path, params, on_attempt=on_attempt)
        if not once or not isinstance(meta, dict) or meta.get("http_status") != 200:
            raise LiveFailure("INVALID_GET_RECEIPT")
        if not isinstance(meta.get("received_local_ms"), (int, float)):
            raise LiveFailure("RECEIPT_TIMESTAMP_MISSING")
        weight = meta.get("used_weight_1m")
        if weight is None or not str(weight).isdigit():
            raise LiveBlocked("USED_WEIGHT_HEADER_UNKNOWN")
        used_weight = int(weight)
        replies.append({
            "path": path, "frame": params.get("interval") if params else None,
            "status": 200, "used_weight_1m": used_weight,
            "latency_ms": meta.get("latency_ms"),
            "received_local_ms": meta["received_local_ms"],
        })
        return data, meta

    try:
        time_doc, time_meta = read("/api/v3/time")
        server_ms = int(require_dict(time_doc, ("serverTime",), "TIME_SCHEMA")["serverTime"])
        if "t0_local_ms" not in time_meta or time_meta["received_local_ms"] < time_meta["t0_local_ms"]:
            raise LiveFailure("TIME_RECEIPT_INVALID")
        offset = server_ms - (time_meta["t0_local_ms"] + time_meta["received_local_ms"]) / 2

        exchange, em = read("/api/v3/exchangeInfo", {"symbol": symbol})
        ticker, tm = read("/api/v3/ticker/24hr", {"symbol": symbol})
        members = require_dict(exchange, ("symbols",), "EXCHANGE_INFO_SCHEMA")["symbols"]
        if not isinstance(members, list) or len(members) != 1:
            raise LiveFailure("EXCHANGE_SYMBOL_NOT_UNIQUE")
        info = require_dict(members[0], ("symbol", "quoteAsset", "status"), "SPOT_SCHEMA")
        ticker = require_dict(ticker,
                              ("symbol", "quoteVolume", "bidPrice", "askPrice"),
                              "24HR_FULL_TICKER_SCHEMA")
        if info["symbol"] != symbol or ticker["symbol"] != symbol:
            raise LiveFailure("PUBLIC_API_SYMBOL_MISMATCH")
        observed = timestamp(max(em["received_local_ms"], tm["received_local_ms"]) + offset)
        market = MarketSnapshot(symbol, info["quoteAsset"], is_spot_enabled(info),
                                info["status"], decimal(ticker["quoteVolume"]),
                                decimal(ticker["bidPrice"]), decimal(ticker["askPrice"]),
                                observed)

        p_frame, c_frame, child_count, parent_ms = CONFIG[horizon]
        close_ms = closed_boundary(server_ms, p_frame)
        open_ms = close_ms - parent_ms
        parent_data, pm = read("/api/v3/klines", {
            "symbol": symbol, "interval": p_frame,
            "startTime": str(open_ms), "endTime": str(close_ms - 1), "limit": "1"})
        if not isinstance(parent_data, list) or len(parent_data) != 1:
            raise LiveFailure("CLOSED_PARENT_UNAVAILABLE")
        parent = parse_kline(parent_data[0], p_frame,
                             timestamp(pm["received_local_ms"] + offset))
        if int(parent.open_at.timestamp() * 1000) != open_ms:
            raise LiveFailure("PARENT_ANCHOR_INVALID")

        child_start = close_ms - (21 * DURATIONS["5m"]) if horizon is Horizon.INTRADAY else open_ms
        expected = 21 if horizon is Horizon.INTRADAY else child_count
        child_data, cm = read("/api/v3/klines", {
            "symbol": symbol, "interval": c_frame,
            "startTime": str(child_start), "endTime": str(close_ms - 1),
            "limit": str(expected)})
        if not isinstance(child_data, list) or len(child_data) != expected:
            raise LiveFailure("CHILD_OR_BASE_HISTORY_UNAVAILABLE")
        child_receipt = timestamp(cm["received_local_ms"] + offset)
        children = tuple(parse_kline(v, c_frame, child_receipt)
                         for v in child_data[-child_count:])

        if horizon is Horizon.SWING:
            core_data, core_meta = read("/api/v3/klines", {
                "symbol": symbol, "interval": "5m",
                "startTime": str(close_ms - 21 * DURATIONS["5m"]),
                "endTime": str(close_ms - 1), "limit": "21"})
            core_receipt = timestamp(core_meta["received_local_ms"] + offset)
        else:
            core_data, core_receipt = child_data, child_receipt
        core = to_candles(core_data, core_receipt)
        if len(core) != 21 or core[-1].close_at != parent.close_at:
            raise LiveFailure("CORE_BASE_NOT_CLOSED_AND_ALIGNED")

        context = {}
        for frame in CONTEXT[horizon]:
            boundary = closed_boundary(server_ms, frame)
            bars, m = read("/api/v3/klines", {
                "symbol": symbol, "interval": frame,
                "startTime": str(boundary - DURATIONS[frame]),
                "endTime": str(boundary - 1), "limit": "1"})
            if not isinstance(bars, list) or len(bars) != 1:
                raise LiveFailure("CLOSED_CONTEXT_UNAVAILABLE:" + frame)
            bar = parse_context(bars[0], frame,
                                timestamp(m["received_local_ms"] + offset))
            if int(bar.close_at.timestamp() * 1000) != boundary:
                raise LiveFailure("CONTEXT_ANCHOR_INVALID:" + frame)
            context[frame] = (bar,)

        decision_ms = max(
            local_ms() + offset, market.observed_at.timestamp() * 1000,
            parent.available_at.timestamp() * 1000,
            core_receipt.timestamp() * 1000,
            *(c.available_at.timestamp() * 1000 for c in children),
            *(v[0].available_at.timestamp() * 1000 for v in context.values()))
        decision_at = timestamp(decision_ms)
        directions = {}
        for direction in (Direction.UP, Direction.DOWN):
            row = scientific_g0_preflight(
                symbol=symbol, horizon=horizon, direction=direction,
                parent=parent, children=children, core_5m=core,
                market=market, decision_at=decision_at, tolerance=EXACT,
                event_discriminator="PUBLIC_GET_SMOKE_OBSERVATION_ONLY",
                context_windows=context, pivots=())
            if (row["scientific_g0"] != "NO_GO_PIT_UNVERIFIED"
                or row["qualification_status"] != "NOT_EVALUATED"
                or row["score_status"] != "SCORE_UNAVAILABLE"
                or row["score"] is not None or row["signal_id"] is not None
                or row["publishable"] or row["delivery_authorized"]
                or row["source_publication_time"] is not None
                or row["clock_uncertainty_ms"] is not None):
                raise LiveFailure("G0_RESEARCH_ONLY_GUARD_FAILED")
            directions[direction.value] = {
                "status": row["code_input_status"],
                "candidate": row["candidate_status"],
                "reason_codes": row["reason_codes"],
                "context": row["context"],
                "scientific_g0": row["scientific_g0"],
                "score_status": row["score_status"],
            }
        result = report("ONLINE_INTEGRATION_OBSERVED")
        result.update({
            "decision_at": decision_at.isoformat(),
            "parent": {
                "frame": p_frame, "source_id": parent.source_id,
                "open_at": parent.open_at.isoformat(),
                "close_at": parent.close_at.isoformat(),
                "received_at": parent.received_at.isoformat(),
                "available_at": parent.available_at.isoformat()},
            "child_frame": c_frame, "child_count": len(children),
            "core_5m_count": len(core),
            "contexts": list(context), "directions": directions,
            "market_observed_at": observed.isoformat(),
            "market_symbol": market.symbol,
            "kline_symbol_validation": "REQUEST_SYMBOL_CHECKED_KLINE_ROWS_HAVE_NO_SYMBOL",
            "receipt_provenance": "LOCAL_RECEIPT_PLUS_ESTIMATED_OFFSET_NOT_PUBLICATION",
        })
        if any(v["status"] != "SOFTWARE_CONTRACTS_VALID_ON_SYNTHETIC_INPUT"
               for v in directions.values()):
            result["status"] = "ONLINE_INPUT_UNAVAILABLE"
        if result["elapsed_ms"] > SOFT_PRE_REQUEST_GUARD_SECONDS * 1000:
            result["status"] = "ONLINE_BLOCKED"
            result["reason"] = "SOFT_DEADLINE_OVERRUN"
        return result
    except LiveBlocked as exc:
        return report("ONLINE_BLOCKED", str(exc))
    except LiveFailure as exc:
        # Access-denial is a provider/geography gate, not code or candle failure.
        detail = str(exc)
        if detail.startswith(("HTTP_403", "HTTP_451", "HTTP_418", "HTTP_429")):
            return report("ONLINE_BLOCKED", detail)
        return report("ONLINE_INPUT_UNAVAILABLE", detail)
    except (ValueError, TypeError, IndexError, KeyError) as exc:
        return report("ONLINE_INPUT_UNAVAILABLE", str(exc))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manual public one-symbol G0 smoke")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--horizon", default="INTRADAY",
                        choices=[v.value for v in Horizon])
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("EXPLICIT_LIVE_OPT_IN_REQUIRED")
    result = probe_once(horizon=Horizon(args.horizon))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "ONLINE_INTEGRATION_OBSERVED" else 2


if __name__ == "__main__":
    sys.exit(main())
