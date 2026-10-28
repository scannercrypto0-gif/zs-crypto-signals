"""FOUNDATION-002: bounded, read-only public Binance Spot/USDT scanner.

One explicit, ephemeral cycle; never stores market data or creates Signal Events.
No scheduler, Telegram, private API, trading or production freshness SLA.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import sys
import time
import tracemalloc
from typing import Callable

from .binance_live import (
    BASE, LiveBlocked, LiveFailure, get_json, is_spot_enabled,
    require_dict, timestamp, to_candles,
)
from .core import (
    MarketSnapshot, ResearchCandidate, build_candidate,
    check_eligibility, decimal, utc,
)

MAX_SYMBOLS_PER_CYCLE = 4  # small explicit research sample, NOT a scheduled market cadence
MAX_HTTP_REQUESTS = 8     # time + 3 inventory endpoints + <=4 klines
MAX_CYCLE_SECONDS = 60    # smoke safety cap, NOT an accepted 24/7 latency SLA
STOP_USED_WEIGHT_1M = 1000  # conservative observation threshold, NOT an exchange quota claim
FIVE_MINUTE_MS = 300_000
SYMBOL_RE = re.compile(r"[A-Z0-9]{1,24}USDT\Z")


@dataclass(frozen=True)
class UniverseItem:
    symbol: str
    status: str
    reasons: tuple[str, ...]
    cohort: str
    market: MarketSnapshot | None

    def as_dict(self) -> dict:
        return {"symbol": self.symbol, "status": self.status,
                "reasons": list(self.reasons), "cohort": self.cohort}


@dataclass(frozen=True)
class SymbolScan:
    symbol: str
    status: str
    reasons: tuple[str, ...]
    candidate: ResearchCandidate | None
    last_closed_at: datetime | None
    elapsed_ms: float

    def as_dict(self) -> dict:
        return {"symbol": self.symbol, "status": self.status,
                "reasons": list(self.reasons),
                "last_closed_at": self.last_closed_at.isoformat() if self.last_closed_at else None,
                "elapsed_ms": self.elapsed_ms,
                "candidate": self.candidate.as_dict() if self.candidate else None}


@dataclass(frozen=True)
class ScanReport:
    cycle_id: str
    status: str
    created_at: datetime
    universe: tuple[UniverseItem, ...]  # complete in-memory inventory, not persisted
    selections: tuple[str, ...]
    results: tuple[SymbolScan, ...]
    calls: tuple[dict, ...]
    clock_offset_ms: float
    clock_rtt_ms: float
    elapsed_ms: float
    peak_allocated_kib: float
    request_budget: int

    def as_dict(self, *, include_inventory: bool = False) -> dict:
        counts = Counter(x.status for x in self.universe)
        reasons = Counter(reason for x in self.universe for reason in x.reasons)
        cohorts = Counter(x.cohort for x in self.universe)
        result_counts = Counter(x.status for x in self.results)
        eligible = [x.symbol for x in self.universe if x.status == "ELIGIBLE"]
        payload = {
            "stage": "FOUNDATION-002_BOUNDED_RESEARCH_ONLY", "cycle_id": self.cycle_id,
            "status": self.status, "created_at": self.created_at.isoformat(),
            "universe": {"total_spot_usdt_inventory": len(self.universe),
                         "eligible_count": len(eligible),
                         "statuses": dict(sorted(counts.items())),
                         "reasons": dict(sorted(reasons.items())),
                         "cohorts": dict(sorted(cohorts.items())),
                         "eligible_symbols": eligible,
                         "inventory_complete": all(x.status not in ("MISSING_DATA", "INVALID_DATA") for x in self.universe)},
            "selection": {"selected_symbols": list(self.selections),
                          "selected_count": len(self.selections),
                          "processed_count": len(self.results),
                          "result_statuses": dict(sorted(result_counts.items()))},
            "results": [x.as_dict() for x in self.results],
            "measurements": {
                "clock_offset_ms": self.clock_offset_ms, "clock_rtt_ms": self.clock_rtt_ms,
                "elapsed_ms": self.elapsed_ms, "peak_python_allocated_kib": self.peak_allocated_kib,
                "calls_made": len(self.calls), "request_budget": self.request_budget,
                "http": [{key: value for key, value in call.items()
                          if key in ("path", "http_status", "latency_ms", "used_weight_1m")} for call in self.calls]},
            "limitations": ["one ephemeral bounded sample, not whole-market scan",
                            "source publication times unavailable on public ticker/book endpoints",
                            "no production freshness SLA, scheduler, persistence, Signal Events or Telegram",
                            "peak_python_allocated_kib measures tracemalloc allocations, not OS RSS"],
        }
        if include_inventory:
            payload["inventory"] = [x.as_dict() for x in self.universe]
        return payload


def _index_records(payload: object, *, name: str) -> dict[str, dict]:
    if not isinstance(payload, list):
        raise LiveFailure(name + "_NOT_LIST")
    result = {}
    for row in payload:
        if not isinstance(row, dict) or not isinstance(row.get("symbol"), str):
            raise LiveFailure(name + "_INVALID_ROW")
        symbol = row["symbol"]
        if symbol in result:
            raise LiveFailure(name + "_DUPLICATE_SYMBOL")
        result[symbol] = row
    return result


def build_universe(exchange_payload: object, tickers: object, books: object,
                   observed_at: datetime) -> tuple[UniverseItem, ...]:
    """Full USDT inventory: no ranking or Score filter; missingness is explicit."""
    observed_at = utc(observed_at)
    exchange = require_dict(exchange_payload, ("symbols",), "EXCHANGE_INFO_SCHEMA")
    entries = _index_records(exchange["symbols"], name="EXCHANGE")
    ticker_map = _index_records(tickers, name="TICKER")
    book_map = _index_records(books, name="BOOK")
    inventory: list[UniverseItem] = []
    for symbol, info in sorted(entries.items()):
        if info.get("quoteAsset") != "USDT":
            continue
        if not SYMBOL_RE.fullmatch(symbol):
            inventory.append(UniverseItem(symbol, "INVALID_DATA",
                                          ("INVALID_SYMBOL_FORMAT",), "BASELINE", None))
            continue
        ticker = ticker_map.get(symbol)
        book = book_map.get(symbol)
        missing = tuple(code for present, code in (
            (ticker is not None, "MISSING_24H_TICKER"),
            (book is not None, "MISSING_BOOK_TICKER"),
        ) if not present)
        if missing:
            inventory.append(UniverseItem(symbol, "MISSING_DATA", missing, "BASELINE", None))
            continue
        try:
            if ticker.get("symbol") != symbol or book.get("symbol") != symbol:
                raise ValueError("SYMBOL_MISMATCH")
            spot_enabled = is_spot_enabled(info)
            quote_volume = decimal(ticker["quoteVolume"])
            if quote_volume < 0:
                raise ValueError("NEGATIVE_QUOTE_VOLUME")
            market = MarketSnapshot(
                symbol=symbol, quote_asset="USDT", spot_enabled=spot_enabled,
                trading_status=str(info["status"]),
                quote_volume_24h=quote_volume,
                bid=decimal(book["bidPrice"]), ask=decimal(book["askPrice"]),
                observed_at=observed_at)
        except (ValueError, TypeError, KeyError, LiveFailure) as exc:
            inventory.append(UniverseItem(symbol, "INVALID_DATA",
                                          ("INVALID_MARKET_FIELDS",), "BASELINE", None))
            continue
        reasons = check_eligibility(market, observed_at)
        cohort = ("LOW_LIQUIDITY_RESEARCH_ONLY"
                  if "LOW_24H_QUOTE_VOLUME" in reasons else "BASELINE")
        inventory.append(UniverseItem(
            symbol, "INELIGIBLE" if reasons else "ELIGIBLE", reasons, cohort, market))
    return tuple(inventory)


def select_sample(universe: tuple[UniverseItem, ...], limit: int, offset: int) -> tuple[UniverseItem, ...]:
    """All eligible assets appear in the inventory; rotating offset avoids fixed favorites."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_SYMBOLS_PER_CYCLE:
        raise ValueError("SAMPLE_LIMIT_OUT_OF_BOUNDS")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValueError("INVALID_SAMPLE_OFFSET")
    eligible = [item for item in universe if item.status == "ELIGIBLE"]
    count = min(limit, len(eligible))
    if not count:
        return ()
    first = offset % len(eligible)
    return tuple(eligible[(first + i) % len(eligible)] for i in range(count))


