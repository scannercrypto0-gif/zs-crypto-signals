"""FOUNDATION-001: explicit point-in-time research contracts (stdlib only).

The classification probe is experimental and NOT an adopted historical baseline.
No Signal Event, order, Telegram, or durable storage is implemented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Sequence

FIVE_MINUTES = timedelta(minutes=5)
MIN_QUOTE_VOLUME = Decimal("10000000")
MAX_SPREAD_BPS = Decimal("20")
PRICE_THRESHOLD_PCT = Decimal("0.7")
RVOL_THRESHOLD = Decimal("2")


def decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("bool is not a numeric observation")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid numeric observation") from exc
    if not result.is_finite():
        raise ValueError("non-finite numeric observation")
    return result


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class Candle:
    open_at: datetime
    close_at: datetime  # exclusive UTC boundary, open_at + 5 minutes
    received_at: datetime
    available_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    base_volume: Decimal
    quote_volume: Decimal

    def __post_init__(self) -> None:
        for field in ("open_at", "close_at", "received_at", "available_at"):
            object.__setattr__(self, field, utc(getattr(self, field)))
        for field in ("open", "high", "low", "close", "base_volume", "quote_volume"):
            object.__setattr__(self, field, decimal(getattr(self, field)))


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    quote_asset: str
    spot_enabled: bool
    trading_status: str
    quote_volume_24h: Decimal
    bid: Decimal
    ask: Decimal
    observed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", utc(self.observed_at))
        for field in ("quote_volume_24h", "bid", "ask"):
            object.__setattr__(self, field, decimal(getattr(self, field)))


@dataclass(frozen=True)
class ResearchCandidate:
    symbol: str
    decision_at: datetime
    status: str
    eligibility_reasons: tuple[str, ...]
    candle_errors: tuple[str, ...]
    c2c_pct: Decimal | None
    oc_pct: Decimal | None
    rvol_base_20: Decimal | None
    rvol_quote_20: Decimal | None
    spread_bps: Decimal | None
    impulse_classification: str
    score: int | None
    score_status: str
    reason_codes: tuple[str, ...]

    def as_dict(self) -> dict:
        """Deterministic JSON-compatible research row; not a live Signal Event."""
        return {
            "symbol": self.symbol,
            "decision_at": self.decision_at.isoformat(),
            "status": self.status,
            "eligibility_reasons": list(self.eligibility_reasons),
            "candle_errors": list(self.candle_errors),
            "c2c_pct": str(self.c2c_pct) if self.c2c_pct is not None else None,
            "oc_pct": str(self.oc_pct) if self.oc_pct is not None else None,
            "rvol_base_20": str(self.rvol_base_20) if self.rvol_base_20 is not None else None,
            "rvol_quote_20": str(self.rvol_quote_20) if self.rvol_quote_20 is not None else None,
            "spread_bps": str(self.spread_bps) if self.spread_bps is not None else None,
            "impulse_classification": self.impulse_classification,
            "score": self.score,
            "score_status": self.score_status,
            "reason_codes": list(self.reason_codes),
        }


def validate_candles(candles: Sequence[Candle], decision_at: datetime) -> tuple[str, ...]:
    """Require exactly 21 continuous CLOSED 5m candles, known at decision time."""
    decision_at = utc(decision_at)
    errors: list[str] = []
    if len(candles) != 21:
        errors.append("EXPECTED_21_CANDLES")
    previous = None
    for idx, c in enumerate(candles):
        if c.open_at.second != 0 or c.open_at.microsecond != 0 or c.open_at.minute % 5:
            errors.append(f"CANDLE_{idx}_BAD_ALIGNMENT")
        if c.close_at - c.open_at != FIVE_MINUTES:
            errors.append(f"CANDLE_{idx}_BAD_DURATION")
        if previous is not None and c.open_at != previous.close_at:
            errors.append(f"CANDLE_{idx}_GAP_OR_OVERLAP")
        if c.open_at >= c.close_at or c.received_at < c.close_at or c.available_at < c.received_at:
            errors.append(f"CANDLE_{idx}_TIME_ORDER")
        if c.close_at > decision_at or c.available_at > decision_at:
            errors.append(f"CANDLE_{idx}_FUTURE_OR_UNAVAILABLE")
        if (c.low <= 0 or c.high < c.low or c.open < c.low or c.open > c.high
                or c.close < c.low or c.close > c.high):
            errors.append(f"CANDLE_{idx}_INVALID_OHLC")
        if c.base_volume < 0 or c.quote_volume < 0:
            errors.append(f"CANDLE_{idx}_INVALID_VOLUME")
        previous = c
    return tuple(errors)


def spread_bps(bid: Decimal, ask: Decimal) -> Decimal:
    bid, ask = decimal(bid), decimal(ask)
    if bid <= 0 or ask <= 0 or ask < bid:
        raise ValueError("INVALID_BID_ASK")
    return Decimal("10000") * (ask - bid) / ((ask + bid) / 2)


def check_eligibility(market: MarketSnapshot, decision_at: datetime) -> tuple[str, ...]:
    decision_at = utc(decision_at)
    # An observation made later cannot supply *any* PIT eligibility or market feature.
    # Do not inspect quote volume, bid/ask, trading flags or quote asset in this case.
    if market.observed_at > decision_at:
        return ("MARKET_SNAPSHOT_FROM_FUTURE",)
    reasons: list[str] = []
    if not market.symbol or market.quote_asset != "USDT" or not market.symbol.endswith("USDT"):
        reasons.append("NOT_USDT_PAIR")
    if not market.spot_enabled or market.trading_status != "TRADING":
        reasons.append("SPOT_NOT_TRADABLE")
    if market.quote_volume_24h < MIN_QUOTE_VOLUME:
        reasons.append("LOW_24H_QUOTE_VOLUME")
    try:
        if spread_bps(market.bid, market.ask) > MAX_SPREAD_BPS:
            reasons.append("SPREAD_ABOVE_LIMIT")
    except ValueError:
        reasons.append("INVALID_BID_ASK")
    return tuple(reasons)


def rvol(candles: Sequence[Candle], kind: str) -> Decimal | None:
    """Explicit independent BASE or QUOTE comparison; no assumed legacy volume type."""
    if kind not in ("base", "quote"):
        raise ValueError("kind must be base or quote")
    if len(candles) != 21:
        return None
    field = "base_volume" if kind == "base" else "quote_volume"
    values = [getattr(c, field) for c in candles]
    if any(x < 0 for x in values):
        return None
    mean = sum(values[:-1], Decimal("0")) / Decimal("20")
    return values[-1] / mean if mean > 0 else None


def price_changes(candles: Sequence[Candle]) -> tuple[Decimal, Decimal]:
    if len(candles) < 2 or candles[-2].close <= 0 or candles[-1].open <= 0:
        raise ValueError("NO_VALID_PRICE_BASE")
    last = candles[-1]
    c2c = Decimal("100") * (last.close - candles[-2].close) / candles[-2].close
    oc = Decimal("100") * (last.close - last.open) / last.open
    return c2c, oc


def impulse_probe(price_change_pct: Decimal, observed_rvol: Decimal,
                  *, basis: str, volume_kind: str) -> str:
    """Opt-in what-if probe. NOT approved for actual signal/event classification.

    EXTENDED precedence/window remains unresolved and is intentionally absent.
    """
    if basis not in ("CLOSE_TO_PREVIOUS_CLOSE_5M", "OPEN_TO_CLOSE_5M"):
        raise ValueError("explicit experimental price basis required")
    if volume_kind not in ("BASE", "QUOTE"):
        raise ValueError("explicit experimental volume basis required")
    p, v = decimal(price_change_pct), decimal(observed_rvol)
    if v < 0:
        raise ValueError("negative RVOL")
    if v < RVOL_THRESHOLD:
        return "NO_IMPULSE"
    if p >= PRICE_THRESHOLD_PCT:
        return "UPWARD_IMPULSE"
    if p <= -PRICE_THRESHOLD_PCT:
        return "DOWNWARD_IMPULSE"
    return "NO_IMPULSE"


def score_v1_partial(price_change_pct: Decimal | None, observed_rvol: Decimal | None,
                     spread: Decimal | None) -> dict:
    """Research-only normalized components; never fabricate a full score or probability.

    C2C and BASE here are explicit experimental comparison bases. Original MTF,
    up/down consistency and precise legacy input choices remain unresolved.
    """
    components: dict[str, str | None] = {
        "price_momentum_35": None,
        "volume_expansion_25": None,
        "liquidity_quality_10": None,
        "mtf_alignment_20": None,
        "momentum_consistency_10": None,
    }
    if price_change_pct is not None:
        p = max(decimal(price_change_pct), Decimal("0"))
        components["price_momentum_35"] = str(Decimal("35") * p / (p + Decimal("0.7")))
    if observed_rvol is not None:
        observed_rvol = decimal(observed_rvol)
        if observed_rvol < 0:
            raise ValueError("INVALID_RVOL")
        v = max(observed_rvol - 1, Decimal("0"))
        components["volume_expansion_25"] = str(Decimal("25") * v / (v + 1))
    if spread is not None:
        spread = decimal(spread)
        if spread < 0:
            raise ValueError("INVALID_SPREAD")
        components["liquidity_quality_10"] = str(Decimal("10") * Decimal("20") / (Decimal("20") + spread))
    return {"total": None, "status": "SCORE_UNAVAILABLE", "version": "V1_PARTIAL_RESEARCH_ONLY",
            "components": components}


def build_candidate(market: MarketSnapshot, candles: Sequence[Candle],
                    decision_at: datetime) -> ResearchCandidate:
    decision_at = utc(decision_at)
    eligibility = check_eligibility(market, decision_at)
    errors = validate_candles(candles, decision_at)
    if "MARKET_SNAPSHOT_FROM_FUTURE" in eligibility:
        # Fail closed before exposing any computed market/candle research feature.
        return ResearchCandidate(
            market.symbol, decision_at, "UNAVAILABLE_MARKET", eligibility, errors,
            None, None, None, None, None, "UNRESOLVED_CONTRACT", None,
            "SCORE_UNAVAILABLE", ("MARKET_SNAPSHOT_FROM_FUTURE", "NO_SIGNAL_EVENT"))
    if errors:
        return ResearchCandidate(
            market.symbol, decision_at, "INVALID_CANDLES", eligibility, errors,
            None, None, None, None, None, "UNRESOLVED_CONTRACT", None,
            "SCORE_UNAVAILABLE", ("CANDLE_QUALITY_FAILURE", "NO_SIGNAL_EVENT"))
    try:
        spread = spread_bps(market.bid, market.ask)
    except ValueError:
        spread = None
    c2c, oc = price_changes(candles)
    base, quote = rvol(candles, "base"), rvol(candles, "quote")
    reasons = ["RESEARCH_CANDIDATE_ONLY", "NO_SIGNAL_EVENT",
               "IMPULSE_PRICE_BASIS_UNAPPROVED", "EXTENDED_WINDOW_UNRESOLVED",
               "MTF_FORMULA_UNRESOLVED", "SCORE_UNAVAILABLE"]
    if base is None:
        reasons.append("RVOL_BASE_DENOMINATOR_MISSING")
    if quote is None:
        reasons.append("RVOL_QUOTE_DENOMINATOR_MISSING")
    if eligibility:
        reasons.append("UNIVERSE_NOT_ELIGIBLE")
    return ResearchCandidate(
        market.symbol, decision_at, "ELIGIBLE" if not eligibility else "INELIGIBLE",
        eligibility, errors, c2c, oc, base, quote, spread,
        "UNRESOLVED_CONTRACT", None, "SCORE_UNAVAILABLE", tuple(reasons))
