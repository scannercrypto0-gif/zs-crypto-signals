# ORDER-022 — Data Coverage & Integrity Inventory (pre-acquisition/pre-run)

**Authority:** Issue #25, PM 1.4 ORDER-022 comment #6653952899.
**Time of review:** 2026-11-05 UTC. **This is not a newly executed market-data import.**

## Source location and access result

| Field | Evidence actually available | Confidence |
|---|---|---|
| Source/provider | Prior 010-B reported Binance Vision public Spot monthly ZIPs | Prior executor report only; no new source download |
| Assets / interval | BTCUSDT and ETHUSDT, Spot 5m | Prior report, PR #27 remains independent/draft |
| Period | 2025-01-01 through 2025-06-30 UTC | Prior report |
| Verified previous archive scope | 48 ZIP + 48 provider checksums, 5m/30m/1h/4h (not all required now) | Prior executor reported checksum/schema PASS |
| Previous 5m interval rows | **104,256 combined** across BTCUSDT and ETHUSDT, 52,128 each expected if full continuous Jan–Jun | Previously reported, not re-opened |
| All-interval rows | 132,492 (overlapping time scales, NOT independent samples) | Previously reported |
| Prior transferred/extracted bytes | 7,025,238 / 21,277,099 for all 48 ZIPs | Previously reported |
| Full raw files / per-ZIP hashes available in GitHub main | **NO**; repo tree contains code/research documents but not these market ZIPs | Confirmed by main tree (99 entries) |
| Data via project conversation files | **NO** corresponding raw archive; only HANDOFF.txt + historical pasted work note | Search result, not the owner's D: filesystem |
| Prior private retention | \`D:\ZS-SMART-GATE\evidence\science-010B\batch-B\` and related private evidence | Prior reported, **not accessed or independently verified now** |
| Prior dataset-index SHA-256 | \`ce0a3716f24612ea04427b12454e420f9f7e10a0a9bedd622c0ac866a372da79\` | Index **hash only**, not recoverable dataset bytes |
| Current OHLCV validation/gaps/duplicates | **NOT RECHECKED** without private ZIPs | UNKNOWN |
| Historical bookTicker / 24h liquidity at decisions | **NOT PRESENT** for complete 6-month study | UNKNOWN; don't fabricate |
| Publisher/receipt PIT and independent UTC | **NOT PROVEN** by archive timestamp or checksum | \`HISTORICAL_REPLAY_PIT_UNVERIFIED\` |
| Data permission | Prior noncommercial/internal research process and public data claim; raw/derived tables deliberately kept private | Cannot claim a new distribution right |

**Official previous evidence:** [PR #27](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/27) and
[010-B acceptance ledger](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6579747449).
Do not use its frozen wider-model outcomes as results of ORDER-021 v1.1.

## Required offline archive inventory

The ORDER-022 runner expects **12** already-obtained source archives, each
named \`BTCUSDT-5m-2025-01.zip\` through \`BTCUSDT-5m-2025-06.zip\`,
and the six equivalent \`ETHUSDT\` files. They must be supplied
out-of-band within approved private custody, never added to this PR.
For *each archive* an operator-created local catalog pins:
\`symbol, month, name, sha256, source, provider_checksum_attested\`.
Source \`REAL_ARCHIVE_PRIVATE\` requires
\`source=BINANCE_VISION_SPOT_PUBLIC_ARCHIVE\`.
The runner **recomputes ZIP byte SHA-256**; \`provider_checksum_attested\`
is a **catalog assertion**, not an independent live provider attestation.
Do not upgrade provenance without a separate corroborated provider checksum.

Before freezing, the engine validates exact ZIP membership and size caps,
12-column public Binance Spot CSV, **microsecond** timestamps as reported for
the 2025 source, aligned exclusive close time, finite Decimal OHLCV, symbol/
month boundaries, monotonicity, gaps and duplicates. It produces a
structural coverage inventory and freezes the source SHA list before
evaluating a single setup outcome.

**Current status:** \`DATASET_BYTES_NOT_ACCESSIBLE_IN_THIS_EXECUTION /
REAL_DEV_NOT_RUN / REAL_OOS_NOT_RUN /
FROZEN_DATA_BOUND_MANIFEST_NOT_CREATED /
INSUFFICIENT_EVIDENCE\`.

The committed **protocol** is preregistered before OOS results.
The dataset-specific **manifest may only be created after all twelve
verified files exist** and before the first genuine evaluation.
That distinction is required: assigning imaginary ZIP hashes would be
fabricating data identity.

## Minimum-friction unblocked continuation

The existing owner-held **010-B 12 Spot/5m ZIP files** are the shortest
source route. A future authorized executor can run the offline inventory,
build a SHA catalog from verified retained bytes and the old provider
checksum evidence, freeze a new ORDER-022 manifest, then run the analysis
with no market calls, no trading, no Telegram, and no private data upload.
If local archives cannot be supplied, owner/PM may separately authorize
a bounded historical-only provider acquisition; this ORDER-022 delivery
**does not** perform or preapprove that new download.
