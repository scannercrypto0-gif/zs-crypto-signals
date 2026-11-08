# «ZS03 P0» — B1–B4 scoped integration and calculation audit (2026-11-08)

Authority: [PM consolidated execution #6719515692](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6719515692), Owner component-calculation-first #6706564402 and corrected #6706573034. This is **not** scientific closure or a merge approval.

## Repository baseline and exact code lineage

- `main` reviewed: `3260a0ef174a27dfff2b57cc3c4501dca60ddc71` («MASTER v1.37»).
- Existing «PR #39» prior to this continuation: `e376bb56e6534ade5239fc100469f49cc3c0d06f`.
- Three scoped engineering commits on the **same** PR39 branch:
  1. `ede75ac25a6689f90a1b90e6c32958dbcd89143c` — reject cross-source context for N05/N07/N10, three directed regression cases.
  2. `9558681ceaaae9f889d62408bddb63b7356eac25` — 1d/1w UTC boundary enforcement and pure 24hr base-vs-quote-volume packet selector, four focused tests.
  3. `5e30f8f729b68edbfad34c0eabe485f9e3ede2f7` — reject mixed-source/non-5m impulse traces and stale independently prior 4h mode, two negative test cases.
- No `README.md`, `ZS_SMART_GATE_MASTER.md`, frozen setup, `main`, live collector or old owner evidence was edited.

## B1 — real per-feature disposition, no blind stacked merges

| PR / exact original HEAD | Distinct feature/path | Compared against main and current branch | Disposition / transfer decision |
|---|---|---|---|
| #27 `e19531c...` | `stage03_science_pilot.py`, `stage03_science_expanded.py`: retrospective ECDF and predictive calibration | Main has newer source-pinned `ORDER022/025`, PR39 has component formulas; old model fitting is not a needed N01–N12 input | `SAFE_DORMANT_LEGACY`; 0 files transferred |
| #28 `0f8f28d...` | `stage03_source_acceptance.py` requires original BTC+ETH 2025-01–07 historical document set; `stage03_source_clock.py` NTP parsing; `stage03_bounded_inference.py` old outcome analysis | 2025 source acceptance cannot certify owner 2026 QUICK30; PR39 has dedicated fail-closed field clock; statistical edge deferred | `SAFE_DORMANT_LEGACY / EXTERNAL_BLOCKED`; 0 transferred |
| #29 `18cc623...` | historical GitHub custody `custody_restore.py`, `custody_aggregate.py`, changed `evidence_journal.py` and `stage04_evidence_packet.py` | Main already includes baseline journal, adapter, stage04 packet; old changes would introduce separate historical storage/dependency and are not direct Stage03 arithmetic | `ALREADY_IN_MAIN` baseline only; extra historical changes `SAFE_DORMANT_LEGACY/CONFLICTING`; 0 transferred |
| #30 `2f4c626...` | `prospective_causality_v2.py`, `clock017.py`, `integrated_research016/018.py`, `manual_alert019.py` | Older receiver/source attestation remains nonbinding for current original event; alert path must not activate during Stage05 hold | `SAFE_DORMANT_LEGACY`; any live alert activation `OBSOLETE/CONFLICTING`; 0 transferred |
| #31 `fe556ae...` | original recovered `pilot020*.py`, `run-020-once.py`, 020 preflight Windows | Published in GitHub PR31, not missing. Original prospective 2026-11-05 window expired; storage/rights/host preflight not proven for a new event | `SAFE_DORMANT_LEGACY / EXTERNAL_BLOCKED`; 0 transferred |
| #39 | current synthetic-only R2 and owner-reported bounded original 30m→03A research | Functional code and accepted old tests retained; 9 new negative arithmetic/source boundary tests added to same branch | `CURRENTLY_NEEDED_AND_ACCEPTED_WITH_LIMITS`; source updates implemented; NO merge yet |
| #40 `722347d...` | separate synthetic custody restore and single old authenticated NTS sample | Separate clock sample is not event-specific; no source-qualified real R2 bridge established; previous PM review says NO_MERGE | `CURRENTLY_NEEDED_RESEARCH_READINESS`, remain independent; 0 transferred |
| #43 `bbd02b4...` | MASTER/README governance only | SD role is expressly barred from editing these | `PM_ONLY`; 0 transferred |

The chain `#31 → #30 → #29 → #28` is stacked. «PRs #34–#38» were merged on `main` previously and are not duplicated. File-name overlap with main does not prove old optional contents are byte-identical. **No old PR was closed or merged**: an earlier successful CI is not an approval for an incompatible stale dependency.

## B2 — component truth table: defined / source / code / reference / functional / blocker

| Normalizer | Defined and required original source | Current calculation and independent reference evidence | Actual remaining blocker |
|---|---|---|---|
| N01 | closed 30m OHLCV | `close_parts` and weighted strong close; previous synthetic checks; owner QUICK30 30m→03A only | Original full-R2 source qualification not independently verified |
| N02 | six closed contiguous 5m OHLCV | `path_parts`, parent-child equality, prior synthetic arithmetic | Independent complete real-R2 receipts/timing |
| N03 | 5m onset + 14-bar prior ATR + independently specified completed impulse | `onset_timing`, provisional V0.1, 45-bar trace; new 5m/source consistency negatives; no false scientific approval | `FULL_IMPULSE` definition and original trace not independently approved |
| N04 | child `quote_volume` plus preceding 20-bar baseline | `volume_continuity`, isolated-spike suppression; synthetic reference | Original quote-volume provenance and source timing |
| N05 | closed and as-of 1h + 4h contexts | `prior_range_alignment`; new cross-source hard rejection | Original context snapshots and receipts |
| N06 | separate public book bid/ask + rolling 24h `quoteVolume USDT` | `liquidity`; explicit pure adapter reads raw `volume` as base and `quoteVolume` as quote without conversion; independent Decimal reference score `0.5001499250374812593703148426` for 100/100.1/20m | Real book/24h causal receipts and licensing/clock authority |
| N07 | prior 4h confirmed 2+2 pivots, BOS/CHoCH, independent prior mode | `structure`, `derive_prior_mode_from_4h`; added cross-feed and >8h mode-staleness guards | Real confirmed source and valid original mode chronology |
| N08 | closed 4h OHLCV | `close_parts` 4h weighting; synthetic reference | Original full 4h POST/real R2 qualification unavailable |
| N09 | four contiguous 1h children | `path_parts` + exact parent/child aggregation; synthetic reference | Original Swing child source/clock coverage |
| N10 | prior closed 1d/1w context + previous ATR, independent mode | `context_movement`; new Monday 00:00 weekly/midnight daily UTC hard guards and tests | Original 18-week history and qualified mode/source |
| N11 | previous 4h ATR14 + quote volume | `MOMENTUM_VOLUME`, conservative missing/zero handling | Original 4h quote volume and independently qualified ATR baseline |
| N12 | Swing book + rolling 24h quote turnover | Same `liquidity` with explicit base/quote distinction; numeric reference shared | Real separately timed book/ticker receipts and clock/license |

Baseline frozen «Setup v1.1», existing deterministic research identity and 03A readiness are reused, **not rewritten**. No `score_v2` promotion or production `signal_id` is called. Previous owner QUICK30 `REAL_30M_03A_E2E=PASS` remains `OWNER_REPORTED`, `RESEARCH_CANDIDATE`; private raw bytes and publisher UTC/rights are not independently accepted. No predictive OOS/Forward/edge requirement applied prematurely.

## Focused test evidence and exact CI obstruction

- Newly authored directed regression functions: **9** (3 source, 4 base/quote/UTC, 2 N03/N07). They are on the PR39 branch; **the actual Python suite has NOT run successfully on this exact SHA**, so none is reported PASS.
- Independent offline arithmetic reference check for the candidate liquidity formula matches `0.5001499250374812593703148426`; this is a **hand/reference calculation**, not proof that the checked-out repository test executed.
- The owner previously reported 6/6 QUICK30 Windows tests PASS at older `bcb9a43...`; no rerun or new Binance GET authorized or made.
- At `5e30f8...` five GitHub Actions workflows concluded `failure` within seconds, before test steps: `42468178157` (025), `42468178145` (foundation), `42468178177` (field), `42468178153` (021), `42468178122` (R2). Preceding heads exhibited the same platform pattern.
- Observed API facts on earlier heads: runner name blank; `steps=[]` on Ubuntu+Windows; job logs 404 `BlobNotFound`; check-run annotation counts 1–2, but the authorized connector cannot retrieve annotation messages. This is `CI_PRE_RUNNER_EXECUTION_BLOCKED_CAUSE_NOT_VERIFIED`, **not** a proven Python test failure nor permission to bypass checks.
- One external possibility is Actions spending/payment/runner entitlement, documented in GitHub's troubleshooting guidance; **not verified for this account**. Requires owner-side private billing/invoice and full run annotation inspection. **No brute-force reruns**.

## B4 — disposition / owner progress / next actor

```text
main_before=3260a0ef174a27dfff2b57cc3c4501dca60ddc71
main_after=3260a0ef174a27dfff2b57cc3c4501dca60ddc71
PR39_DRAFT_OPEN_UNMERGED=true
NO_MAIN_MERGE / NO_STAGE05 / NO_MARKET_GET / NO_TRADING / NO_TELEGRAM
STAGE03_PROGRESS=███████░░░░░░░░░░░░░░░ 31.8% (7/22 VERIFIED)
VERIFIED=7 PARTIAL=9 BLOCKED=6 DELTA=+0.0pp
```

**Blocking reason for main merge:** current exact-head mandatory «CI» unable to start, plus «PM» independent code/source-science review and branch dependency acceptance not issued. A synthetic arithmetic fix is not a real publisher/rights PIT proof. The next single operational gate is to inspect the private job annotation and Actions billing/runner status once (no repo code changes needed), then execute **only the 9 new focused offline tests** on the exact checked-out PR39 SHA; keep Stage05 held. Next actor «SD Coding» for tests/CI diagnosis, «PM» for any qualifying independent review/merge and #43 governance.