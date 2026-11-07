# Stage03 P0 — bounded source evidence gate and scientific/computational separation

Authority: [Owner single autonomous closure directive #6707985618](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6707985618), superseding internal permission loops only. Date: 2026-11-07. **Evidence status: not source-qualified; no new market GET.** Do not merge or mark Stage03 closed based on synthetic CI.

## Frozen operational N03 and independent prior mode

Implementation `src/zs_smart_gate/stage03_r2_n03_provisional.py` pins PM [V0.1 JSON SHA `ae1b645897866eed435ba29c585e75265b36b89e47d3f16cb360d94be4afb4d8`](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6707721496). The self-check recomputes SHA256 of canonical JSON at import. Strict 5m UP/DOWN pivot, 2-left + 2-right, excursion ≥0.5 ATR14_prev at first onset, H20/H48; **TRUE** only at second right candle's **actual available_at**, FALSE only for fully observed, no-pivot-as-of or expired episode, UNKNOWN on missing/late/conflicted/overlapping episode or unapproved mode/clock. This is an operational completion *proxy*, not a theoretical maximum/full trend, frozen Setup v1.1, or a PRE_MOVE prediction. **It cannot contribute to normalized scientific score or signal production.**

Provisional `ZS03_PRIOR_CONFIRMED_4H_PIVOT_MODE / V0_1_OPS_CANDIDATE_NO_REAL_PIT` is computed from 32 typed, continuous, available **before parent-open** 4h bars, with 2 confirmed strict highs and lows. Rising HH+HL implies uptrend, falling LH+LL implies downtrend; `CONTINUATION` if prior structure follows direction and `REVERSAL` otherwise; mixed/missing/ties are unavailable. It fingerprints the exact bars, their receipts and confirmed pivot IDs and never consumes N10 or later post-parent data. Synthetic tests prove causality of this *candidate rule*; authentic pre-open receipt still absent.

## Original-source rights/clock gate — evaluated, not bypassed

- [Official Binance Spot market-data-only docs](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md) list public, unauthenticated `https://data-api.binance.vision` GET endpoints for `/api/v3/exchangeInfo`, `/api/v3/klines`, `/api/v3/ticker/bookTicker`, `/api/v3/ticker/24hr`. [REST general info](https://developers.binance.com/en/docs/products/spot/rest-api) identifies the public market-data service; **technical public access is not a certificate of historical provenance, lawful retention, or clock correctness**.
- [Spot terms](https://developers.binance.com/en/docs/products/spot/PROD-TERMS-OF-USE) explicitly defer to Binance product terms; the [Binance Vision historical Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md) restrict covered archival dataset use to non-commercial domains unless specially licensed. Historical Vision archive rights must **not** be silently transferred to real-time Spot REST retention/commercial deployment. This assessment is a technical licensing boundary, not a substitute for legal review or a commercial data license.
- Source-capture path endorsed by Owner in [proposal #6707721496](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6707721496): at most **10 BTCUSDT read-only GET in 2 phases** (4 pre-parent: symbol/4h/1d/1w; 6 post-parent: 5m/30m/1h/4h/bookTicker/ticker24), no retries, no credentials, no scheduler, no publishing. All sources must be genuinely closed and available as of the correct parent and decision; publisher time is `PUBLISHER_TIME_UNKNOWN` if not in payload. `ticker24.openTime/closeTime` describe the rolling window; they are NOT independent proof of publisher/receipt time. Two snapshots are non-atomic.
- Actual **independent UTC clock/witness** and its conservative event-specific uncertainty interval (`< 1.5s`) must be demonstrably available in the exact runtime before any claimed source-qualified test. A local `datetime.now()`, GitHub job logs, file mtime, serverTime, or synthetic witness is NOT independent proof. An NTP/NTS/PHC validated source plus proof of offset/error/monotonic reception and attributable receipt hashing would be required. Neither an owner Windows host nor such event-specific independent clock records are connected to this coding environment at this point.
- **Hard stop for scientific original-source claim:** no executed original prospective 4h pre-open mode receipt, separately evidenced book/ticker24 requests, real 18-week last-closed daily/weekly context receipt, independently attested clock, or independently approved retention scope. **No GET or raw capture has been made in this work**; do not manufacture them. No code path converts synthetic records into `REAL_SOURCE_VERIFIED` or `SCIENCE_PASS`.

## Required isolated evidence/negative tests (current status)

| Stage03 layer | Validated on synthetic | Not validated on original |
|---|---|---|
| N01/N02/N04/N05/N08/N09/N11 | accepted 007A/009A deterministic descriptive calculations | 2025 independent historical receipt/PIT |
| N03 | hash-locked operational predicate; UP/DOWN × both horizons, FALSE/expiry/tie/UNKNOWN and late-right-bar guards; never score | scientifically universal impulse identity, original causal input receipt |
| N06/N12 | separated bid/ask and rolling `USDT quoteVolume`, individual synthetic receipts/clock/as-of | original eligible bid/ask and ticker24 event timestamps and rights |
| N07 | 32×4h structure/ATR from previously accepted 009A, new pre-parent independently derived mode and fingerprint | actual 4h mode provenance before real parent open |
| N10 | accepted last-closed, 18-week required-context and synthetic availability guards; context-only | genuine original 1d/1w availability and 18-week receipts |
| Stage03→03A | 009A bridge plus provisional N03 diagnostics; source mismatch/fail closed, deterministic `RESEARCH_CANDIDATE/REJECTED` | **single fully source-qualified original E2E** |
| Quality/OOS/Forward/economics | **DEFERRED_FULL_SMART_GATE** by owner | deliberately not rerun as current Stage03 engineering proof |

No `N03` credit, `score`, `signal_id`, `publishable` or trading/Telegram/Stage05.

## Permanent E01–E22 register preserved

VERIFIED: **E01–E06, E17** (7). PARTIAL: **E07–E12, E16, E20, E21** (9). BLOCKED: **E13–E15, E18–E19, E22** (6). `E13/E14` are historical PIT limitations, `E18/E19` (and predictive parts of E10/E12/E16) explicitly **DEFERRED_FULL_SMART_GATE**, never converted to VERIFIED. Scientific Stage03 source/functional hard gates (E11/E15/E20/N07/N10/source E2E) are **not** deferrable. [Detailed accepted original register](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6689623230).

```text
STAGE03 — VERIFIED ACCEPTANCE EVIDENCE
███████░░░░░░░░░░░░░░░ 31.8% (7/22)
VERIFIED 7 | PARTIAL 9 | BLOCKED 6 | DELTA +0.0 pp
STATUS STAGE03_OPEN / ORIGINAL_SOURCE_PIT_BLOCKED / NO_MERGE
```

**Precise external prerequisite:** one genuinely lawful event-specific *prospective original source* capture with 4h prior mode evidence and independently bounded UTC witness/immutable receipt, then source-qualified Stage03→03A research-only E2E and formal acceptance. Without that independent proof the Owner's allowed hard-stop exception applies; it cannot be resolved by another offline test or by deciding that metadata is real.
