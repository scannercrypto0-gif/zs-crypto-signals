# ORDER-021 — Setup v1 frozen contract and evidence limits

Authority: Issue #25 comment 6652586815, MASTER v1.37 on main
\`1723c4c4b0299034084aa0dadf75eceb54d1394b\`. **Development only.**

## One setup, no optimization on OOS

**ORDER021_SETUP_V1_FROZEN** selects:
- One direction **UP**, one horizon **INTRADAY_5M**, Binance public
  **BTCUSDT / ETHUSDT Spot** fixture format, no trading or output delivery.
- Two rolling windows of **21 consecutive, aligned, completed 5m candles each**,
  overlapping by 20 bars: **22 sequential raw bars** in total.
- Predicate at the final bar: its close is **strictly greater** than
  the maximum HIGH of the preceding 20; close is also **greater than open**;
  quote volume is at least **1.20 × arithmetic mean of the preceding 20
  quote volumes**. Denominator must be positive. Exactly the same predicate
  is evaluated one candle earlier on the preceding 21-bar window.
- Internal detection **only** for **previous FALSE → current TRUE**.
  Previous UNKNOWN/invalid cannot be promoted. Every final candle must have
  been closed and received before the decision; the exact final candle must
  be the requested candle (no fallback to a previous candle when forming).
- Source parser: existing \`binance_live.to_candles\` and
  \`core.validate_candles\`; scanner gate: existing
  \`scanner.inspect_candles\` and \`core.build_candidate\`. Market
  snapshot must match the symbol and pass existing Spot, liquidity and spread
  guards **at decision time**. Do not copy scanner thresholds into a
  parallel formula; the accepted implementation remains the source of truth.
- Fixture receipt/decision lag is bounded to **90 seconds** (no new network
  SLA claim). The archive replay receipt metadata is **not** independently
  verified historical arrival. **Real prospective receipt capture is not
  implemented or authorized by ORDER-021.**
- \`event_id\` = SHA-256(canonical sorted JSON of
  \`contract_version, symbol, direction, horizon, setup_id,
  trigger_closed_candle_time_ms, source_event_identity\`).
  Different independent closed events have different identity; SQLite
  UNIQUE ensures readback dedup for identical events. This is **research event
  identity**, not downstream delivery or exact-once messaging.
- \`SCORE_UNAVAILABLE\`, \`score=null\`, \`probability=null\`,
  \`publishable=false\`, \`qualified=false\` regardless of detection.
  \`DETECTED_SIGNAL\` labels only an internal reproducible observation
  of this one predicate, **not** \`QUALIFIED_SIGNAL\`, a profitable
  trading prediction, or production permission.

### Strict history / OOS separation

\`DEV\`: synthetic September 2026 windows; \`OOS\`: **different, later**
synthetic October 2026 windows with exactly the **same constant frozen
CONFIG**. No search or retune of lookback, volume ratio, direction, trigger,
choice of symbol, price/staleness guard or market eligibility using OOS.
\`PROSPECTIVE\` is deliberately refused by this replay harness: genuine
owner-time receipts and a separate approved Manifest and PM review are absent.
\`HISTORICAL_PIT_UNVERIFIED\` throughout. All reported detections and exclusions
are **synthetic test data**, not backtest success.

OOS sample outcomes are **UNAVAILABLE**; financial performance, win rate,
profit factor, slippage and fees are **NOT CALCULATED** and no sample-size power
claim is made. Real DEV/OOS coverage inventory and a predeclared minimum
sample requirement **must precede** performance OOS assessment. This module
does not alter the frozen 010–020 protocols or historical results.

### Engineering quality gates

- Real code path: fixture → existing Binance REST-format parser → existing
  scanner+core candidate → closed/ordered decision validation → one predicate
  → immutable row/event identity → SQLite atomic commit/WAL/FULL sync →
  readback through independent connection → SQLite backup API to **separate**
  database → integrity/hash/row verification.
- Failure scenarios: false/non-breakout, prior-TRUE suppression, missing bar,
  gap, forming bar, stale receipt, future market snapshot, late decision,
  zero denominator, bad symbol, wrong partition, duplicate receipt,
  conflicting event identity, corruption, injected storage outage, reopen
  after interruption. No concealed replays.
- During development \`SQLiteResearchJournal\` is a swappable **research
  adapter**, not verified owner-Windows production custody, backup encryption
  or live GitHub writer. CI uses only local tempfiles; optional GitHub Actions
  artifacts retain **synthetic reports only**, never market, account or host
  secrets. Historical Stage04 custody remains unchanged.
- Setup v1 must run solely from a standard Python 3.11/3.12 installation.
  No network requests or new scheduler/task; \`GitHub Actions\` is temporary
  for development and tested on both Windows and Ubuntu.
- Acceptance of this PR does **not** authorize live capture, Stage05,
  Telegram, private APIs, trading, scoring calibration, PIT certification,
  merging other drafts, or Stage03 closure.

### Independent review questions

1. Are the **single setup** trigger and its 20-bar/volume controls adequate
   as a minimal research hypothesis, without claiming profit? If the PM
   wants a materially different detection rule, treat it as a **new version**
   and predeclare before testing any real OOS.
2. Can the local adapter's interfaces later preserve all identity, readback
   and restoration semantics under owner-Windows service/backup faults?
   This must be tested at final deployment, not inferred from hosted CI.
3. Which real historical data rights/coverage justify evaluation of fees,
   slippage and the minimum sample requirement? Until established, mark
   \`INSUFFICIENT_EVIDENCE\`.

### Reproduction

\`PYTHONPATH=src python -m unittest discover -s tests -p test_setup021.py -v\`

\`PYTHONPATH=src python scripts/order021-offline-e2e.py --output order021-e2e.json\`

Both are deliberately offline and synthetic. Run the full existing foundation
regression in GitHub Actions and inspect the new \`021\` workflow artifacts.
