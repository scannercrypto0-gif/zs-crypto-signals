"""Stage10 synthetic, point-in-time derivatives context; no transport."""
from decimal import Decimal, DecimalException

from .stage05_contracts import ContractError, canonical, digest, parse_utc

VERSION = "zs.stage10.futures-context.v1"
FEEDS = ("oi", "price", "funding", "ratio", "aggtrades", "depth", "liquidations")
MAX_ROWS = 4096


def number(value, *, signed=False, positive=False):
    if not isinstance(value, str):
        raise ValueError("DECIMAL_STRING_REQUIRED")
    result = Decimal(value)
    if not result.is_finite() or (positive and result <= 0) or (not signed and result < 0):
        raise ValueError("INVALID_NUMERIC_VALUE")
    return result


def result(status, value=None, **details):
    return {"status": status, "value": value, **details}


def bounded_rows(feed, source, symbol, start, decision, max_age_seconds):
    if feed is None:
        return result("MISSING")
    if feed.get("source_id") != source:
        return result("UNVERIFIED_SOURCE")
    if feed.get("symbol") != symbol:
        raise ValueError("SYMBOL_MISMATCH")
    pages = feed["pages"]
    if not isinstance(pages, list) or not 1 <= len(pages) <= 64:
        raise ValueError("PAGES_INVALID")
    rows = []
    expected_cursor = 0
    interval = feed["coverage"]
    coverage_start, coverage_end = (parse_utc(interval[key]) for key in ("start", "end"))
    if coverage_start != start or coverage_end > decision or coverage_start > coverage_end:
        return result("INSUFFICIENT_COVERAGE")
    for index, page in enumerate(pages):
        batch = page["rows"]
        if type(page["cursor"]) is not int or page["cursor"] != expected_cursor:
            raise ValueError("PAGE_CURSOR_MISMATCH")
        if not isinstance(batch, list) or (not batch and len(pages) > 1):
            raise ValueError("PAGE_ROWS_INVALID")
        expected_cursor += len(batch)
        next_cursor = page["next_cursor"]
        if index < len(pages)-1:
            if type(next_cursor) is not int or next_cursor != expected_cursor:
                raise ValueError("PAGE_CHAIN_BROKEN")
        elif next_cursor is not None:
            return result("INSUFFICIENT_COVERAGE")
        rows.extend(batch)
        if len(rows) > MAX_ROWS:
            raise ValueError("ROW_LIMIT")
    previous, identities = None, set()
    for row in rows:
        event, receipt, ready = (parse_utc(row[key]) for key in
                                 ("event_at", "received_at", "available_at"))
        if (row.get("source_id") != source or row.get("symbol") != symbol
                or not start <= event <= coverage_end
                or not event <= receipt <= ready <= decision):
            raise ValueError("ROW_SOURCE_OR_TIME_INVALID")
        if previous is not None and event < previous:
            raise ValueError("EVENT_ORDER_INVALID")
        identity = row["id"]
        if type(identity) not in (str, int) or identity in identities:
            raise ValueError("INVALID_OR_DUPLICATE_ID")
        identities.add(identity)
        previous = event
    if (interval.get("complete") is not True or type(interval.get("row_count")) is not int
            or interval["row_count"] != len(rows)):
        return result("INSUFFICIENT_COVERAGE")
    watermark = parse_utc(interval["available_at"])
    if not coverage_end <= watermark <= decision:
        raise ValueError("COVERAGE_TIME_INVALID")
    if (decision - coverage_end).total_seconds() > max_age_seconds:
        return result("STALE")
    return rows


