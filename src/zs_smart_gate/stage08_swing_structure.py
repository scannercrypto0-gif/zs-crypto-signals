"""Stage08 source-bound swing structure research (offline synthetic only).

Independent of Stage03/Stage07 identity, qualification and dispatch. Closed,
available, contiguous UTC inputs only. No network, database or trade execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

from .core import utc
from .mtf_contracts import CandleWindow, ReconciliationTolerance, reconcile
from .stage03_r0_identity import SYMBOL, stamp
from .stage05_contracts import ContractError, SHA, canonical, digest, parse_utc

VERSION = "zs.stage08.swing-structure.v1"
OUTCOME_VERSION = "zs.stage08.retrospective-observation.v1"
ZERO = Decimal("0")
ONE = Decimal("1")
PIVOT_LEFT = 2
PIVOT_RIGHT = 2
MAX_HISTORY = 512
EXACT_SYNTHETIC = ReconciliationTolerance(
    ZERO, ZERO, ZERO, "STAGE08_SYNTHETIC_EXACT_NOT_REAL_SOURCE_POLICY")


@dataclass(frozen=True)
class EightHourObservation:
    open_at: datetime
    close_at: datetime
    received_at: datetime
    available_at: datetime
    source_id: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    base_volume: Decimal
    quote_volume: Decimal


@dataclass(frozen=True)
class SwingWindow:
    symbol: str
    direction: str
    parent_4h: CandleWindow
    children_1h: tuple[CandleWindow, ...]
    history_4h: tuple[CandleWindow, ...] = ()
    comparison_8h: EightHourObservation | None = None
    daily: tuple[CandleWindow, ...] = ()
    weekly: tuple[CandleWindow, ...] = ()
    source_manifest_sha256: str = ""
    source_scope: str = "SYNTHETIC_TEST_ONLY"


def _unavailable(reason: str) -> dict:
    return {"schema": VERSION, "status": "UNAVAILABLE",
            "reason_codes": [reason], "qualification_state": "RESEARCH_ONLY",
            "signal_id": None, "score": None, "publishable": False,
            "dispatch_allowed": False, "features": {}}


def _validate_sequence(bars: Sequence[CandleWindow], frame: str, source: str,
                       observed: datetime, decision: datetime) -> str | None:
    previous = None
    if len(bars) > MAX_HISTORY:
        return "HISTORY_LIMIT_EXCEEDED"
    for bar in bars:
        if not isinstance(bar, CandleWindow) or bar.timeframe != frame:
            return "FRAME_MISMATCH:" + frame
        if bar.source_id != source:
            return "SOURCE_MISMATCH:" + frame
        if previous is not None and bar.open_at != previous:
            return "GAP_DUPLICATE_OR_OUT_OF_ORDER:" + frame
        if bar.close_at > observed:
            return "POST_EVENT_CONTEXT_FORBIDDEN:" + frame
        errors = bar.errors_at(decision)
        if errors:
            return "INVALID_OR_UNAVAILABLE_" + frame + ":" + ",".join(errors)
        previous = bar.close_at
    return None


def _finite_comparison(c: EightHourObservation) -> bool:
    return all(isinstance(getattr(c, k), Decimal) and getattr(c, k).is_finite()
               for k in ("open", "high", "low", "close", "base_volume", "quote_volume"))


def _eight_hour(comparison: EightHourObservation | None,
                prior: Sequence[CandleWindow], parent: CandleWindow,
                decision: datetime) -> dict:
    if comparison is None:
        return {"status": "UNAVAILABLE", "reason": "OPTIONAL_8H_NOT_SUPPLIED"}
    c = comparison
    if not isinstance(c, EightHourObservation) or not _finite_comparison(c):
        raise ContractError("STAGE08_8H_TYPED_FINITE_REQUIRED")
    try:
        times = tuple(utc(x) for x in
                      (c.open_at, c.close_at, c.received_at, c.available_at))
    except (ValueError, TypeError):
        raise ContractError("STAGE08_8H_UTC_REQUIRED") from None
    start, end, received, available = times
    if (end - start != timedelta(hours=8)
            or int(start.timestamp()) % (8*3600) != 0
            or not end <= received <= available <= decision
            or end != parent.close_at or c.source_id != parent.source_id):
        raise ContractError("STAGE08_8H_SOURCE_TIME_INVALID")
    if not prior:
        raise ContractError("STAGE08_8H_PRIOR_4H_REQUIRED")
    before = prior[-1]
    if before.open_at != start or before.close_at != parent.open_at:
        raise ContractError("STAGE08_8H_COMPONENT_ALIGNMENT_INVALID")
    if (c.open != before.open or c.close != parent.close
            or c.high != max(before.high, parent.high)
            or c.low != min(before.low, parent.low)
            or c.base_volume != before.base_volume + parent.base_volume
            or c.quote_volume != before.quote_volume + parent.quote_volume):
        raise ContractError("STAGE08_8H_RECONCILIATION_FAILED")
    return {"status": "PRESENT", "close": str(c.close),
            "signed_return": str((c.close-c.open)/c.open),
            "close_at": stamp(end), "available_at": stamp(available),
            "source_id": c.source_id, "components": 2}


def _pivots_and_breaks(bars: Sequence[CandleWindow]) -> dict:
    """Strict 2-left/2-right extrema, confirmed only when right bars arrive.

    Equal high/low neighbors invalidate that candidate pivot (no guess).
    Only a close crossing a *previously confirmed* pivot creates a break.
    A wick crossing without close is descriptive and never BOS/CHoCH.
    """
    pivots: list[dict] = []
    breaks: list[dict] = []
    high_ref = low_ref = None
    broken = set()
    state = "UNKNOWN"
    ties = 0
    latest_wick = None
    for i, bar in enumerate(bars):
        j = i - PIVOT_RIGHT
        if j >= PIVOT_LEFT:
            center = bars[j]
            neighbors = [bars[k] for k in range(j-PIVOT_LEFT, j+PIVOT_RIGHT+1) if k != j]
            for kind, value, test in (
                    ("HIGH", center.high, lambda v, other: v > other),
                    ("LOW", center.low, lambda v, other: v < other)):
                peers = [getattr(x, "high" if kind == "HIGH" else "low") for x in neighbors]
                if all(test(value, v) for v in peers):
                    first_available = max(x.available_at for x in bars[j-PIVOT_LEFT:i+1])
                    row = {"kind": kind, "pivot_at": stamp(center.close_at),
                           "confirmation_close_at": stamp(bar.close_at),
                           "first_available_at": stamp(first_available),
                           "price": str(value), "right_bars": PIVOT_RIGHT,
                           "left_bars": PIVOT_LEFT,
                           "source_id": center.source_id}
                    pivots.append(row)
                    if kind == "HIGH":
                        high_ref = row
                    else:
                        low_ref = row
                elif any(value == v for v in peers):
                    ties += 1
        if i == 0:
            continue
        previous = bars[i-1]
        for side, ref in (("UP", high_ref), ("DOWN", low_ref)):
            if ref is None:
                continue
            level = Decimal(ref["price"])
            ident = (side, ref["pivot_at"], ref["confirmation_close_at"])
            if side == "UP":
                crossed_close = previous.close <= level < bar.close
                crossed_wick = previous.close <= level < bar.high and bar.close <= level
            else:
                crossed_close = previous.close >= level > bar.close
                crossed_wick = previous.close >= level > bar.low and bar.close >= level
            if crossed_wick:
                latest_wick = {"side": side, "status": "WICK_ONLY",
                               "observed_close_at": stamp(bar.close_at),
                               "source_level": str(level)}
            if crossed_close and ident not in broken:
                # Delayed inputs can make retrospective knowledge later than
                # the bar close. Record the actual latest availability.
                confirmed = parse_utc(ref["first_available_at"])
                knowledge = max(bar.available_at, previous.available_at, confirmed)
                breaks.append({"side": side,
                               "kind": ("INITIAL_BREAK" if state == "UNKNOWN"
                                        else "BOS" if state == side else "CHoCH"),
                               "prior_state": state, "pivot_at": ref["pivot_at"],
                               "level": str(level), "event_close_at": stamp(bar.close_at),
                               "first_available_at": stamp(knowledge),
                               "criterion": "CLOSE_CROSS_ONLY",
                               "source_id": bar.source_id})
                broken.add(ident)
                state = side
    latest_close = bars[-1].close_at if bars else None
    return {"status": "PRESENT" if len(bars) >= 5 else "INSUFFICIENT_HISTORY",
            "minimum_bars": 5, "bar_count": len(bars), "tie_rejections": ties,
            "confirmed_pivots": pivots, "close_breaks": breaks,
            "latest_wick_only": latest_wick,
            "structure_state": state,
            "latest_parent_break": (next((x for x in reversed(breaks)
                if parse_utc(x["event_close_at"]) == latest_close), None)
                if latest_close else None)}


def _ema_series(values: Sequence[Decimal], period: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    if len(values) < period:
        return result
    previous = sum(values[:period], ZERO) / Decimal(period)  # SMA seed
    result[period-1] = previous
    alpha = Decimal(2) / Decimal(period+1)
    for idx in range(period, len(values)):
        previous = (values[idx]-previous)*alpha + previous
        result[idx] = previous
    return result


def _rsi(values: Sequence[Decimal], period: int = 14) -> Decimal | None:
    if len(values) < period+1:
        return None
    changes = [b-a for a, b in zip(values, values[1:])]
    gains = [max(v, ZERO) for v in changes]
    losses = [max(-v, ZERO) for v in changes]
    gain = sum(gains[:period], ZERO)/Decimal(period)
    loss = sum(losses[:period], ZERO)/Decimal(period)
    for x, y in zip(gains[period:], losses[period:]):
        gain = (gain*(period-1)+x)/Decimal(period)
        loss = (loss*(period-1)+y)/Decimal(period)
    if not gain and not loss:
        return Decimal(50)
    if not loss:
        return Decimal(100)
    return Decimal(100) - Decimal(100)/(ONE+gain/loss)


def _feature(value: Decimal | None, *, frame: str, minimum: int,
             count: int, source: CandleWindow | None,
             definition: str, unit: str) -> dict:
    return {"status": "PRESENT" if value is not None else "INSUFFICIENT_HISTORY",
            "value": str(value) if value is not None else None,
            "timeframe": frame, "period_definition": definition,
            "minimum_bars": minimum, "available_bars": count, "unit": unit,
            "source_id": source.source_id if source else None,
            "event_close_at": stamp(source.close_at) if source else None,
            "available_at": stamp(source.available_at) if source else None}


def _descriptors(history: Sequence[CandleWindow], daily: Sequence[CandleWindow],
                 weekly: Sequence[CandleWindow]) -> dict:
    closes = [b.close for b in history]
    source4 = history[-1] if history else None
    e12 = _ema_series(closes, 12)
    e26 = _ema_series(closes, 26)
    macd = [a-b for a, b in zip(e12, e26) if a is not None and b is not None]
    signal = _ema_series(macd, 9)
    values = {
        "ema12_4h": (e12[-1] if e12 else None, 12, "EMA12_SMA12_SEED", "PRICE"),
        "ema26_4h": (e26[-1] if e26 else None, 26, "EMA26_SMA26_SEED", "PRICE"),
        "rsi14_4h": (_rsi(closes), 15, "WILDER_RSI14_SMA14_CHANGES_SEED", "INDEX_0_100"),
        "macd_12_26_9_line": (macd[-1] if macd else None, 26,
                              "EMA12_MINUS_EMA26", "PRICE_DELTA"),
        "macd_12_26_9_signal": (signal[-1] if signal else None, 34,
                                "EMA9_SMA9_SEED_OF_MACD", "PRICE_DELTA"),
    }
    out = {k: _feature(v, frame="4h", minimum=n, count=len(history),
                       source=source4, definition=rule, unit=unit)
           for k, (v, n, rule, unit) in values.items()}
    source_w = weekly[-1] if weekly else None
    ma50 = (sum((x.close for x in weekly[-50:]), ZERO)/Decimal(50)
            if len(weekly) >= 50 else None)
    out["ma50_week_close"] = _feature(ma50, frame="1w", minimum=50,
        count=len(weekly), source=source_w, definition="SMA50_OF_50_CLOSED_WEEKLY_CLOSES",
        unit="PRICE")
    for frame, bars in (("1d", daily), ("1w", weekly)):
        src = bars[-1] if bars else None
        out["latest_"+frame+"_close"] = _feature(
            src.close if src else None, frame=frame, minimum=1,
            count=len(bars), source=src, definition="LAST_AVAILABLE_CLOSED_CLOSE",
            unit="PRICE")
    return out


def analyze_swing(window: SwingWindow, *, decision_at: datetime) -> dict:
    """One fully bounded Stage08 snapshot; no qualified signal is possible."""
    if not isinstance(window, SwingWindow):
        return _unavailable("SWING_INPUT_TYPE_REQUIRED")
    try:
        decision = utc(decision_at)
    except (ValueError, TypeError):
        return _unavailable("DECISION_UTC_REQUIRED")
    if (not isinstance(window.symbol, str) or not SYMBOL.fullmatch(window.symbol)
            or window.direction not in ("UP", "DOWN")
            or window.source_scope != "SYNTHETIC_TEST_ONLY"
            or not isinstance(window.source_manifest_sha256, str)
            or not SHA.fullmatch(window.source_manifest_sha256)):
        return _unavailable("SYNTHETIC_RESEARCH_IDENTITY_REQUIRED")
    p = window.parent_4h
    if not isinstance(p, CandleWindow) or p.timeframe != "4h":
        return _unavailable("PARENT_4H_REQUIRED")
    if p.errors_at(decision):
        return _unavailable("PARENT_4H_INVALID_OR_UNAVAILABLE")
    if not p.source_id.startswith("SYNTHETIC:"):
        return _unavailable("UNVERIFIED_SOURCE")
    if not isinstance(window.children_1h, tuple) or len(window.children_1h) != 4:
        return _unavailable("FOUR_1H_CHILDREN_REQUIRED")
    if not all(isinstance(x, tuple) for x in
               (window.history_4h, window.daily, window.weekly)):
        return _unavailable("HISTORY_SEQUENCE_REQUIRED")
    source = p.source_id
    for bars, frame in ((window.children_1h, "1h"), (window.history_4h, "4h"),
                        (window.daily, "1d"), (window.weekly, "1w")):
        error = _validate_sequence(bars, frame, source, p.close_at, decision)
        if error:
            return _unavailable(error)
    if window.history_4h and window.history_4h[-1].close_at != p.open_at:
        return _unavailable("4H_HISTORY_NOT_ADJACENT")
    if reconcile(p, window.children_1h, decision,
                 tolerance=EXACT_SYNTHETIC).status != "PASS":
        return _unavailable("4X1H_RECONCILIATION_FAILED")
    try:
        eight = _eight_hour(window.comparison_8h, window.history_4h, p, decision)
    except ContractError as exc:
        return _unavailable(str(exc))
    all4 = (*window.history_4h, p)
    structure = _pivots_and_breaks(all4)
    features = _descriptors(all4, window.daily, window.weekly)
    observed = {
        "4h_close_open_direction": ("UP" if p.close > p.open else
                                     "DOWN" if p.close < p.open else "FLAT"),
        "4h_vs_last_daily_close": (("ABOVE" if p.close > window.daily[-1].close else
                                    "BELOW" if p.close < window.daily[-1].close else "EQUAL")
                                   if window.daily else "UNKNOWN"),
        "4h_vs_last_weekly_close": (("ABOVE" if p.close > window.weekly[-1].close else
                                     "BELOW" if p.close < window.weekly[-1].close else "EQUAL")
                                    if window.weekly else "UNKNOWN"),
        "structure_direction_agreement": (
            "UNKNOWN" if structure["structure_state"] == "UNKNOWN" else
            "AGREES" if structure["structure_state"] == window.direction else "CONFLICTS"),
    }
    key = digest(canonical([VERSION, window.symbol, window.direction,
                             stamp(p.close_at), p.source_id, window.source_manifest_sha256]))
    def snapshot_bar(bar: CandleWindow) -> list[str]:
        return [bar.timeframe, stamp(bar.open_at), stamp(bar.close_at),
                stamp(bar.received_at), stamp(bar.available_at), bar.source_id,
                *[str(getattr(bar, k)) for k in
                  ("open", "high", "low", "close", "base_volume", "quote_volume")]]
    content = [snapshot_bar(b) for b in
               (*window.history_4h, p, *window.children_1h,
                *window.daily, *window.weekly)]
    if window.comparison_8h is not None:
        content.append(["8h", stamp(utc(window.comparison_8h.open_at)),
                        stamp(utc(window.comparison_8h.close_at)),
                        stamp(utc(window.comparison_8h.received_at)),
                        stamp(utc(window.comparison_8h.available_at)),
                        window.comparison_8h.source_id,
                        *[str(getattr(window.comparison_8h, k)) for k in
                          ("open", "high", "low", "close", "base_volume", "quote_volume")]])
    row = {
        "schema": VERSION, "status": "RESEARCH_MEASURED",
        "source_scope": "SYNTHETIC_TEST_ONLY",
        "symbol": window.symbol, "direction": window.direction,
        "event_id": "s08-" + key, "candidate_id": "s08cand-" + key,
        "source_id": source, "source_manifest_sha256": window.source_manifest_sha256,
        "parent_close_at": stamp(p.close_at), "parent_available_at": stamp(p.available_at),
        "decision_at": stamp(decision), "decision_reference_price": str(p.close),
        "decision_lag_seconds": str(Decimal(str((decision-p.close_at).total_seconds()))),
        "comparison_8h": eight, "structure": structure,
        "timeframe_context": observed, "features": features,
        "input_sha256": digest(canonical([VERSION, key, content])),
        "no_lookahead": True, "qualification_state": "RESEARCH_ONLY",
        "signal_id": None, "score": None, "publishable": False,
        "dispatch_allowed": False, "is_trade": False,
    }
    row["result_sha256"] = digest(canonical(row))
    return row


def retrospective_swing_observation(research: dict, future: Sequence[CandleWindow],
                                    *, as_of: datetime) -> dict:
    """Descriptive post-decision returns only; never mutate original decision."""
    if (not isinstance(research, dict) or research.get("schema") != VERSION
            or research.get("status") != "RESEARCH_MEASURED"
            or research.get("signal_id") is not None
            or research.get("publishable") is not False
            or research.get("result_sha256") != digest(canonical({
                k: v for k, v in research.items() if k != "result_sha256"}))):
        raise ContractError("STAGE08_OUTCOME_RESEARCH_RECEIPT_REQUIRED")
    decision = parse_utc(research["decision_at"])
    now = utc(as_of)
    if now < decision:
        raise ContractError("STAGE08_OUTCOME_BEFORE_DECISION")
    if not isinstance(future, (tuple, list)):
        raise ContractError("STAGE08_OUTCOME_SEQUENCE_REQUIRED")
    # A post-decision FULL 4h bar opens on the next UTC boundary.
    duration_seconds = 4 * 3600
    first_start = datetime.fromtimestamp(
        ((int(decision.timestamp()) // duration_seconds) + 1) * duration_seconds,
        timezone.utc)
    if future:
        if not isinstance(future[0], CandleWindow) or future[0].open_at < decision:
            raise ContractError("STAGE08_OUTCOME_STRADDLES_DECISION")
        invalid = _validate_sequence(future, "4h", research["source_id"], now, now)
        if invalid:
            raise ContractError("STAGE08_OUTCOME_INVALID:" + invalid)
    initial_gap = bool(future and future[0].open_at != first_start)
    ref = Decimal(research["decision_reference_price"])
    change = ((future[-1].close-ref)/ref if future and not initial_gap else None)
    status = ("CENSORED_NO_BARS" if not future else
              "CENSORED_GAP" if initial_gap else "OBSERVED")
    result = {
        "schema": OUTCOME_VERSION, "research_sha256": research["result_sha256"],
        "as_of": stamp(now), "status": status,
        "expected_first_full_bar_at": stamp(first_start),
        "closed_bar_count": len(future),
        "last_available_at": stamp(future[-1].available_at) if future else None,
        "signed_close_return": str(change) if change is not None else None,
        "note": "OBSERVED_PRICE_CHANGE_NOT_CAUSAL_PREDICTION_OR_EXECUTED_TRADE",
        "is_trade": False, "is_signal": False,
    }
    result["result_sha256"] = digest(canonical(result))
    return result


def compare_synthetic_structure(records: Sequence[dict]) -> dict:
    """Descriptive same-window baseline vs confirmed structure, not predictive edge.

    Baseline is the parent 4h candle close-open direction; alternative is
    last structurally confirmed breakout state, or UNKNOWN. No future labels.
    """
    if not isinstance(records, (tuple, list)) or len(records) > 128:
        raise ContractError("STAGE08_COMPARISON_BOUNDED_RECORDS_REQUIRED")
    out = {"count": len(records), "known_pairs": 0, "agreements": 0,
           "disagreements": 0, "unknown_pairs": 0}
    for row in records:
        if (not isinstance(row, dict) or row.get("schema") != VERSION
                or row.get("status") != "RESEARCH_MEASURED"
                or row.get("source_scope") != "SYNTHETIC_TEST_ONLY"
                or row.get("signal_id") is not None
                or row.get("publishable") is not False
                or row.get("result_sha256") != digest(canonical({
                    k: v for k, v in row.items() if k != "result_sha256"}))):
            raise ContractError("STAGE08_COMPARISON_RESEARCH_RECEIPT_REQUIRED")
        base = row["timeframe_context"]["4h_close_open_direction"]
        alt = row["structure"]["structure_state"]
        if base not in ("UP", "DOWN") or alt not in ("UP", "DOWN"):
            out["unknown_pairs"] += 1
        else:
            out["known_pairs"] += 1
            out["agreements" if base == alt else "disagreements"] += 1
    return {"schema": "zs.stage08.synthetic-baseline.v1",
            "baseline": "CURRENT_4H_CLOSE_MINUS_OPEN_SIGN",
            "alternative": "LAST_CONFIRMED_CLOSE_BREAK_STRUCTURE_STATE",
            "summary": out, "source_scope": "SYNTHETIC_TEST_ONLY",
            "scientific_validity": "CONTEMPORANEOUS_DESCRIPTIVE_ONLY_NOT_OOS",
            "false_positive_rate": None, "prediction_accuracy": None,
            "qualification_authority": None}
