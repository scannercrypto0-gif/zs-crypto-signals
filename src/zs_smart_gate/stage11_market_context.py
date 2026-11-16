"""Stage11 offline market context on a pinned synthetic eligible universe."""
from collections import Counter
from datetime import timedelta
from decimal import Decimal, DecimalException, localcontext

from .core import utc
from .mtf_contracts import CandleWindow, DURATIONS
from .stage05_contracts import ContractError, canonical, digest, parse_utc

VERSION = "zs.stage11.market-context.v1"
FRAMES = {"Intraday": ("1h", "4h"), "Swing": ("4h", "1d")}
MAX_BARS = 512
MIN_CORRELATION_RETURNS = 3


def metric(status, value=None):
    return {"status": status, "value": value}


def sign(value):
    return "UP" if value > 0 else "DOWN" if value < 0 else "NEUTRAL"


def series(bars, source, frame, decision):
    if bars is None or bars == ():
        return metric("MISSING")
    if not isinstance(bars, tuple) or len(bars) > MAX_BARS:
        return metric("INVALID_DATA")
    previous = None
    for bar in bars:
        if not isinstance(bar, CandleWindow) or bar.timeframe != frame:
            return metric("INVALID_DATA")
        if bar.source_id != source:
            return metric("UNVERIFIED_SOURCE")
        if bar.errors_at(decision) or (previous is not None and bar.open_at != previous):
            return metric("INVALID_DATA")
        previous = bar.close_at
    if decision - bars[-1].close_at >= DURATIONS[frame]:
        return metric("STALE")
    if len(bars) < 2:
        return metric("INSUFFICIENT_COVERAGE")
    try:
        prices = [bar.close for bar in bars]
        returns = [(right-left)/left for left, right in zip(prices, prices[1:])]
        return metric("PRESENT", {
            "closes": [bar.close_at.isoformat() for bar in bars],
            "returns": returns, "window_return": (prices[-1]-prices[0])/prices[0],
        })
    except DecimalException:
        return metric("INVALID_DATA")


def correlation(left, right):
    if len(left) < MIN_CORRELATION_RETURNS:
        return metric("INSUFFICIENT_SAMPLE")
    x_mean, y_mean = sum(left)/len(left), sum(right)/len(right)
    x = [v-x_mean for v in left]
    y = [v-y_mean for v in right]
    xx, yy = sum(v*v for v in x), sum(v*v for v in y)
    if not xx or not yy:
        return metric("CONSTANT_SAMPLE")
    return metric("PRESENT", str(sum(a*b for a,b in zip(x,y))/(xx*yy).sqrt()))


def frame_context(items, subject, members):
    btc, asset = items["BTCUSDT"], items[subject]
    btc_regime = btc
    if btc["status"] == "PRESENT":
        b = btc["value"]
        returns = b["returns"]
        btc_regime = metric("PRESENT", {
            "trend": sign(b["window_return"]), "window_return": str(b["window_return"]),
            "return_count": len(returns),
            "mean_absolute_bar_return": (
                str(sum(abs(x) for x in returns)/len(returns)) if len(returns) >= 2 else None),
            "volatility_status": "PRESENT" if len(returns) >= 2 else "INSUFFICIENT_SAMPLE",
        })
    anchor = btc["value"]["closes"] if btc["status"] == "PRESENT" else None
    aligned = {symbol: item["value"] for symbol, item in items.items()
               if item["status"] == "PRESENT" and item["value"]["closes"] == anchor}
    counts = Counter(sign(aligned[symbol]["window_return"]) for symbol in members if symbol in aligned)
    denominator = len(members)
    aligned_count = sum(symbol in aligned for symbol in members)
    complete = aligned_count == denominator
    breadth = metric("PRESENT" if complete else "INSUFFICIENT_COVERAGE",
                     str(Decimal(counts["UP"]-counts["DOWN"])/denominator) if complete else None)
    breadth.update(eligible_count=denominator, aligned_count=aligned_count,
                   counts={key: counts[key] for key in ("UP", "DOWN", "NEUTRAL")})
    relative = metric("INSUFFICIENT_COVERAGE")
    if subject in aligned:
        delta = aligned[subject]["window_return"]-aligned["BTCUSDT"]["window_return"]
        relative = metric("PRESENT", {"excess_return": str(delta), "direction": sign(delta)})
    elif asset["status"] == btc["status"] == "PRESENT":
        relative = metric("MISALIGNED")
    correlations = {}
    for symbol, item in items.items():
        if symbol == subject:
            continue
        if asset["status"] != "PRESENT" or item["status"] != "PRESENT":
            correlations[symbol] = metric("INSUFFICIENT_COVERAGE")
        elif asset["value"]["closes"] != item["value"]["closes"]:
            correlations[symbol] = metric("MISALIGNED")
        else:
            correlations[symbol] = correlation(asset["value"]["returns"], item["value"]["returns"])
    return {"btc_regime": btc_regime, "breadth": breadth, "relative_strength": relative,
            "correlations": correlations, "series_status": {k:v["status"] for k,v in items.items()}}


