# FOUNDATION-001 — implementation boundary

Scope: Python standard-library research-only contracts and deterministic synthetic unit tests.
Status: working proof of core contracts, NOT a live scanner, trading system, approved signal policy, or finalized old SMART GATE baseline.

## What is actually implemented
- Immutable typed 5m candle and Spot market snapshot models (UTC-aware timestamps).
- Strict exactly-21 contiguous closed-candle and available-at-decision validation.
- Reference Spot/USDT universe: tradable, 24h quote volume >= 10,000,000, spread <= 20 basis points.
- Separate BASE and QUOTE RVOL over 20 preceding candles, no zero-denominator imputation.
- Separate close-to-previous-close and open-to-close percentage observations.
- Opt-in experimental impulse probe with explicit basis and volume choice (NOT production classification).
- Incomplete V1 score component observables; no published score or probability.
- Deterministic research candidate output with typed quality limitations.

## Intentionally unimplemented / approval needed
- Actual EXTENDED +/-8% window and precedence, original price comparison basis, RVOL type, MTF net/path formula, and consistency up/down semantics.
- Signal identity, event lifecycle, low-scoring delivery handling, any Telegram outbox/retries, real tokens or dispatch.
- Github-only permanent historical and operational storage backend; Windows buffering and outage behavior.
- Intraday/Swing predictive labels, calibrated predictions, persistence, real Binance connector, live scheduler.
- Entry/stop/targets and automated orders.

## Safety and timing conventions
Candle close_at is the EXCLUSIVE UTC end boundary; received_at >= close_at, available_at >= received_at.
A candle cannot be a decision feature unless close_at <= decision_at and available_at <= decision_at.
No future labels are merged into research features.
Market observed_at cannot exceed decision_at; snapshot freshness beyond that requires an approved contract.
Only synthetic records are processed. No network API calls or persistence.

## Running tests

    PYTHONPATH=src python -m unittest discover -s tests -v

On PowerShell:

    $env:PYTHONPATH = "src"; python -m unittest discover -s tests -v

GitHub Actions runs the same tests on Ubuntu and Windows with Python 3.11/3.12.
These unit tests establish behavior, not prediction accuracy or operational reliability.
