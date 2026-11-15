"""Bounded Spot receipt -> Scanner -> Setup -> research -> application journal -> 05."""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
import json
import time

from .binance_live import BASE, FIVE_MS, timestamp
from .pre05_offline_chain import LocalChainJournal, SCHEMA as JOURNAL_SCHEMA
from .scanner import build_universe, inspect_candles
from .setup021 import evaluate
from .stage03a_contracts import Direction
from .stage03_r2_offline import Unavailable, close_parts, path_parts, volume_continuity
from .stage05_contracts import SCHEMA, canonical, digest, ensure_event, make_document, sql_projection

SYMBOL = "BTCUSDT"
VERSION = "ZS_00_05_BOUNDED_E2E_V1"
PATHS = ("time", "exchangeInfo", "klines", "ticker/24hr", "ticker/bookTicker", "time")


class Stop(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def utc(dt):
    return dt.isoformat().replace("+00:00", "Z")


def ms():
    return time.time_ns() // 1_000_000


def public_get(path, params):
    url = BASE + "/api/v3/" + path + ("?" + urlencode(params) if params else "")
    request = Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache"})
    with build_opener(NoRedirect()).open(request, timeout=5) as response:
        raw = response.read(262145)
        if response.status != 200 or len(raw) > 262144:
            raise Stop("MARKET_HTTP_OR_SIZE")
    return json.loads(raw)


def capture(receipts, *, get=public_get, clock=ms):
    """Exactly one attempt per path, with an explicit ordered receipt per attempt."""
    for index, path in enumerate(PATHS):
        params = {} if path == "time" else {"symbol": SYMBOL}
        if path == "klines":
            anchor = receipts[0]["payload"]["serverTime"] // FIVE_MS * FIVE_MS
            params.update(interval="5m", limit="34", endTime=str(anchor - 1))
        row = {"path": path, "params": params, "started_ms": clock()}
        receipts.append(row)
        started = time.monotonic_ns()
        try:
            row["payload"] = get(path, params)
            row["status"] = "RECEIVED"
        except Exception:
            row["status"] = "FAILED"
            raise Stop("MARKET_REQUEST_FAILED_" + str(index + 1)) from None
        finally:
            row["received_ms"] = clock()
            row["elapsed_ms"] = (time.monotonic_ns() - started) // 1_000_000
        if path == "time" and (not isinstance(row["payload"], dict)
                               or type(row["payload"].get("serverTime")) is not int
                               or row["payload"]["serverTime"] <= 0):
            raise Stop("SERVER_TIME_INVALID")


def analyze(receipts, decision_ms, *, synthetic):
    """Compute available components without passing a synthetic clock to real data."""
    if tuple(row.get("path") for row in receipts) != PATHS:
        raise Stop("INCOMPLETE_SOURCE")
    prev = receipts[0]["started_ms"]
    for row in receipts:
        begin, end = row["started_ms"], row["received_ms"]
        if (row["status"] != "RECEIVED" or not prev <= begin <= end <= decision_ms
                or abs((end - begin) - row["elapsed_ms"]) > 150
                or end - begin > 5000):
            raise Stop("RECEIPT_ORDER_OR_CLOCK_DISCONTINUITY")
        prev = end
    if decision_ms - receipts[0]["started_ms"] > 20000:
        raise Stop("SESSION_STALE")
    first, info, klines, ticker, book, last = receipts
    t0, t1 = first["payload"]["serverTime"], last["payload"]["serverTime"]
    # Same-provider diagnostic: intersection of request brackets, allowing
    # small acquisition jitter. Never used as independent scientific PIT.
    low = max(t0-first["received_ms"], t1-last["received_ms"]) - 2
    high = min(t0-first["started_ms"], t1-last["started_ms"]) + 2
    if t1 < t0 or high < low or max(abs(low), abs(high)) > 1500:
        raise Stop("LOCAL_UTC_PROVIDER_COMPARISON_UNCERTAIN")
    boundary = t0 // FIVE_MS * FIVE_MS
    if boundary != (decision_ms + high) // FIVE_MS * FIVE_MS:
        raise Stop("DECISION_CROSSES_CANDLE_BOUNDARY")
    expected_params = {"symbol": SYMBOL, "interval": "5m", "limit": "34", "endTime": str(boundary-1)}
    if klines["params"] != expected_params:
        raise Stop("KLINE_REQUEST_IDENTITY_INVALID")
    for row in (info, ticker, book):
        if row["params"] != {"symbol": SYMBOL}:
            raise Stop("MARKET_REQUEST_IDENTITY_INVALID")
    raw = klines["payload"]
    if not isinstance(raw, list) or len(raw) != 34:
        raise Stop("INCOMPLETE_KLINE_WINDOW")
    bars = []
    for i, row in enumerate(raw):
        opened = boundary - (34-i)*FIVE_MS
        if (not isinstance(row, list) or len(row) != 12
                or type(row[0]) is not int or row[0] != opened
                or type(row[6]) is not int or row[6] != opened + FIVE_MS - 1
                or any(not isinstance(row[j], str) for j in (1, 2, 3, 4, 5, 7))):
            raise Stop("KLINE_GAP_DUPLICATE_FORMING_OR_INVALID")
        o, h, l, c, v, q = (Decimal(row[j]) for j in (1, 2, 3, 4, 5, 7))
        if (not all(n.is_finite() for n in (o, h, l, c, v, q))
                or not 0 < l <= min(o, c) <= max(o, c) <= h or min(v, q) < 0):
            raise Stop("KLINE_OHLCV_INVALID")
        bars.append(SimpleNamespace(o=o, h=h, l=l, c=c, q=q))
    if (not isinstance(info["payload"].get("symbols"), list)
            or len(info["payload"]["symbols"]) != 1
            or info["payload"]["symbols"][0].get("symbol") != SYMBOL
            or any(r["payload"].get("symbol") != SYMBOL for r in (ticker, book))):
        raise Stop("MARKET_RESPONSE_IDENTITY_INVALID")
    ticker_end = ticker["payload"].get("closeTime")
    if (type(ticker_end) is not int
            or not decision_ms + high - 60000 <= ticker_end <= ticker["received_ms"] + high):
        raise Stop("TICKER_STALE_OR_FUTURE")
    if decision_ms - book["started_ms"] > 5000:
        raise Stop("BOOK_RECEIPT_STALE")
    available_ms = max(row["received_ms"] for row in receipts)
    received_ms = klines["received_ms"]
    if not boundary <= received_ms <= available_ms <= decision_ms:
        raise Stop("CAUSAL_RECEIPT_ORDER")
    decision = timestamp(decision_ms)
    available = timestamp(available_ms)
    items = build_universe(info["payload"], [ticker["payload"]], [book["payload"]], available)
    if len(items) != 1 or items[0].status != "ELIGIBLE" or items[0].market is None:
        raise Stop("SCANNER_UNIVERSE_REJECTED")
    scan = inspect_candles(items[0], raw[-21:], timestamp(received_ms), decision, 0)
    if scan.status != "PASS":
        raise Stop("SCANNER_REJECTED")
    setup = evaluate(symbol=SYMBOL, klines=raw[-22:], market=items[0].market,
                     received_at=timestamp(received_ms), decision_at=decision, partition="DEV")
    if (setup["score"] is not None or setup["qualified"] or setup["publishable"]
            or setup["reason_codes"] not in (["CLOSED_CAUSAL_TRIGGER"], ["NO_BREAKOUT"],
                                             ["NO_FALSE_TO_TRUE_TRANSITION"])):
        raise Stop("SETUP_REJECTED_INPUT")
    aligned = len(bars) - (boundary // FIVE_MS) % 6
    children = bars[aligned-6:aligned]
    parent = SimpleNamespace(o=children[0].o, h=max(b.h for b in children),
                             l=min(b.l for b in children), c=children[-1].c)
    calculated = {}
    try:
        k, b, w = close_parts(parent, Direction.UP)
        calculated[1] = (8*k+6*b+6*w)/20
    except Unavailable:
        pass
    g, e, t = path_parts(children, Direction.UP)
    calculated[2] = (8*g+8*e+4*t)/20
    try:
        calculated[4] = volume_continuity(children, bars[aligned-26:aligned-6])
    except Unavailable:
        pass
    reasons = {1: "ZERO_CANDLE_RANGE", 3: "FULL_IMPULSE_NOT_APPROVED",
               4: "VOLUME_BASELINE_ZERO", 5: "HIGHER_TIMEFRAME_NOT_CAPTURED",
               6: "INDEPENDENT_WITNESS_AND_BOOK_EVENT_TIME_UNAVAILABLE"}
    scope = "SYNTHETIC_TEST_ONLY" if synthetic else "APPROVED_REAL_SOURCE"
    source_sha = digest(canonical(receipts))
    window_sha = digest(canonical(raw))
    event_key = digest(canonical([VERSION, scope, SYMBOL, boundary, "UP", "INTRADAY"]))
    stamp = utc(decision)
    rows = []
    for n in range(1, 13):
        value = str(calculated[n]) if n in calculated else None
        rows.append(dict(indicator_id=f"N{n:02}", value=value, raw_value=value, threshold=None,
                         availability="PRESENT" if value is not None else "MISSING",
                         evaluation="UNKNOWN", unit="RATIO_0_1", timeframe="30m/5m",
                         source=scope, as_of=utc(available), version=VERSION,
                         reason_codes=["RESEARCH_COMPONENT_ONLY"] if value is not None else
                                      [reasons.get(n, "SWING_NOT_EVALUATED")]))
    event = dict(schema=SCHEMA, event_type="REJECTED_CANDIDATE",
                 candidate_id="cand-" + event_key, signal_id=None,
                 detection_event_key=event_key, qualification_status="REJECTED",
                 source_scope=scope, source_manifest_id="src-" + source_sha,
                 source_manifest_sha256=source_sha, scan_cycle_id="cycle-" + source_sha,
                 candle_window_sha256=window_sha, quality_policy_version=VERSION,
                 candidate_origin="QUALIFICATION_CANDIDATE", source_quality="VALIDATED",
                 symbol=SYMBOL, direction="UP", horizon="INTRADAY", setup_version="1.1",
                 timestamps=dict(decision_candle_open_at=utc(timestamp(boundary-FIVE_MS)),
                                 decision_candle_close_at=utc(timestamp(boundary)),
                                 received_at=utc(timestamp(received_ms)), available_at=utc(available),
                                 decision_at=stamp, record_created_at=stamp),
                 clock=dict(source="SYNTHETIC_CLOCK" if synthetic else "MEASURED_CLOCK",
                            precision="MILLISECONDS", offset_ms=-(high+low)/2,
                            uncertainty_ms=(high-low)/2),
                 gates=[dict(gate_id="RESEARCH_ONLY", state="FAIL",
                             reason_codes=["NO_APPROVED_QUALIFICATION"])],
                 reject_reason_codes=["NO_APPROVED_QUALIFICATION"], indicators=rows,
                 score=None, trade_plan=None,
                 source_metadata=dict(provider="FIXTURE" if synthetic else BASE,
                                      absolute_utc_pit="HOLD", clock_comparison="SAME_PROVIDER_ONLY"),
                 candle_metadata=dict(frame="5m", count=len(raw), component_parent="AGGREGATE_OF_SIX_CLOSED_5M",
                                      component_close_at=utc(timestamp((boundary//(6*FIVE_MS))*6*FIVE_MS))),
                 scan_metadata=dict(scanner=scan.status, setup=setup["status"], reasons=setup["reason_codes"]),
                 quality_metadata=dict(qualification="RESEARCH_ONLY", dispatch_scope="E2E_TEST_ONLY"))
    ensure_event(event)
    return event


def persist(folder, receipts, event, *, expected_sha=None):
    source_sha = digest(canonical(receipts))
    if source_sha != event["source_manifest_sha256"]:
        raise Stop("SOURCE_HASH_MISMATCH")
    document = make_document(event)
    payload = dict(schema=JOURNAL_SCHEMA, status="RESEARCH_ONLY_READY_FOR_LOCAL_APPLICATION_JOURNAL",
                   source_id=event["detection_event_key"], symbol=event["symbol"],
                   decision_at=event["timestamps"]["decision_at"], signal_id=None,
                   score=None, qualified=False, publishable=False, delivery_authorized=False,
                   source_sha256=source_sha, source_receipts=receipts, stage05_event=event,
                   sql_projection=sql_projection(event), archive_sha256=document["manifest"]["sha256"])
    if expected_sha is not None and digest(canonical(payload)) != expected_sha:
        raise Stop("INTEGRATION_READBACK_PIN_MISMATCH")
    journal = LocalChainJournal(folder / "journal.sqlite")
    identity, outcome = journal.append_readback(payload)
    readback = journal.read_verified(identity)
    if make_document(readback["stage05_event"]) != document:
        raise Stop("ARCHIVE_READBACK_MISMATCH")
    return readback, outcome