def optional_event(event, source, decision):
    if event is None:
        return metric("MISSING")
    if not isinstance(event, dict):
        return metric("INVALID_DATA")
    if event.get("source_id") != source:
        return metric("UNVERIFIED_SOURCE")
    try:
        event_at, published, received, available = (
            parse_utc(event[key]) for key in ("event_at","published_at","received_at","available_at"))
        if not event_at <= published <= received <= available <= decision:
            return metric("INVALID_DATA")
        if not isinstance(event["event_id"], str) or not event["event_id"]:
            return metric("INVALID_DATA")
        return metric("PRESENT", {key:event[key] for key in (
            "event_id","source_id","event_at","published_at","received_at","available_at")})
    except (KeyError, ContractError):
        return metric("INVALID_DATA")


def evaluate_context(*, inventory, inventory_sha256, datasets, subject, direction,
                     horizon, decision_at, source_id, news=None):
    """Inventory is supplied by the caller and fixed at decision time."""
    decision = utc(decision_at)
    if (direction not in ("UP","DOWN") or horizon not in FRAMES
            or not isinstance(source_id, str) or not source_id.startswith("SYNTHETIC:")
            or not isinstance(inventory, dict) or digest(canonical(inventory)) != inventory_sha256
            or inventory.get("source_id") != source_id
            or not isinstance(datasets, dict)):
        raise ContractError("STAGE11_CONTEXT_CONTRACT_INVALID")
    observed, received, ready = (parse_utc(inventory.get(key)) for key in
                                 ("observed_at","received_at","available_at"))
    members = inventory.get("symbols")
    if (not observed <= received <= ready <= decision or not isinstance(members,list)
            or not 2 <= len(members) <= 128 or any(not isinstance(s,str) or not s for s in members)
            or len(set(members)) != len(members)
            or subject not in members or set(datasets)-(set(members) | {"BTCUSDT"})):
        raise ContractError("STAGE11_INVENTORY_INVALID")
    if decision-observed >= min(DURATIONS[frame] for frame in FRAMES[horizon]):
        raise ContractError("STAGE11_INVENTORY_STALE")
    frames = {}
    with localcontext() as ctx:
        ctx.prec = 34
        for frame in FRAMES[horizon]:
            items = {}
            for symbol in dict.fromkeys((*members, "BTCUSDT")):
                asset_frames = datasets.get(symbol, {})
                items[symbol] = (series(asset_frames.get(frame), source_id, frame, decision)
                                 if isinstance(asset_frames,dict) else metric("INVALID_DATA"))
            try:
                frames[frame] = frame_context(items, subject, members)
            except DecimalException:
                frames[frame] = {"status": "INVALID_DATA"}
    row = {"schema":VERSION, "scope":"SYNTHETIC_RESEARCH_ONLY",
           "inventory_sha256":inventory_sha256, "source_id":source_id, "subject":subject,
           "direction":direction, "horizon":horizon, "decision_at":decision.isoformat(),
           "frames":frames, "news":optional_event(news,source_id,decision),
           "eth_btc":metric("NOT_IMPLEMENTED"), "btc_dominance":metric("NOT_IMPLEMENTED"),
           "spot_eligibility_effect":None, "signal_id":None, "trading_authorized":False}
    row["result_sha256"] = digest(canonical(row))
    return row


def synthetic_ablation(context):
    if (context.get("schema") != VERSION or context.get("scope") != "SYNTHETIC_RESEARCH_ONLY"
            or context.get("result_sha256") != digest(canonical({
                key:value for key,value in context.items() if key != "result_sha256"}))):
        raise ContractError("STAGE11_ABLATION_CONTEXT_INVALID")
    baseline = context["direction"]
    comparisons = {}
    for frame, values in context["frames"].items():
        trend = (values.get("btc_regime", {}).get("value") or {}).get("trend")
        comparisons[frame] = None if trend in (None,"NEUTRAL") else trend == baseline
    return {"scope":"SYNTHETIC_DESCRIPTIVE_ONLY", "spot_only":baseline,
            "spot_plus_context":{"baseline":baseline,"btc_trend_agreement":comparisons},
            "predictive_accuracy":None}