def measure(kind, rows, coverage_end, decision, max_age_seconds):
    if kind in ("aggtrades", "liquidations") and coverage_end != decision:
        return result("INSUFFICIENT_COVERAGE")
    if not rows and kind not in ("aggtrades", "liquidations"):
        return result("MISSING")
    if rows and kind not in ("aggtrades", "liquidations"):
        if (decision - parse_utc(rows[-1]["event_at"])).total_seconds() > max_age_seconds:
            return result("STALE")
    if kind in ("oi", "price"):
        field = "contracts" if kind == "oi" else "price"
        values = [number(r[field], positive=kind == "price") for r in rows]
        times = [r["event_at"] for r in rows]
        if len({parse_utc(t) for t in times}) != len(times):
            raise ValueError("DUPLICATE_SERIES_TIMESTAMP")
        return result("PRESENT", {"current": str(values[-1]),
            "history": [{"event_at": t, "value": str(v)} for t,v in zip(times,values)],
            "change": str(values[-1]-values[0]) if len(values)>1 else None})
    if kind == "funding":
        history = []
        for row in rows:
            start, end = (parse_utc(row[key]) for key in ("period_start","period_end"))
            if not start < end == parse_utc(row["event_at"]):
                raise ValueError("FUNDING_APPLICATION_TIME_INVALID")
            history.append(dict(rate=str(number(row["rate"], signed=True)),
                                period_start=row["period_start"], applied_at=row["period_end"]))
        return result("PRESENT", {"latest": history[-1], "history": history})
    if kind == "ratio":
        row = rows[-1]
        if row["definition"] not in ("GLOBAL_ACCOUNT_RATIO", "TOP_ACCOUNT_RATIO", "TOP_POSITION_RATIO"):
            raise ValueError("RATIO_DEFINITION_INVALID")
        return result("PRESENT", {"ratio": str(number(row["ratio"])), "definition": row["definition"],
                                  "event_at": row["event_at"]})
    if kind == "aggtrades":
        ids = [r["id"] for r in rows]
        if any(type(i) is not int or i < 0 for i in ids):
            raise ValueError("AGGTRADE_ID_INVALID")
        if any(b != a+1 for a,b in zip(ids,ids[1:])):
            return result("INSUFFICIENT_COVERAGE")
        delta = Decimal(0)
        for row in rows:
            maker = row["buyer_is_maker"]
            if type(maker) is not bool:
                raise ValueError("MAKER_FLAG_INVALID")
            number(row["price"], positive=True)
            qty = number(row["base_qty"], positive=True)
            delta += -qty if maker else qty
        return result("PRESENT", {"base_cvd": str(delta), "count": len(rows)})
    if kind == "liquidations":
        events = []
        for row in rows:
            if row["event_type"] != "ACTUAL_LIQUIDATION" or row["order_side"] not in ("BUY","SELL"):
                raise ValueError("ACTUAL_LIQUIDATION_REQUIRED")
            events.append({"id":row["id"], "event_at":row["event_at"], "order_side":row["order_side"],
                           "price":str(number(row["price"], positive=True)),
                           "base_qty":str(number(row["base_qty"], positive=True))})
        return result("PRESENT", {"events":events,"count":len(events)})
    row = rows[-1]
    sides = []
    for key in ("bids", "asks"):
        levels = row[key]
        if not isinstance(levels, list) or not 1 <= len(levels) <= 1000:
            raise ValueError("DEPTH_LEVEL_LIMIT")
        parsed = [(number(price, positive=True), number(qty, positive=True)) for price,qty in levels]
        prices = [price for price, _ in parsed]
        if len(set(prices)) != len(prices) or sorted(prices, reverse=key=="bids") != prices:
            raise ValueError("DEPTH_LEVEL_ORDER")
        sides.append(parsed)
    bids,asks = sides
    if bids[0][0] >= asks[0][0]:
        raise ValueError("DEPTH_CROSSED")
    bid_qty,ask_qty = (sum(q for _,q in side) for side in sides)
    zones = [[{"price":str(p),"base_qty":str(q)} for p,q in
              sorted(side,key=lambda level:(-level[1],level[0]))[:3]] for side in sides]
    return result("PRESENT", {"base_imbalance": str((bid_qty-ask_qty)/(bid_qty+ask_qty)),
                              "bid_zones": zones[0], "ask_zones":zones[1],
                              "event_at":row["event_at"]})


