# ORDER-025 — Stage03 engineering and scientific acceptance (not an owner approval)

> **SUPERSEDED FOR STAGE03 CLOSURE — OWNER/PM 2026-11-08.** This is a retained historical research record, **not** an active Stage03 closure checklist. The only active Stage03 closure gates are **C1–C4** in [MASTER](../../ZS_SMART_GATE_MASTER.md) and [Issue #25 PM audit](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6721751412). Historical requirements for blind OOS, forward studies, N_eff/N_REQUIRED, predictive edge, executable PnL, fees/slippage economics, full historical publisher PIT, prospective capture, D1–D5 predictive calibration, and full 00–04 E2E **MUST NOT block C1–C4**. Retain their original scientific limitations for future separately authorized work; never interpret them as waived scientific evidence or as production approval. Tests/evidence already accepted are REUSE, not mandatory RETEST. All new acceptance runs are local Windows only; GitHub Actions checks are not Stage03 acceptance evidence. Stage05, market access, trading and Telegram remain unauthorized.


Authority: [ORDER-025](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6656960128).
Pinned base: main `05ced43dcfbc476a60030283004503945be82120`; MASTER v1.37.
Historical Setup v1.1 SHA256: `0cb5f5aed50ac219d00188cca9827b26ab75dd15a9786773e683b40d10d818ce`.
ORDER022 protocol source blob SHA `3d9021bc204508c22f397799e523fa667189986b`.
Owner-reported historic private report SHA `985abecf489ea23d1e46f9aace7152df8cf997cd94cce33dde440bdb34cea5ee` **has not been independently read here**.

| Gate | Engineering verification now | Scientific qualification | Blocker / evidence required |
|---|---|---|---|
| Frozen source and v1.1 rule | Existing `read_protocol`, archive pinning, byte check; new boundary tests | PROTOCOL_PINNED; not eligible full-signal proof | Independent audit of private frozen manifest, original receipt, and source rights |
| False→true and overlap | New three-trigger inside/outside 12-bar tests with exact raw/suppressed/admitted/label arithmetic | PRICE_ONLY_PARTIAL, NOT full qualification | Actual privately reproducible event counts |
| 12-bar outcomes and no future info | New independent counter + edge, boundary and gap tests | DESCRIPTIVE_PRICE_ONLY | Executable entries/exits and realistic fee/slippage source not established |
| Exact DEV/OOS and purge | Feb 1–Mar 30 DEV; Mar 31–Apr 1 excluded; Apr 2–Jun 30 OOS; Jan warmup | No OOS tuning allowed; existing outcomes ALREADY EXAMINED | A new independent untouched confirmatory set or prospective segment is required before any new threshold/normalizer claims |
| Source provenance/rights | Prior 12 private ZIP hashes reportedly checked on owner Windows | PROVIDER_PUBLICATION_AND_RECEIPT_NOT_ATTESTED | Corroborate old provider CHECKSUM, archive corrections and legal purpose before expanding usage |
| PIT and full market gates | Historic kline timestamps not receipt timestamps; bid/ask and 24h decision snapshots missing | HISTORICAL_FULL_SETUP_NOT_PROVABLE | Owner-approved prospective immutable timestamped read-only capture |
| D1 semantics | Four ambiguous group links explicitly held | PENDING_OWNER_SIGNOFF | SEM-I-01, SEM-I-02, SEM-S-01, SEM-S-02 |
| D2 normalizers | 12 group identities/weights exist; **no numeric formulas accepted** | NORMALIZATION_12_UNAPPROVED | Versioned data fields, polarities, null/outlier rules, DEV alternatives and owner selection |
| D3 outcomes | ORDER022 frozen +12 close-UP descriptive target | NO EXECUTABLE_PNL | Separate entry/exit target, costs and baseline approval for actual scientific evaluation |
| D4 temporal authority | No fake timestamps in core; prospective design not run | PIT_FAIL_HOLD | Independent publication/receipt/clock uncertainty proof |
| D5 validation/samples | DEV/OOS separation + 100 merely descriptive prefilter | N_REQUIRED_UNDETERMINED | Prespecified effect, precision/power, effective sample, regime strata/multiplicity, untouched forward holdout |
| Reproducibility | New owner-private read-only checker verifies 12 ZIP pins, report SHA, event arithmetic, original journal and restore | NOT_INDEPENDENTLY_REPLAYED_YET | Owner executes verifier and independent reviewer inspects redacted receipt |
| Production gate | No Telegram/trading/export; existing flags remain false | BLOCKED | Independent PM/owner scientific acceptance; separate Stage05 order |

**Strict status:** ENGINEERING_FIX_SUBMITTED_FOR_REVIEW, REAL_REPLAY_UNVERIFIED_HERE, HISTORICAL_PIT_UNVERIFIED, N_REQUIRED_UNDETERMINED, STAGE03_OPEN, STAGE05_FULL_HOLD.

The old owner-reported arithmetic is consistent but not independently reproduced:

| Group | Raw | Suppressed | Admitted | Up | Not-up |
|---|---:|---:|---:|---:|---:|
| BTCUSDT DEV | 445 | 140 | 305 | 124 | 181 |
| BTCUSDT OOS | 780 | 283 | 497 | 256 | 241 |
| ETHUSDT DEV | 419 | 124 | 295 | 128 | 167 |
| ETHUSDT OOS | 731 | 240 | 491 | 237 | 254 |

Every row satisfies raw − suppressed = admitted and up + not-up = admitted. Values are from the owner-reported summary in [PM ORDER023 disposition](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6656883207), not re-read archive observations.

**Historical scientific-qualification completion definition (SUPERSEDED AS A STAGE03 CLOSURE GATE):** ALL core tests passed on the same Draft PR head; independent original-archive reproduction; scientific protocol OWNER SIGNED before any new confirmatory outcome; non-fabricated PIT and contemporaneous book/24h for full detection; preset effect/uncertainty/effective N; independent PM validation; explicit owner closure. These remain historical/future scientific qualification criteria only; they are NOT prerequisites for the current Stage03 C1–C4 component closure. The current Stage03 completion definition is solely C1–C4 plus explicit owner closure.
