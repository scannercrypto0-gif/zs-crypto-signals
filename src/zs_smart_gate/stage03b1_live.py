"""03B1 single-symbol/single-horizon public Spot MTF evidence probe; opt-in only.

An independent parent and exactly anchored children use Stage-03A reconcile and
the existing Stage-01 candidate for eligible, available 21x5m history. It does
NOT qualify/signals/trade, nor assert historical exchange publication times.
No exchange write endpoints, persistent results, daemon or Telegram.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import re
import sys
import time
from typing import Callable

from .binance_live import (BASE, LiveBlocked, LiveFailure, get_json, is_spot_enabled,
                           require_dict, timestamp, to_candles)
from .core import MarketSnapshot, build_candidate, check_eligibility, decimal
from .mtf_contracts import CandleWindow, ReconciliationTolerance, reconcile
from .research_metrics import VERSION as METRIC_VERSION, describe
from .scanner import MAX_HTTP_REQUESTS, SOFT_PRE_REQUEST_GUARD_SECONDS, STOP_USED_WEIGHT_1M
from .stage03a_contracts import Direction, EventIdentity, Horizon, bind_research_candidate

CONFIG = {Horizon.INTRADAY: ("30m", "5m", 6, 30 * 60_000),
          Horizon.SWING: ("4h", "1h", 4, 4 * 60 * 60_000)}
DURATION_MS = {"5m": 300_000, "30m": 1_800_000,
               "1h": 3_600_000, "4h": 14_400_000}
SOURCE_ID = "BINANCE:SPOT:PUBLIC_KLINES"
EXACT = ReconciliationTolerance("0", "0", "0",
                                "03B1_SAME_SOURCE_EXACT_RESEARCH_NOT_PRODUCTION_TOLERANCE")


def parse_kline(row: object, frame: str, received_at: datetime) -> CandleWindow:
    """Reject wrong exchange inclusive end time; no fabricated source publication."""
    if not isinstance(row, list) or len(row) < 11:
        raise LiveFailure("KLINE_SCHEMA_INVALID")
    try:
        start = int(row[0])
        inclusive_end = int(row[6])
        duration = DURATION_MS[frame]
        if start % duration or inclusive_end != start + duration - 1:
            raise LiveFailure("EXCHANGE_KLINE_TIME_SEMANTICS_INVALID")
        return CandleWindow(frame, timestamp(start), timestamp(start + duration),
                            received_at, received_at, SOURCE_ID,
                            *[decimal(row[i]) for i in (1, 2, 3, 4, 5, 7)])
    except (KeyError, IndexError, ValueError, TypeError, OverflowError) as exc:
        raise LiveFailure("KLINE_VALUES_INVALID") from exc


def deviations(parent: CandleWindow, children: list[CandleWindow]) -> dict:
    """Signed parent-minus-aggregated values; never a tolerance or PASS override."""
    if not children:
        return {}
    aggregate = {
        "open": children[0].open,
        "close": children[-1].close,
        "high": max(c.high for c in children),
        "low": min(c.low for c in children),
        "base_volume": sum((c.base_volume for c in children), Decimal(0)),
        "quote_volume": sum((c.quote_volume for c in children), Decimal(0)),
    }
    return {key: str(getattr(parent, key) - value) for key, value in aggregate.items()}


def probe_once(*, horizon: Horizon, symbol: str = "BTCUSDT",
               getter: Callable = get_json,
               local_ms: Callable[[], float] = lambda: time.time() * 1000,
               monotonic: Callable[[], float] = time.perf_counter) -> dict:
    """One explicit research run; MAX 8 physical HTTP GETs INCLUDING retries.

    A soft pre-attempt 60s guard cannot cancel an in-flight HTTP request.
    All metadata timestamps from response receipts are offset-adjusted estimates.
    """
    if not isinstance(horizon, Horizon):
        raise ValueError("HORIZON_ENUM_REQUIRED")
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9]{1,16}USDT", symbol):
        raise ValueError("EXPLICIT_SPOT_USDT_SYMBOL_REQUIRED")
    parent_frame, child_frame, expected, duration_ms = CONFIG[horizon]
    start_monotonic = monotonic()
    attempts: list[str] = []
    calls: list[dict] = []
    clock_offset: float | None = None
    clock_rtt: float | None = None

    def telemetry() -> dict:
        elapsed = round((monotonic() - start_monotonic) * 1000, 2)
        return {
            "physical_http_attempts": len(attempts),
            "logical_calls_succeeded": len(calls),
            "attempted_paths": list(attempts),
            "http_attempt_budget": MAX_HTTP_REQUESTS,
            "soft_guard_seconds": SOFT_PRE_REQUEST_GUARD_SECONDS,
            "soft_guard_kind": "PRE_ATTEMPT_ONLY_NOT_HARD_DEADLINE",
            "elapsed_ms": elapsed, "deadline_exceeded": elapsed > 60_000,
            "estimated_server_clock_offset_ms": round(clock_offset, 2) if clock_offset is not None else None,
            "clock_rtt_ms": round(clock_rtt, 2) if clock_rtt is not None else None,
            "clock_uncertainty_lower_bound_ms": round(clock_rtt / 2, 2) if clock_rtt is not None else None,
            "true_clock_uncertainty_ms": None,
            "source_kline_publication_timestamps": None,
            "http": [{k: c.get(k) for k in ("path", "http_status", "latency_ms", "used_weight_1m")}
                     for c in calls],
        }

    def attempt(path: str) -> None:
        if len(attempts) >= MAX_HTTP_REQUESTS:
            raise LiveBlocked("PHYSICAL_HTTP_ATTEMPT_BUDGET_EXHAUSTED")
        if monotonic() - start_monotonic > SOFT_PRE_REQUEST_GUARD_SECONDS:
            raise LiveBlocked("SOFT_PRE_REQUEST_GUARD_EXCEEDED")
        if calls and calls[-1].get("used_weight_1m") is not None:
            if int(calls[-1]["used_weight_1m"]) >= STOP_USED_WEIGHT_1M:
                raise LiveBlocked("EXCHANGE_WEIGHT_SAFETY_STOP")
        attempts.append(path)

    def read(path: str, params: dict | None = None) -> tuple[object, dict]:
        result, meta = getter(path, params, on_attempt=attempt)
        if not isinstance(meta, dict) or not isinstance(meta.get("received_local_ms"), (int, float)):
            raise LiveFailure("MISSING_HTTP_RECEIPT_METADATA")
        calls.append(meta)
        return result, meta

    try:
        server, clock = read("/api/v3/time")
        server = require_dict(server, ("serverTime",), "TIME_SCHEMA")
        server_ms = int(server["serverTime"])
        clock_rtt = clock["received_local_ms"] - clock["t0_local_ms"]
        if clock_rtt < 0:
            raise LiveFailure("LOCAL_CLOCK_MOVED_BACKWARDS")
        clock_offset = server_ms - (clock["t0_local_ms"] + clock["received_local_ms"]) / 2
        # Freeze the newest *finished* parent at the sampled exchange server time.
        # Never infer closed state from a later GET's new, developing bar.
        close_ms = (server_ms // duration_ms) * duration_ms
        open_ms = close_ms - duration_ms
        if open_ms <= 0:
            raise LiveFailure("INVALID_PARENT_ANCHOR")

        exchange, xm = read("/api/v3/exchangeInfo", {"symbol": symbol})
        ticker, tm = read("/api/v3/ticker/24hr", {"symbol": symbol})
        book, bm = read("/api/v3/ticker/bookTicker", {"symbol": symbol})
        exchange = require_dict(exchange, ("symbols",), "EXCHANGE_INFO_SCHEMA")
        entries = exchange["symbols"]
        if not isinstance(entries, list) or len(entries) != 1:
            raise LiveFailure("EXCHANGE_SYMBOL_NOT_UNIQUE")
        info = require_dict(entries[0], ("symbol", "quoteAsset", "status"),
                            "SYMBOL_SCHEMA")
        ticker = require_dict(ticker, ("symbol", "quoteVolume"), "TICKER_SCHEMA")
        book = require_dict(book, ("symbol", "bidPrice", "askPrice"), "BOOK_SCHEMA")
        if any(entry["symbol"] != symbol for entry in (info, ticker, book)):
            raise LiveFailure("SPOT_SYMBOL_MISMATCH")
        market_received = timestamp(max(
            meta["received_local_ms"] for meta in (xm, tm, bm)) + clock_offset)
        market = MarketSnapshot(
            symbol, info["quoteAsset"], is_spot_enabled(info), info["status"],
            decimal(ticker["quoteVolume"]), decimal(book["bidPrice"]),
            decimal(book["askPrice"]), market_received)
        eligibility = check_eligibility(market, market.observed_at)
        if eligibility:
            raise LiveFailure("SPOT_NOT_ELIGIBLE_" + ",".join(eligibility))

        base_params = {"symbol": symbol, "interval": parent_frame,
                       "startTime": str(open_ms), "endTime": str(close_ms - 1), "limit": "1"}
        p_rows, pm = read("/api/v3/klines", base_params)
        if not isinstance(p_rows, list) or len(p_rows) != 1:
            raise LiveFailure("EXACTLY_ONE_CLOSED_PARENT_REQUIRED")
        parent = parse_kline(p_rows[0], parent_frame,
                             timestamp(pm["received_local_ms"] + clock_offset))
        if int(parent.open_at.timestamp() * 1000) != open_ms:
            raise LiveFailure("PARENT_ANCHOR_MISMATCH")

        # Intraday last six children are the final six bars in 21x5m core history,
        # all anchored to the same closed parent. Swing uses 4x1h and a separate
        # 21x5m core research window at the 4h boundary.
        child_start = (close_ms - 21 * 300_000) if horizon is Horizon.INTRADAY else open_ms
        child_limit = 21 if horizon is Horizon.INTRADAY else expected
        child_rows, cm = read("/api/v3/klines", {
            "symbol": symbol, "interval": child_frame,
            "startTime": str(child_start), "endTime": str(close_ms - 1),
            "limit": str(child_limit)})
        if not isinstance(child_rows, list) or len(child_rows) != child_limit:
            raise LiveFailure("EXACT_CHILD_OR_HISTORY_COVERAGE_MISSING")
        child_received = timestamp(cm["received_local_ms"] + clock_offset)
        children = [parse_kline(row, child_frame, child_received)
                    for row in child_rows[-expected:]]
        if horizon is Horizon.SWING:
            core_rows, core_meta = read("/api/v3/klines", {
                "symbol": symbol, "interval": "5m",
                "startTime": str(close_ms - 21 * 300_000),
                "endTime": str(close_ms - 1), "limit": "21"})
            core_received = timestamp(core_meta["received_local_ms"] + clock_offset)
        else:
            core_rows, core_received = child_rows, child_received

        # Capture actual data-arrival decision, not a retroactive decision at the
        # parent bar close. Never claim unavailable data was known earlier.
        decision = max(timestamp(local_ms() + clock_offset), market.observed_at,
                       parent.available_at, *(c.available_at for c in children),
                       core_received)
        evidence = reconcile(parent, children, decision, tolerance=EXACT)
        core_candles = to_candles(core_rows, core_received)
        candidate = build_candidate(market, core_candles, decision)
        if candidate.status != "ELIGIBLE":
            raise LiveFailure("CORE_CANDIDATE_" + candidate.status + "_" +
                              ",".join(candidate.eligibility_reasons + candidate.candle_errors))
        if core_candles[-1].close_at != parent.close_at:
            raise LiveFailure("CORE_FIVE_MINUTE_WINDOW_NOT_PARENT_ALIGNED")

        diagnostics = deviations(parent, children)
        rows = {
            "stage": "03B1_LIVE_MTF_RESEARCH_ONLY",
            "status": "PASS" if evidence.status == "PASS" else "INVALID",
            "horizon": horizon.value, "symbol": symbol, "host": BASE,
            "parent_frame": parent_frame, "child_frame": child_frame,
            "expected_children": expected, "received_children": len(children),
            "parent_open_exclusive_window_at": parent.open_at.isoformat(),
            "parent_close_exclusive_at": parent.close_at.isoformat(),
            "decision_at": decision.isoformat(),
            "exchange_server_time_at_anchor": timestamp(server_ms).isoformat(),
            "source_id": SOURCE_ID,
            "source_publication_time_known": False,
            "receipt_and_availability": "ESTIMATED_SERVER_UTC_FROM_CLIENT_RECEIPT_PLUS_OFFSET",
            "reconciliation": evidence.as_dict(),
            "signed_parent_minus_children_deltas": diagnostics,
            "zero_tolerance_is_research_comparison_not_adopted_policy": True,
            "coverage": {"spot_assets_selected": 1, "horizons_evaluated": 1,
                         "parent_candles_fetched": 1,
                         "child_candles_fetched": len(children),
                         "core_5m_candles": len(core_candles),
                         "market_wide_scanned": False},
            "candidate": candidate.as_dict(),
            "research_events": [], "signal_id": None, "score": None,
            "score_status": "SCORE_UNAVAILABLE", "trade_plan_status": "RESEARCH_ONLY",
            "research_metric_version": METRIC_VERSION,
            "research_metrics": {},
            "limits": ["one Spot/USDT symbol and horizon; no coverage beyond this fixture",
                       "market metadata sampled at runtime, not reconstructed at candle close",
                       "server clock offset is an estimate with unknown additional uncertainty",
                       "exact 0 tolerance is observational; nonzero deviation not suppressed",
                       "no source kline publication timestamps; receipt is best known availability",
                       "not predictive, not calibrated, not Signal/Score/TradeReady/Telegram"],
        }
        if evidence.status == "PASS":
            for direction in (Direction.UP, Direction.DOWN):
                identity = EventIdentity.research_key(
                    symbol=symbol, horizon=horizon, direction=direction,
                    setup_type="03B1_DESCRIPTIVE_RESEARCH", decision_candle_close_at=parent.close_at,
                    rule_version=METRIC_VERSION, event_discriminator="OBSERVATION_ONLY")
                event = bind_research_candidate(
                    candidate=candidate, identity=identity, reconciliation=evidence,
                    candidate_id="03B1-EPHEMERAL-" + horizon.value + "-" + symbol)
                rows["research_events"].append({
                    "direction": direction.value, "status": event.status.value,
                    "detection_event_key": identity.detection_event_key,
                    "signal_id": event.identity.signal_id,
                    "publishable": event.as_dict()["publishable"]})
                rows["research_metrics"][direction.value] = [
                    x.as_dict() for x in describe(parent, children,
                                                  direction=direction, decision_at=decision)]
        else:
            rows["reasons"] = list(evidence.reason_codes)
        rows["measurements"] = telemetry()
        if rows["measurements"]["deadline_exceeded"]:
            rows["status"] = "FAIL"
            rows.setdefault("reasons", []).append("SOFT_GUARD_OVERRUN_IN_FLIGHT")
        return rows
    except (LiveFailure, LiveBlocked, ValueError, TypeError) as exc:
        kind = "BLOCKED" if isinstance(exc, LiveBlocked) else "FAIL"
        return {"stage": "03B1_LIVE_MTF_RESEARCH_ONLY", "status": kind,
                "symbol": symbol, "horizon": horizon.value,
                "reason": str(exc), "measurements": telemetry(),
                "research_events": [], "signal_id": None,
                "score_status": "SCORE_UNAVAILABLE",
                "trade_plan_status": "RESEARCH_ONLY"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="03B1 manual public Binance MTF evidence only")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--horizon", required=True, choices=[x.value for x in Horizon])
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("EXPLICIT_LIVE_OPT_IN_REQUIRED")
    output = probe_once(horizon=Horizon(args.horizon), symbol=args.symbol)
    print(json.dumps(output, sort_keys=True))
    return 0 if output["status"] == "PASS" else 2 if output["status"] == "BLOCKED" else 1


if __name__ == "__main__":
    sys.exit(main())