def evaluate_context(feeds, *, source_id, symbol, window_start, decision_at, max_age_seconds):
    """Use caller-pinned synthetic source, symbol, decision and freshness limit."""
    start, decision = parse_utc(window_start), parse_utc(decision_at)
    if (not isinstance(source_id,str) or not source_id.startswith("SYNTHETIC:")
            or not isinstance(symbol,str) or not symbol or not start < decision
            or type(max_age_seconds) is not int or max_age_seconds <= 0
            or not isinstance(feeds,dict) or set(feeds)-set(FEEDS)):
        raise ContractError("STAGE10_CONTEXT_CONTRACT_INVALID")
    try:
        input_hash = digest(canonical(feeds))
    except ContractError:
        input_hash = None
    metrics = {}
    for kind in FEEDS:
        try:
            feed = feeds.get(kind)
            # Reject non-JSON feed values independently of unrelated feeds.
            if input_hash is None:
                canonical(feed)
            rows = bounded_rows(feed, source_id, symbol, start, decision, max_age_seconds)
            metrics[kind] = (rows if isinstance(rows, dict) else
                             measure(kind, rows, parse_utc(feed["coverage"]["end"]), decision, max_age_seconds))
            if metrics[kind]["status"] == "PRESENT":
                interval = feed["coverage"]
                metrics[kind]["coverage"] = {
                    **{key: interval[key] for key in ("start", "end", "available_at", "complete", "row_count")},
                    "coverage_to_decision": parse_utc(interval["end"]) == decision,
                    "kind": ("COMPLETE_INTERVAL" if kind in ("aggtrades", "liquidations")
                             else "AS_OF_SAMPLE"),
                }
        except (ValueError, TypeError, KeyError, AttributeError, DecimalException) as exc:
            metrics[kind] = result("INVALID_DATA", reason=str(exc) if type(exc) in (ValueError, ContractError) else "MALFORMED_FEED")
    price, oi = metrics["price"], metrics["oi"]
    relationship = result("INSUFFICIENT_COVERAGE")
    if price["status"] == oi["status"] == "PRESENT":
        left, right = price["value"]["history"], oi["value"]["history"]
        if len(left) >= 2 and [parse_utc(x["event_at"]) for x in left] == [parse_utc(x["event_at"]) for x in right]:
            relationship = result("PRESENT", {"price_change":price["value"]["change"],
                                               "oi_change":oi["value"]["change"],
                                               "position_side_inference":None})
    cvd = metrics["aggtrades"]
    divergence = result("INSUFFICIENT_COVERAGE")
    if price["status"] == cvd["status"] == "PRESENT":
        history = price["value"]["history"]
        # Compare only endpoints that cover the same complete trade interval.
        if parse_utc(history[0]["event_at"]) == start and parse_utc(history[-1]["event_at"]) == decision:
            delta = Decimal(price["value"]["change"])
            flow = Decimal(cvd["value"]["base_cvd"])
            divergence = result("PRESENT", {"price_delta": str(delta), "base_cvd": str(flow),
                "relationship": ("FLAT_COMPONENT" if not delta or not flow else
                                 "OPPOSITE_SIGNS" if (delta > 0) != (flow > 0) else "SAME_SIGN")})
    out = dict(schema=VERSION, scope="SYNTHETIC_RESEARCH_ONLY", symbol=symbol, source_id=source_id,
               window_start=window_start, decision_at=decision_at, max_age_seconds=max_age_seconds,
               input_sha256=input_hash, metrics=metrics, oi_price=relationship, price_cvd=divergence,
               spot_eligibility_effect=None, score=None, signal_id=None, trading_authorized=False)
    out["result_sha256"] = digest(canonical(out))
    return out


def synthetic_ablation(baseline_direction, context):
    """Compare context sign with a fixed UP/DOWN baseline without altering it."""
    if baseline_direction not in ("UP","DOWN"):
        raise ContractError("STAGE10_BASELINE_DIRECTION_INVALID")
    if (context.get("schema") != VERSION or context.get("scope") != "SYNTHETIC_RESEARCH_ONLY"
            or context.get("result_sha256") != digest(canonical({
                k:v for k,v in context.items() if k != "result_sha256"}))):
        raise ContractError("STAGE10_ABLATION_CONTEXT_INVALID")
    cvd = context["metrics"]["aggtrades"]
    value = Decimal(cvd["value"]["base_cvd"]) if cvd["status"] == "PRESENT" else None
    direction = None if value is None or value == 0 else "UP" if value > 0 else "DOWN"
    return {"scope":"SYNTHETIC_DESCRIPTIVE_ONLY", "spot_only":baseline_direction,
            "spot_plus_context":{"baseline":baseline_direction,"cvd_direction":direction,
                                 "agreement": None if direction is None else direction == baseline_direction},
            "predictive_accuracy":None}
