# ORDER 006 — market-wide bidirectional research acceptance

**Disposition — ENGINEERING IMPLEMENTED / MARKET_COVERAGE_PARTIAL / QV1_REAL_POLICY_BLOCKED / LIVE_E2E_NOT_PROVEN.**

Authority is [PR71 Order006](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/71#issuecomment-6969816188) and [Issue51 dispatch](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6969824954). Re-fetched main was ad949a595814385dc70572a860b0539aa15d7d12. Base PR head c040758c3bb017f58c0f6f8a28b34ab36f671051 and all Order005 evidence remain preserved. Frozen Setup021, historical UP qualification and prior science registries remain byte-identical to that base.

## Implemented contract

- **Inventory** — dynamic exchangeInfo plus matching public 24h ticker and book. Every returned pair retains base/quote, Spot/trading status, availability, source digest, eligible/excluded status and explicit reasons. Non-USDT quotes carry UNSUPPORTED_QUOTE_POLICY. Missing or future/stale ticker/book data cannot become eligibility. Source inventory, supported eligible scope and evaluated pairs have separate counts. There is no popularity whitelist. An inventory resource guard of 20,000 returned instruments fails closed.
- **Fair scan** — SQLite transactional reservation and durable rotation shared by explicit foreground chunks. At most four supplied pairs per research chunk, and two per live invocation. Cursor advances across the entire dynamically eligible universe, including across new snapshots. Global pair/boundary reservations prevent duplication across different snapshots. Interrupted or uncertain reservations remain incomplete and are never silently repeated. Continue other pairs after restart; reacquire failed pairs on a later boundary with fresh inputs. Snapshot and result hashes are verified on read. This guarantees queue fairness when valid clock/source/budget permit work; it does not guarantee that a cold REST scan can cover every pair within one 90-second boundary window.
- **Safety bounds** — maximum 11 GET attempts, declared weight 140, observed minute headroom guard 200, 110-second source deadline and 120-second Windows process-tree watchdog. Maximum 16 MiB per response and 32 MiB cumulative response bytes. No redirect, proxy, automatic retry, credentials, paid service, delivery or scheduler. Reservations and response metadata are flushed before progression.
- **UP/DOWN research contracts** — separate versioned hypotheses in MARKETWIDE_DIRECTIONAL_RESEARCH_V1. UP tests close above preceding 20 highs and an up-close. DOWN tests close below preceding 20 lows and a down-close. Both use quote volume at least 1.20 times preceding 20-bar mean and a false-to-true transition. These are explicitly unapproved DEVELOPMENT HYPOTHESES. Neither direction has a real scientific policy record. Detector, hypothesis, source and input fingerprints are in each result.
- **Equal-quality joins** — exactly 22 closed consecutive 5m bars permit both previous/current predicates. Six constituents reconcile exactly against their 30m OHLC and base/quote volume. Causal closed 1h/4h contexts, exact symbol/request/anchor binding, eligible source snapshot and freshness checks apply identically. Missing, forming, late, gapped, tampered or inconsistent input becomes DATA_INVALID. Unverified clock becomes QUALIFICATION_BLOCKED. Valid positives remain CANDIDATE_SHADOW_ONLY. Both directions have stable distinct research event IDs and signed analytical return conventions. No production sig-ID, alert or short-selling authority exists.
- **Coverage** — counts include discovered, active, eligible, exclusion reasons, queued, attempted, source-validated, directionally evaluated, per-direction no-trigger/candidates/invalid/blocked, unscanned symbols, paused/interrupted, stale/invalid and percentage. Exclusion counts are non-exclusive. A full valid detector inventory with no trigger is distinct from incomplete coverage and the still-blocked real qualification path. Snapshot-bound reports never accumulate different boundaries into a false full-market pass.

## Windows evidence

Tested final implementation HEAD **43b864eb9b5bbf3f706a28904633a0426f26fc96**, TREE **3e8624d9ba3d4ffede1bf9072bf63b7c1b7339c7**. Windows 11 Pro, Python 3.12.10, existing D: staged optional dependencies.

**820 tests PASS**, zero failures/errors/skips, EXIT 0. This preserves the prior 790 baseline and adds 30 tests. Both mixed-market fixture funnels cover five pairs through restartable chunks. In the bull fixture there are three UP and one DOWN shadow candidates. In the bear fixture there are one UP and three DOWN shadow candidates. The sideways pair has no trigger. These are synthetic positive controls with zero delivery. Additional tests exercise equal-high/low, transition persistence, low/zero volume, missing/stale/future/context/gap/repaint/hash/symbol faults, invalid market, unknown clock, request/deadline/quota/timeout, concurrent claims, cross-snapshot dedup, corruption and restart.

See [acceptance receipts](windows/order006/acceptance-tests.stderr.txt), [controls](windows/order006/controls.json), [recorded replay](windows/order006/recorded-replay.json) and [file hashes](windows/order006/SHA256SUMS). Earlier full-suite 817 and 819 passes and the source-size stop are retained as historical iterations. Development corrected fixture UTC formatting and a test-only unclosed SQLite connection before final acceptance. No accepted live Telegram tests were repeated.

### Authentic recorded source replay

The pinned two-asset historical capture SHA 8aee74b4d185cdb8e36167ba16f0bb774d13232062e9f20360c84c23dee50ddb independently replays its original R0/R1/R2 results for BNBUSDT/BTCUSDT. Its four-pair inventory also includes ETHUSDT/SOLUSDT without candle captures. The two captured assets contain only six 5m bars each. All four attempted new directional evaluations truthfully return DATA_INVALID / INSUFFICIENT_HISTORY. Their original accepted reconciliation remains intact.

A separate pinned BTCUSDT 22-bar capture d2221b6b7849bff258a50367d9fef1507e31e17f9e67aedd30d30309fccaeccb verifies joined inputs, source receipts and recorded conditional timing. Both new directional paths return NO_TRIGGER. Its historical request records omitted the implicit symbol parameter; the replay explicitly labels LEGACY_IMPLICIT_SYMBOL_IN_PINNED_SOURCE_MANIFEST. This is weaker than the new explicit per-request symbol binding. No historical receipt was changed. No fully valid multi-asset 22-bar directional dataset or genuine live candidate is claimed.

### Bounded live source observations — 18 November 2026

Two separate foreground invocations made **two actual public GETs total**, estimated weight 40.

1. At 05:55:04–05:55:11 UTC, the first unfiltered exchangeInfo hit the 16 MiB body guard at 16,777,217 bytes. It also reported minute weight 380. The truncated bytes were not decoded or accepted as a full inventory.
2. After the payload fix, at 05:56:32–05:56:36 UTC, exchangeInfo with showPermissionSets=false returned a complete 6,784,941-byte JSON response. That documented parameter omits permission-set details and does not filter instruments. The observed minute weight 540 exceeded guard 200, so no ticker, book or candle requests followed. No additional live retries were performed.

The complete response was SHA-verified locally and decoded offline without further requests. It returned **3,743 instruments**, **3,703 Spot-enabled**, **1,373 active Spot pairs**, including **518 active USDT** pairs. All 3,743 derived per-pair identities/reasons are published in [discovery metadata](windows/order006/discovery-readback.json). There are 2,968 returned non-USDT instruments with explicit unsupported-quote reasons; these counts include inactive instruments. The actual eligible supported count remains NOT_ESTABLISHED without ticker/book liquidity. **Actually evaluated live pairs = 0.** This is discovery evidence only.

The raw complete-response SHA is 985b2f8dca6fc0fa5b14f2c4954c5678ee82639a984bca9ead273024fb4677fa. Raw live bodies stay on owner D: as required by this order. GitHub retains derived metadata, exact source hashes, timestamps, request parameters, quotas and stop results. Independent byte-for-byte regeneration of this particular live response requires those owner-local bytes; GitHub-only reproduction covers the published historical replay and deterministic controls. Windows clock was not remeasured in either quota/size-stopped invocation. Order005 clock blockers remain unresolved.

## Acceptance matrix

| Gate | Result |
| --- | --- |
| SCANNER_HEALTH_PASS | PASS for deterministic source admission, complete supplied inventory, cursor and negative controls |
| UP_DETECTOR_ENGINEERING_PASS | PASS for new research hypothesis and pinned BTC no-trigger replay |
| DOWN_DETECTOR_ENGINEERING_PASS | PASS for new research hypothesis and pinned BTC no-trigger replay |
| MARKET_COVERAGE_VERIFIED | Fixture supplied inventories only; actual market coverage PARTIAL, zero live directional evaluation |
| QV1_REAL_POLICY_BLOCKED | Both directions lack independently accepted scientific policy and sufficient real calibration evidence |
| LIVE_E2E_NOT_PROVEN | No qualified live signal or external delivery in this package |

| Stage | Current scope |
| --- | --- |
| 00 | Standing public-read and technical stop controls exercised |
| 01 | Complete returned instrument discovery observed; liquidity eligibility and candle scan incomplete |
| 02 | Versioned UP/DOWN research detectors implemented; frozen baseline preserved |
| 03 | Symmetric research admission implemented; real qualification and multi-asset 22-bar evidence blocked |
| 04 | New research cursor/result durability, hashing, restart and dedup tested |
| 05 | No new external Telegram effects; prior accepted scope retained |
| 06 | Directional analytical return convention tested; SQL and genuine live outcome deferred |
| 07–12 | Prior bounded engineering scopes preserved, regression suite passed; no new scientific acceptance |
| 13 | Bounded foreground capture/watchdog retained; real operating clock, full coverage, qualified cycle and soak pending |

## Reproduction and remaining decisions

On Windows set PYTHONPATH=src plus the existing D: optional-dependency staging directory described in NTS_QV1_002.md, and TEMP/TMP to D:. Use Python 3.12.10. Commands are in [commands](windows/order006/commands.txt).

A fresh read-only invocation can continue only with genuine quota headroom. The collector must additionally pass the independently adopted operational clock policy and fresh boundary checks before requesting a candle chunk. These guards were not relaxed to force market coverage.

Independent scientific review must freeze separate UP/DOWN criteria, context/liquidity normalization, spread/fee/slippage stress, horizon and outcome rules, causal data/witness eligibility, clustered/overlap-aware DEV/OOS/forward evaluation and acceptance thresholds. Non-USDT support additionally needs an approved causal conversion path to a common liquidity/cost unit, quote-source freshness and spread normalization. The current hypothesis supplies testable engineering behavior, not proven edge.

No merge, trading, Telegram send, operational archive write, SQL provisioning or unattended operation. PM owns MASTER/README edits.
