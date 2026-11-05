"""SYNTHETIC ONLY reproducible ORDER-021 fixtures. NOT Binance observations."""
from datetime import datetime, timedelta, timezone

from .core import MarketSnapshot
from .binance_live import timestamp

BAR_MS = 300000


def scenario(start_utc: str, *, symbol="BTCUSDT", breakout=True, missing=False, forming=False, delayed=False):
    start = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
    if start.tzinfo is None or start.utcoffset() != timedelta(0):
        raise ValueError("UTC_FIXTURE_START_REQUIRED")
    start_ms = int(start.timestamp() * 1000)
    if start_ms % BAR_MS:
        raise ValueError("FIVE_MINUTE_ALIGNMENT_REQUIRED")
    bars = []
    for idx in range(22):
        open_ms = start_ms + BAR_MS * idx
        is_trigger = idx == 21 and breakout
        high = "112" if is_trigger else "101"
        close = "111" if is_trigger else "100"
        quote = "1300" if is_trigger else "1000"
        bars.append([open_ms, "100", high, "99", close, "10", open_ms + BAR_MS - 1, quote, "0", "0", "0", "0"])
    if missing:
        bars.pop(12)
    last_end = start_ms + BAR_MS * 22
    receipt_ms = last_end + (120000 if delayed else (0 if forming else 1000))
    if forming:
        receipt_ms = last_end - 1000
    received = timestamp(receipt_ms)
    decision = received + timedelta(seconds=1)
    market = MarketSnapshot(symbol=symbol,quote_asset="USDT",spot_enabled=True,trading_status="TRADING",
        quote_volume_24h="50000000",bid="100",ask="100.01",observed_at=received)
    return dict(symbol=symbol,klines=bars,market=market,received_at=received,decision_at=decision)
