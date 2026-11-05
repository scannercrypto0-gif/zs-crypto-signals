# ORDER-022 — Pre-registered research design and reproducibility

The machine-readable immutable **protocol** is
[\`protocol-v1.json\`](protocol-v1.json). It was published **before
any new real DEV/OOS run**. Do not change it after first source-bound freeze;
altered assumptions require new experiment/version and unexamined OOS.

## Data split and leakage prevention

| Time (UTC) | Partition | Treatment |
|---|---|---|
| Jan 1–31 2025 | Warmup/data integrity | Never score or fit outcomes |
| Feb 1–Mar 30 2025 (exclusive Mar 31) | DEV | Independent private source required |
| Mar 31 and Apr 1 2025 | Purge/embargo | NO evaluated events |
| Apr 2–Jun 30 2025 | OOS | One frozen pass; no refitting or threshold changes |

A test requires **22 consecutive closed 5m bars entirely inside the
partition**. The old and new 21-bar predicates call the **existing**
\`setup021._predicate\` from the pinned \`ORDER021_SETUP_V1_1_FROZEN\`.
Any gap or duplicate prevents falsely continuous windows. OOS never
reuses DEV windows. Future prices enter only *after* a causal trigger
has been evaluated for **descriptive price-direction labels**; an
included outcome requires 12 continuous future 5m bars in the same phase.
A selected partial pattern suppresses the next 11 trigger indices
from the outcome set to avoid overlap; suppression is counted and no
suppressed trade is given an independent result.

## Critical status separation

- \`PARTIAL_PRICE_VOLUME_PATTERN_NOT_DETECTED_SIGNAL\`: a 22-bar,
  false-to-true price/quote-volume predicate, **not an authorized
  \`DETECTED_SIGNAL\`**. Historic bid/ask, 24h quote turnover, genuine
  \`market.observed_at\`, and original publisher receipt are unavailable;
  the existing full \`setup021.evaluate\` is **not** invoked with
  reconstructed/fake snapshots. Its 20 / 1.20 / 90-second guards are unchanged.
- \`HISTORICAL_REPLAY_PIT_UNVERIFIED\`: CSV event times are *exchange bar
  timestamps*, **not independently measured receipt times**. No fake
  \`received_at\` or \`decision_at\` are inserted in the v1.1 contract.
- Price-only outcome: future close at exactly +12 closed 5m bars is
  strictly higher than trigger close. A nonpositive move is recorded
  separately. Outcomes crossing a gap/split are unavailable, not assumed.
- Baseline: every UTC clock-aligned **hourly** 5m reference point with a
  complete valid 12-bar future interval, independently of the setup,
  yields a descriptive future-close-UP/NOT-UP count. Different sampling
  means it is **NOT** a matched causal treatment comparison.
- Predeclared hypothetical *cost parameters* when/if executable data
  becomes available: fee 10bps each side + slippage 5bps each side
  (30bps total). There are **NO execution prices** in the retained 5m
  public candles, so \`return_after_costs=NOT_CALCULATED\`; don't
  treat close-to-close labels as executable P&L.
- Descriptive sample floor **100 nonoverlapping partial patterns and 100
  complete 12-bar labels per symbol/per phase**, **not** a statistical
  power calculation. True \`N_REQUIRED\` is \`UNDETERMINED\`. Even
  crossing this arbitrary review floor would not establish signal
  accuracy or full eligibility.

**No combined DEV/OOS score.** Report counts, negative outcomes, missing
source status, gaps, duplicate rejects, gross coverage and reproducible
signatures per symbol/partition; OOS can't tune v1.1.

## Workflow with locally retained real source (NOT executed in this delivery)

1. Place the existing 12 private ZIPs under an authorized local
   \`DATA_DIR\` (not Git). Use a local catalog with 12 explicit external
   SHA-256 pins and source descriptions; note that a claimed provider
   checksum is not independent proof until checked.
2. \`PYTHONPATH=src python scripts/order022-offline-history.py inventory --data-dir DATA_DIR --catalog LOCAL_CATALOG.json --output local-inventory.json\`
3. \`PYTHONPATH=src python scripts/order022-offline-history.py freeze --data-dir DATA_DIR --catalog LOCAL_CATALOG.json --manifest PRIVATE_MANIFEST.json --output local-freeze-receipt.json\`
4. \`PYTHONPATH=src python scripts/order022-offline-history.py run --data-dir DATA_DIR --manifest PRIVATE_MANIFEST.json --database private-results.sqlite --backup private-restored.sqlite --output private-report.json\`

**All output paths are create-once**, except the append-only SQLite report
table which rejects conflicting replays. A run fails if any frozen input ZIP
or the current study module / Setup source / preregistered protocol differs.
The report includes readback and independent SQLite backup restore with
payload hashes; no GitHub token, service, network, collector or sender is
required. This is development research; owner-Windows production recovery
has **not** been proven.

In «GitHub Actions» the allowed offline tests use **\`SYNTHETIC_TEST\`**
archives generated inside temporary test directories and an empty-source
inventory. Synthetic outputs are solely engineering regression evidence,
**never real market research results**.
