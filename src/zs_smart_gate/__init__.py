"""SMART GATE research-only foundation. No live trading, storage, or Telegram."""
from .core import (Candle, MarketSnapshot, ResearchCandidate, validate_candles,
                   spread_bps, check_eligibility, rvol, impulse_probe,
                   build_candidate, score_v1_partial)
