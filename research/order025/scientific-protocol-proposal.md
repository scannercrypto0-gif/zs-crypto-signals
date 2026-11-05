# ORDER-025 — Scientific protocol candidate for owner approval (NOT FROZEN / NOT EXECUTED)

**Current frozen reference**: ORDER021_SETUP_V1_1_FROZEN / original ORDER022 historical protocol unchanged. This document is **a proposed new scientific contract for an as-yet-unseen future prospective/confirmatory set**, not an amendment to the already evaluated historical OOS, and not authorization to run any source.

## Distinct research questions (do not mix estimands)

**A. Price-only retrospective (available in existing private 010-B run):**
Define a `partial` event as first false-to-true closed 5m candle above the previous 20 highs, bullish and quote volume >=1.20× previous 20 mean quote volume, with 12-bar nonoverlap. The binary **descriptive** target is `close[t+12]>close[t]` on complete consecutive bars within DEV/OOS. It does not measure spread, executable returns, signal eligibility, or chance of profitable trade.

**B. Historically full Setup v1.1:**
Requires bookTicker bid/ask and 24h liquidity snapshot *as observed and knowable before decision* plus verifiable source publication and receipt timing/clock uncertainty. The 010-B OHLCV archives **do not prove B**. Status: HISTORICAL_FULL_SETUP_NOT_PROVABLE unless independent time-valid historical snapshots are furnished. Do not reconstruct book/receipts from OHLCV.

**C. Prospective source-valid shadow evaluation (separately authorized later):**
Freeze scope, source & receipt contract and hash-chained append-only raw observation journal before the first live packet. Apply unchanged v1.1, count all rejected/unknown candidates and transitions. No market or account orders, no Telegram, no Stage05. C is not authorized by this document.

## D1–D5 disposition: owner decisions explicitly OPEN

- **D1 — four ambiguous semantics:** `SEM-I-01 SIX_5M_INTERNAL_QUALITY` vs `internal_path`; `SEM-I-02 VOLUME_CONTINUITY` vs `volume`; `SEM-S-01 FOUR_1H_INTERNAL_QUALITY` vs `internal_path`; `SEM-S-02 DAILY_WEEKLY_CONTEXT` vs `higher_context`. Select exact semantics, input clocks, and domain boundaries for each. Existing `stage03_contract_alignment.py` deliberately leaves these unmapped.
- **D2 — twelve normalizers:** intraday `30M_STRONG_CLOSE, SIX_5M_INTERNAL_QUALITY, MOMENTUM_EARLY_TIMING, VOLUME_CONTINUITY, MTF_NEARBY_STRUCTURE, LIQUIDITY_QUALITY`; swing `MARKET_STRUCTURE, FOUR_H_STRONG_CLOSE, FOUR_1H_INTERNAL_QUALITY, DAILY_WEEKLY_CONTEXT, MOMENTUM_VOLUME, LIQUIDITY_QUALITY`. For EACH, define source, UTC availability, units, polarity, transform A/B tested on DEV only, robust missing/outlier behavior, versioned normalization and an unambiguous mapping to the existing weights. **Neither formula nor resulting 0..1 score is approved yet.** Keep `SCORE_UNAVAILABLE` and no production score. Setup v1.1's simple deterministic detection remains separately usable as research without making V2 weights mandatory for its predicate.
- **D3 — outcomes and qualification:** owner chooses whether the primary target is *directional close movement* (A, non-executable) or a genuinely executable trade target with fixed after-cost entry/exit (C, prospective). Fix candidate vs detected vs qualified statuses, source timing, cost policy, and objective definition **before** further confirmatory OOS/forward. Do not rename past directional success as P&L.
- **D4 — publication/clock authority:** minimum chain `source_event_time ≤ independently recorded receipt_time ≤ available_at ≤ decision_at`, with separately measured uncertainty and retention of source bytes/headers, rather than assuming independent accuracy from a server timestamp or client clock. Previous <1s scientific clock target remains **unverified**; owner must approve concrete precision/evidence rules and the source measurement scope, not weaken it for PASS.
- **D5 — validation/inference:** exact disjoint calendar windows, embargo at least the 12-bar observation horizon (existing two-day exclusion is stronger), group identifiers, regime strata, baseline matched by asset/time/regime, loss definitions, confounders, multiple-test policy, confidence intervals by independent date/cluster and **N_REQUIRED before viewing untouched results**. Existing `100` is only a heuristic descriptive review floor, NOT a power calculation.

## Scientific effect sizes and uncertainty on ALREADY REPORTED historical values

This table is **derived arithmetic only from owner-supplied counts** (not independently verified). Percent is the fraction of 12-bar outcomes with future close higher than trigger close; NOT winning trades. Wilson intervals are **unadjusted indicative binomial intervals**, not valid inferential coverage under serial dependence, heterogeneous regimes, and previous outcome exposure.

| Symbol / partition | Up / observed | Price-up share | Nominal unadjusted Wilson 95% |
|---|---:|---:|---:|
| BTC DEV | 124 / 305 | 40.66% | 35.29%–46.25% |
| BTC OOS | 256 / 497 | 51.51% | 47.12%–55.87% |
| ETH DEV | 128 / 295 | 43.39% | 37.86%–49.09% |
| ETH OOS | 237 / 491 | 48.27% | 43.88%–52.69% |

Do **not** apply the OOS figures to select a new threshold, normalizer, or success criterion; OOS has already been observed by the owner and is no longer a completely blind future holdout. Without **hourly reference outcomes plus entry/exit costs and cluster dependence**, a treatment effect, independent CI, trading expectancy and numerical `N_REQUIRED` cannot be certified.

## Recommended pre-registration template (requires owner sign-off)

Before any **new** confirmatory evaluation:
1. Pin source rights, data schema, source bytes/packet hashes, 5m interval, exact two assets, chronological unseen dates, update/correction policy.
2. Pin one **primary** estimand, binary labels and null handling, matched control/baseline and fee/slippage executable basis if target is trading. Original v1.1 remains unchanged.
3. Pin one primary comparison or a finite family, alpha/multiplicity adjustment and clustering unit (e.g. day/session with asset/regime stratification). No unregistered lookups.
4. Specify a minimum meaningful effect `delta`, control prevalence `p0`, tolerance `epsilon`, sample dependence/design effect and statistical power. `N_REQUIRED=UNDETERMINED` until these values are approved and the effective-N method can be justified. A naive independent-binomial starting value for precision h is `ceil(1.96²*p*(1-p)/h²)` (p=0.5 worst case), then inflate for temporal dependence; **not an approved N threshold**.
5. Explicitly define reject conditions: missing timestamps, incoherent clocks/receipts, future bars, stale bid/ask/24h, changed contracts, source checksum changes, leakage, no control or low effective N, large missingness, ambiguous license, or unapproved selective OOS runs.
6. Retain separate per-symbol DEV, independent OOS and forward records; preserve all zero/negative/unknown outcomes and failures. An independent auditor must reproduce before owner can judge scientific PASS.

**No task here implies authority to tune or change v1.1, approve D1–D5 numerics, collect market data or close Stage03.**
