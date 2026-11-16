# Stage10 — Futures context, order flow and liquidity

Standalone offline contract `zs.stage10.futures-context.v1`. Use `evaluate_context` with a synthetic source identity, symbol, UTC observation window and caller-specified engineering freshness bound. Spot Scanner has no dependency on this module. Its eligibility and decisions are unaffected by context.

| Requirement | Implementation and test evidence |
|---|---|
| OI current/history and price synchronization | Decimal deltas and exact timestamp joins. No long/short attribution from OI. |
| Funding and long/short | Signed funding rate with applied UTC time and explicit period. Ratios keep global account, top account and top position definitions distinct. These are descriptive measurements without a crowding threshold. |
| AggTrades | One synthetic source and symbol, bounded ordered pages and row count, unique consecutive aggregate IDs, coverage through decision. Buyer-maker means sell aggression; buyer-taker means buy aggression. A price/CVD sign comparison requires matched window endpoints. |
| Depth and liquidation | Ordered uncrossed book, signed base-quantity imbalance and largest three levels per side; only explicitly typed source liquidation events. Inferred candles are rejected. |
| PIT and missingness | Event ≤ receipt ≤ availability ≤ decision, matching source and symbol, declared coverage watermark ≤ decision. Missing, stale, unverified, incomplete and invalid are distinct; an attested empty stream may measure zero events. |
| Isolation and ablation | Separate module, import isolation test, descriptive baseline-vs-CVD sign agreement with immutable baseline and no predictive accuracy. |

Each feed declares `coverage` (`start`, `end`, `available_at`, `complete`, `row_count`), source/symbol and pages (`cursor`, `next_cursor`, `rows`). The cursor is a normalized row offset rather than an exchange token. Every row carries source, symbol, identity and three UTC stamps. Completeness in this contract is a synthetic attestation, never an exchange authority claim. A raw Binance adapter, independent coverage verification and measured latency require separate work and authority. Binance liquidation snapshot feeds must not be assumed complete.

## Illustrative API cost and latency

Assumptions for sizing only. Budget one current OI, one OI history, one funding, one ratio, two AggTrades pages, one book and one reference-price request. At eight hypothetical calls of 150 ms each, serial time is about 1.2 seconds before parsing, retries or throttling. Under a hypothetical two weight units per call, cost would be 16 units. These are planning assumptions, not exchange weights, measured latency or a live budget. Liquidation streaming cost is excluded because no connection is implemented. Keep this optional workload off the Spot Scanner's critical path.

Run only Stage10 using `PYTHONPATH=src` and `py -3.12 -m unittest discover -s tests -p test_stage10_futures_context.py -v`.