def inspect_candles(item: UniverseItem, klines: object,
                    received_at: datetime, decision_at: datetime, elapsed_ms: float) -> SymbolScan:
    """Exercise the real core path; failures never turn into research signals."""
    try:
        candles = to_candles(klines, received_at)
        candidate = build_candidate(item.market, candles, decision_at)
        if candidate.status != "ELIGIBLE":
            return SymbolScan(item.symbol, "FAIL",
                              candidate.eligibility_reasons + candidate.candle_errors
                              or ("CORE_CANDIDATE_NOT_ELIGIBLE",),
                              candidate, candles[-1].close_at, elapsed_ms)
        latest_closed_boundary_ms = (int(decision_at.timestamp() * 1000) // FIVE_MINUTE_MS) * FIVE_MINUTE_MS
        if candles[-1].close_at < timestamp(latest_closed_boundary_ms):
            return SymbolScan(item.symbol, "FAIL", ("STALE_CLOSED_5M_WINDOW",),
                              None, candles[-1].close_at, elapsed_ms)
        if candidate.rvol_base_20 is None or candidate.rvol_quote_20 is None:
            return SymbolScan(item.symbol, "FAIL", ("MISSING_RVOL_BASE_OR_QUOTE",),
                              candidate, candles[-1].close_at, elapsed_ms)
        return SymbolScan(item.symbol, "PASS", (), candidate, candles[-1].close_at, elapsed_ms)
    except (LiveFailure, ValueError, OverflowError) as exc:
        # Sanitized error category; never embed untrusted upstream response contents.
        code = str(exc) if isinstance(exc, LiveFailure) else "INVALID_KLINE_FIELDS"
        return SymbolScan(item.symbol, "FAIL", (code,), None, None, elapsed_ms)


def scan_once(*, limit: int = 2, offset: int = 0,
              getter: Callable = get_json) -> ScanReport:
    """At most 8 public GETs, sequential/no workers, and no writes/side effects.

    getter is an injectable public market data interface used by offline contract/E2E
    tests. Never re-purpose this as a 24/7 scheduler without a new owner decision.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_SYMBOLS_PER_CYCLE:
        raise ValueError("SAMPLE_LIMIT_OUT_OF_BOUNDS")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValueError("INVALID_SAMPLE_OFFSET")
    start = time.perf_counter()
    started_tracing = not tracemalloc.is_tracing()
    if started_tracing:
        tracemalloc.start()
    calls: list[dict] = []
    try:
        def limited_get(path: str, params: dict | None = None) -> tuple[object, dict]:
            if len(calls) >= MAX_HTTP_REQUESTS:
                raise LiveBlocked("HTTP_REQUEST_BUDGET_EXHAUSTED")
            if time.perf_counter() - start > MAX_CYCLE_SECONDS:
                raise LiveBlocked("SMOKE_CYCLE_TIME_BUDGET_EXCEEDED")
            if calls:
                used = calls[-1].get("used_weight_1m")
                if used is not None and int(used) >= STOP_USED_WEIGHT_1M:
                    raise LiveBlocked("OBSERVED_EXCHANGE_WEIGHT_SAFETY_STOP")
            payload, metadata = getter(path, params)
            if not isinstance(metadata, dict) or not isinstance(metadata.get("received_local_ms"), (int, float)):
                raise LiveFailure("RECEIPT_METADATA_MISSING")
            calls.append(dict(metadata))
            return payload, metadata

        server, clock = limited_get("/api/v3/time")
        server = require_dict(server, ("serverTime",), "TIME_SCHEMA")
        try:
            server_ms = int(server["serverTime"])
        except (ValueError, TypeError) as exc:
            raise LiveFailure("TIME_SCHEMA") from exc
        clock_rtt = clock["received_local_ms"] - clock["t0_local_ms"]
        if clock_rtt < 0:
            raise LiveFailure("LOCAL_CLOCK_MOVED_BACKWARD")
        offset_ms = server_ms - (clock["t0_local_ms"] + clock["received_local_ms"]) / 2
        exchange, exchange_meta = limited_get("/api/v3/exchangeInfo")
        # MINI retains quoteVolume while avoiding unused 24hr fields and excess memory.
        tickers, ticker_meta = limited_get("/api/v3/ticker/24hr", {"type": "MINI"})
        books, book_meta = limited_get("/api/v3/ticker/bookTicker")
        observed = timestamp(max(m["received_local_ms"] for m in
                                 (exchange_meta, ticker_meta, book_meta)) + offset_ms)
        universe = build_universe(exchange, tickers, books, observed)
        selected = select_sample(universe, limit, offset)
        results: list[SymbolScan] = []
        for entry in selected:
            symbol_start = time.perf_counter()
            try:
                klines, meta = limited_get("/api/v3/klines",
                                           {"symbol": entry.symbol, "interval": "5m", "limit": "22"})
                receipt = timestamp(meta["received_local_ms"] + offset_ms)
                decision = timestamp(time.time() * 1000 + offset_ms)
                results.append(inspect_candles(entry, klines, receipt, decision,
                                               round((time.perf_counter() - symbol_start) * 1000, 2)))
            except LiveBlocked as exc:
                results.append(SymbolScan(entry.symbol, "BLOCKED", (str(exc),), None, None,
                                          round((time.perf_counter() - symbol_start) * 1000, 2)))
                break  # Do not continue requests after rate-block, network block or budget stop.
            except LiveFailure as exc:
                results.append(SymbolScan(entry.symbol, "FAIL", (str(exc),), None, None,
                                          round((time.perf_counter() - symbol_start) * 1000, 2)))
        state = ("BLOCKED" if any(r.status == "BLOCKED" for r in results)
                 else "FAIL" if not selected or any(r.status != "PASS" for r in results)
                 else "PASS")
        if len(results) < len(selected):
            state = "BLOCKED"
        peak = tracemalloc.get_traced_memory()[1] / 1024
        return ScanReport(
            cycle_id="RESEARCH-CYCLE-" + str(int(clock["t0_local_ms"])),
            status=state, created_at=timestamp(clock["received_local_ms"] + offset_ms),
            universe=universe, selections=tuple(x.symbol for x in selected),
            results=tuple(results), calls=tuple(calls), clock_offset_ms=round(offset_ms, 2),
            clock_rtt_ms=round(clock_rtt, 2),
            elapsed_ms=round((time.perf_counter() - start) * 1000, 2),
            peak_allocated_kib=round(peak, 2), request_budget=MAX_HTTP_REQUESTS)
    finally:
        if started_tracing:
            tracemalloc.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Opt-in single bounded public Binance Spot scanner cycle")
    parser.add_argument("--live", action="store_true", help="allow public unauthenticated GETs; no secrets")
    parser.add_argument("--limit", type=int, choices=(1, 2, 3, 4), default=2,
                        help="bounded count of eligible symbols (not whole-market scanning)")
    parser.add_argument("--offset", type=int, default=0,
                        help="nonnegative rotating position in alphabetically sorted eligible inventory")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("Network requests require --live; no automatic scanner scheduling")
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = scan_once(limit=args.limit, offset=args.offset)
        output = result.as_dict()
        print(json.dumps(output, sort_keys=True))
        return 0 if result.status == "PASS" else 2 if result.status == "BLOCKED" else 1
    except LiveBlocked as exc:
        print(json.dumps({"stage": "FOUNDATION-002", "status": "BLOCKED",
                          "reason": str(exc), "utc": started}, sort_keys=True))
        return 2
    except (LiveFailure, ValueError) as exc:
        print(json.dumps({"stage": "FOUNDATION-002", "status": "FAIL",
                          "reason": str(exc), "utc": started}, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
