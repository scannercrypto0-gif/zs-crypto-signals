# P0 — Full Eligible-Market 24×7 Windows Operation: Owner Execution Direction

**Date:** 2026-11-21 (Asia/Riyadh)
**Authority:** Owner's explicit instruction in PM 1.14 conversation to prioritize actual 24-hour, all-market readiness.
**Order:** [Issue #51 — P0-OPS-FULL-MARKET-24H-001](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-7059836760).
**Status:** `ENGINEERING_AUTHORIZED / FULL_MARKET_LIVE_NOT_PROVEN / WINDOWS_24H_NOT_STARTED / NO_TRADING_AUTHORITY`.
**This document is a governance/acceptance contract, not a running service or approval to merge code.**

## Source-of-truth snapshot and prior acceptance

At this direction, `main=7b7bb0ebdf0bb601cf1f468c0146c784cb8e0a5f`, TREE `ac9b9fd8b0c7801183589b027cba1082d616f32b`; PR #74 merged at tested source `3e360d7471fa6d7270ededd77660392e80c8b250` and identical TREE. CLOCK74 accepted **91/91 offline Windows tests**, not a live full-market scan. Last live CLOCK73 on 2026-11-20: 45 historically eligible, 1/45 source-validated, AAVEUSDT both directions NO_TRIGGER, partial exit. Main limits: 11 GET, 140 estimated weight, two pairs, 90-second entry, 110-second capture and 120-second watchdog. The currently checked-in Windows release controller does NOT install an unattended schedule, and last live installed revision is not proven upgraded to CLOCK74.

## Owner priority and staged operating authority

- **P0:** complete all eligible Binance **Spot USDT** source-verified scanning throughout each declared 24-hour period on the owner Windows machine; recover safely from restart, transient network failure, timing issues, quota stalls and power outages without fabricating coverage.
- The owner directs engineering and a **controlled read-only 24-hour research soak**, but starting it is gated by real measured full-market feasibility, a safe least-privilege Windows service and verified stop/rollback. This direction does **not** waive the need for independent PM review and an owner approval of the **exact final merge head**.
- Public read-only market/time calls only under valid source/time/quota guardrails. No trading or keys, real Telegram sends, production external archive, SQL writes, elevated persistent scanner, or unreviewed spend. QV1/real UP and DOWN scientific validity must be decided separately before any production signal.
- Windows 11 / Python 3.12.10 / PowerShell 5.1 on `D:\ZS-SMART-GATE` is the operational and acceptance environment. GitHub is the authoritative repository for ALL permitted nonsecret Windows source, tests, docs, scripts and verifiable evidence. Publish safely screened evidence; never upload secrets/private raw responses without a custody decision.

## Coherent full-market definition

For each candidate 30-minute boundary B, a frozen eligible inventory I of size N forms a declared cohort. Inclusion/exclusion rules and `inventory_id` must be immutable for the boundary. Under the current four-frame cold REST design the *estimate* is `R(N)=3+4N` and `W(N)=104+8N`; the old N=45 suggests 183 GET / 464 estimated weight, NOT an executable limit or authorization. Actual endpoint weight, IP headroom, latency, request/response size and clock viability need measured evidence.

At final decision time D, verify for **each** eligible pair: four closed frames, 22 consecutive closed 5m bars when required, 30m reconciliation with six 5m bars, causally available 1h/4h, original payload hashes, and `as-of/available-at/received-at`. Reassess *all* inputs at D. `MARKET_COVERAGE_VERIFIED` is only justified for N/N valid pairs from the same inventory, boundary and causal decision, never from combining different boundary samples. Missing/late/unknown/stale inputs are `PARTIAL` or `BLOCKED` with reasons.

First candidate: versioned B1 REST budgets with atomic in-flight reservations, measured bounded concurrency, explicit earliest deadline, cumulative weight/bytes/requests, 429/418 safe backoff and durable uncertainty ledger. Do not blindly raise `MAX_REQUESTS` or reclassify partial. If B1 cannot meet a validated snapshot window, propose versioned B2 stream-backed closed-bar cache with reconnect, gaps, retention and PIT controls. Repeating B3 partial batches is NOT full-market acceptance. Preserve CLOCK74 valid 11th receipt and blocked 12th regression.

## Windows service and 24-hour validation contract

Deploy only reviewed exact SHA/TREE and retain `DISABLED` as default. Scanner must run with a least-privilege **nonadministrator** token; isolate a minimal time witness or equally reviewed clock evidence, never turn one-shot Administrator pilot into a persistent elevated task. Explicit, operator-initiated enablement is required after live/full-market acceptance and independent PM review. All service state, original evidence and rollback data remain on D:.

Implement and test: singleton lock; bounded retries/restarts with backoff/circuit breaker; watchdog; atomic journal and cursor; reconcile reception/commit uncertainty on restart; no duplicate reservations or signal events; heartbeat; disk/CPU/RAM/storage retention caps; operator `Status/Stop/Disable/Rollback/Restore`; reboot/network loss; owner-visible summary; source time, request IP quota and source checksum audit. A stop request or untrusted clock, stale data, HTTP 429/418, exhausted budget, corrupted receipts, stale cache or unknown state must degrade or stop safely. Never retry through bans or widen time windows silently.

**24-hour proof** should identify a measured start/end in UTC and Asia/Riyadh, actual continuous process/service uptime, and **288** planned 5m health slots in the day; if the selected full-market policy remains 30m, enumerate **48** eligible boundary opportunities with inventory and N/N/partial statuses individually. Record missing opportunities and downtime. A running process for 24h is not evidence of 48/48 full-market research coverage. The exact intended cadence and availability SLO must be explicit before testing; do not label a 24h experiment 100% ready if an agreed mandatory boundary fails.

## Independent acceptance gates and evidence

| Gate | PASS evidence | Otherwise |
| --- | --- | --- |
| G0 — Code/release | Exact GitHub head/tree, clean Windows checkout, impacted offline tests with original stdout/stderr, exits and SHA256, restore from GitHub | ENGINEERING_PENDING |
| G1 — Live full-market | Frozen I/N, same-B fully causal and fresh N/N pairs at final D, all four frames and raw original hash receipts, actual weight/latency | MARKET_COVERAGE_PARTIAL / BLOCKED |
| G2 — Runtime safety | Least-privilege time and worker, singleton, watchdog, failures, stop/disable, rollback, reboot recovery proven | RUNTIME_UNSAFE |
| G3 — 24h soak | 24h measured Windows read-only run, each intended 5m/30m opportunity enumerated, health/downtime/recovery, zero unauthorized effect | 24H_STABILITY_NOT_PROVEN |
| G4 — Science | Pre-registered real-source PIT DEV/OOS/forward for UP/DOWN QV1, uncertainty/cost/baselines and independent review | SCIENCE_NOT_QUALIFIED |
| G5 — Dispatch | Separate explicit owner authorization, real Telegram A/B/C ACK/dedup/isolation and 05C human inbound, archive readback/restore | LIVE_E2E_NOT_PROVEN |
| G6 — Trading | Not within project; no orders/transfers/keys | TRADING_AUTHORITY_NONE |

G1/G2/G3 enable evidence of a **read-only marketwide 24×7 research service** only; G4 and G5 are required for trustworthy real production signals/delivery. SQL deferred by owner. Never claim 100% launch readiness from G0–G3 alone.

## Mandatory delivery route

1. SD Coding starts from fresh main, ONE focused Draft implementation PR (code, deterministic failure tests, disabled safe install, operator runbook, real-source measurement plan); do not edit MASTER/README root files.
2. Pin exact final implementation HEAD/TREE; owner Windows performs targeted offline tests and bounded live marketwide acceptance, preserving D: raw logs and SHA256. Reuse accepted CLOCK74 91/91 evidence unless affected paths require rerun.
3. PM independently reviews code and privacy-screened GitHub-synchronized originals; owner separately authorizes exact-head merge/deploy. Remote restore verifies the tested code and permitted evidence hashes.
4. Only after G1/G2: start controlled **read-only 24h soak** using the reviewed installed release, with hourly snapshots and post-run acceptance report. If any mandatory gate fails, stop safely, retain durable evidence and return a precise blocker and corrective PR rather than claiming progress.
5. Stage QV1 science and delivery E2E as separately owned workstreams, not as excuses to call mock signals production.

This order is accompanied by the owner instruction recorded on Issue #51. No step above represents a claim that the current Windows machine is running or that all-market coverage was already achieved.

## Owner latest override — 2026-11-21: no per-run approval and maximum safe dynamic capacity

The newer standing owner directive [Issue #51 comment 7061389384](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-7061389384) supersedes references in earlier sections of this document requiring *fresh owner permission* for each public-read-only request, live research boundary, finite 24h nontrading soak, and routine read-only reviewed release. After PM independent technical review, original Windows pinned tests, proved stop/recovery and GitHub branch-rule compliance, SD Coding/Codex may automatically perform these actions under standing permission; PM does not have to solicit ceremonial owner approval repeatedly. This does not eliminate evidence gates or permit unsafe/external side effects. It does not itself merge PR76 or start Windows.

Dynamic rate control replaces unnecessary caps: target up to 98.333% of **measured available legal quota**, illustrated as 5900/6000 REQUEST_WEIGHT points/minute (not request count), reduced by shared-IP observed use, in-flight reservations, all enforceable interval limits and an adaptive uncertainty margin. Never exceed source limits or Retry-After, provoke bans, remove clock/data causal validity, or waste quota when the market snapshot has already completed. PR76 currently still hardcodes 5500 maximum, so implementing this policy requires new source, tests and Windows evidence; no acceptance claim can rely on its old 41/41 tests for modified code.

The PR76 normal-user protected-registry clock profile passed owner-reported real witnesses and replaces the obsolete elevated-only limitation after an independent equivalence assessment, not a new owner permit. The prohibition on trading, transfers, live Telegram/SQL writes and unapproved spending remains. All actual nontrading operation must pass restart/rollback safety checks and continuously report partial/blocked outcomes truthfully.
