# ORDER-025 — DATA / PIT decision packet for owner (ONE consolidated approval step later)

**This document is a request for future choices, not a market authorization.**
Authority: [ORDER-025](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6656960128). Current engine base `05ced43dcfbc476a60030283004503945be82120` on MASTER v1.37.

## A. Use what we already have — cheapest, no new network (recommended NOW)

Original, owner-retained `010-B` study reportedly contains **12 Binance Vision Spot monthly 5m ZIPs** for `BTCUSDT` and `ETHUSDT` for **2025-01..06**, with original index, frozen manifest and SHA-256 proof. Owner reports 12/12 ZIPs verified, private report SHA `985abecf489ea23d1e46f9aace7152df8cf997cd94cce33dde440bdb34cea5ee`, 1588 admitted descriptive price patterns. Our execution context **does not have access to these private bytes**.

**Requested approval A1:** let the owner run the **read-only, offline independent verifier** on their own private data directory; send only a redacted verification JSON / counts/hashes to independent Audit. No private ZIPs, source timestamps or databases published to Git. The verifier checks original archive pinning, engine and contract hashes, all four counters, original event-list digests and SQLite restore using a separately implemented counter, **but shares the original archive CSV parser**; this is strong arithmetic corroboration, not wholly independent parser auditing or publication-time PIT.

Archive source: [official Binance public-data README](https://github.com/binance/binance-public-data/blob/master/README.md) confirms Spot files dated 2025 onward use **microsecond timestamps** and optional per-ZIP `.CHECKSUM`; archives can be corrected after publication. The SHA of the retained ZIP matches old owner manifest; absent CHECKSUM publication/receipt archive, do not label original publisher identity independently certified.

**Resource planning (not actual measured use):** approved ORDER022 implementation caps each ZIP at 12 MiB and expanded CSV at 32 MiB. Twelve ZIPs therefore cap at **144 MiB**, expanded CSV inspected one by one caps at **32 MiB per file**, while the combined 12 CSVs could reach **384 MiB** if materialized. Allow **at least 1 GiB private free working storage** for archive staging, hash/index, reports, SQLite DB and independent restore; actual usage must be measured, not assumed. **Incremental market download: zero.** No paid external service is necessary for this existing-data verification; owner local storage/compute costs are not measured.

**Legal use is a hard decision**: Binance Vision Dataset Terms (as published 2026-08-26) permit specified *noncommercial personal research* but exclude commercial use/signal resale absent a separate written enterprise agreement. Legal rights of previously downloaded files depend on terms applicable at original acquisition; keep original contract/date and do not assume grandfathering of later use. Do not put raw or licensed derived feeds in a public repository. See [official dataset terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md) and base Binance terms; consult legal/owner for future commercial scope.

## B. Historical additions — NOT AUTHORIZED, only if original source is absent or insufficient

Option B1: **one-time original-provider archive correction/reference check** of exactly BTCUSDT and ETHUSDT, Spot 5m, monthly January–June 2025, 12 ZIP and their 12 `.CHECKSUM` objects **ONLY**, plus documented update/replacement history. Use pre-specified exact URLs from official [binance-public-data README](https://github.com/binance/binance-public-data), immutable request ledger (URL, bytes, UTC receipt, published headers, SHA, checksum, correction notice), strict failure on mismatch. **No REST/WS/live stream.** Download quota/HTTP count and transfer budget must be measured and explicitly approved before a call; no fabricated exact ZIP sizes. This historical recovery **cannot** reconstruct known-at-2025 decision receipts or missing 2025 bid/ask/24h snapshots.

Option B2: if real historical PIT/full market-state proof is required, seek a **separately licensed institutional historical market-data provider** with symbol-specific contemporaneous bid/ask, 24h quote-volume snapshots, publisher timestamp plus independently recorded receipt/availability trace and explicit correction policy. Request a **metadata-only** quote/sample schema and rights first; price **UNKNOWN**, source completeness/coverage/PIT **UNKNOWN**. Do not accept advertised historical OHLCV as equivalent to original receipt. If no provable provider exists, mark `HISTORICAL_FULL_SETUP_NOT_PROVABLE`.

**Owner decision B:** do we permit a strictly bounded new historical acquisition for B1/B2 after reviewing provider rights, bytes/storage caps, API/request count, data fields and legal terms? **Default NO.**

## C. Prospective paper/shadow qualification — next scientific route (separate approval required)

Source candidate: official public market-only endpoints `data-api.binance.vision` (REST) and `data-stream.binance.vision` (WS), which support 5m closed klines, `bookTicker`, `ticker/24hr` and server time per [official market-only FAQ](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md) and [public WS docs](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md).

**Proposed narrow capture:** only `BTCUSDT`, `ETHUSDT` Spot; closed `5m` bars and their 20-bar warm-up; time-aligned bid+ask with sizes, 24h quote volume, exchange event/server times, complete source messages/header identity, receipt UTC + monotonic clock, clock offset and **independently assessed uncertainty**, availability and decision time. No keys/account endpoints/orders/trades; avoid future leakage. Freeze a versioned source-clock schema before launch. Local append-only journal/WAL with chained SHA256 and bounded retention; independent restore and fail-closed on duplicates, source outages, negative/future delay and stale data. **Hash chain alone does not prove unforgeable UTC or WORM**. Period length/packet rate/REST weight, latency caps, clock target and retention must be separately approved after reviewing the preflight measurements and terms. Do not assume real-time 24h snapshot existed at historic decision based on today's API.

**Owner decision C:** approve a **new, explicit**, bounded read-only source/capture plan for prospective independent evaluation, following final technical and licensing preflight? **Default NO**. Stage05 still FULL HOLD and no publishing.

## Minimum approvals to achieve genuine scientific closure (in dependency order)

1. **A1**: owner-private *read-only* reproduction receipt and independent Audit; clarify actual source rights and prohibited dissemination; no market access.
2. **D1–D5 sign-off**: settle four semantics, twelve group normalizers or explicitly defer V2 from simple v1.1 scope, primary outcome/estimand, costs, independent controls and N/power/multiplicity and untouched forward partition. Scientific standards not weakened; update contracts only in a new version after separate owner approval.
3. **Either B2** with credible actual time-valid historical state and publication/receipt documentation, **or C** prospective market observations with independently auditable clock. Without either, full-v1.1 PIT and complete eligibility remain unprovable.
4. Separate independent PM/Audit review of complete data/clock, code and effect/uncertainty, then **owner Stage03 scientific closure**; only after that could Stage05 become eligible for a *separate* activation decision.

**Milestone order (not a promise of completion time):**
`PRIVATE_SOURCE_REPRODUCTION → RIGHTS/SCIENCE_CONTRACT_SIGNOFF → APPROVED_DATA_OR_PROSPECTIVE_CAPTURE → UNTOUCHED_VALIDATION → INDEPENDENT_SCIENTIFIC_REVIEW → OWNER_DECISION`.

NO MARKET CALLS, NO PRODUCTION, NO TELEGRAM, NO TRADING, NO STAGE05 by creating or accepting this packet.
