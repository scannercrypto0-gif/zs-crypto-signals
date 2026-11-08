# ZS03 — prospective 30m fast-track reuse of an original PRE (non-closing research)

**Scope:** Owner P0 execution order in Issue #25, existing PR #39. No new approval cycle; no historic backfill, no Stage05, no simulated qualified signal, no merge until independent full scientific acceptance.

## Why a fast-track is possible
The owner actually captured a 4h PRE receipt on 2026-11-08 before `08:00:00Z`. That timestamp is also an approved 30m opening. The PRE's source-received records can prove *prospective as-of* for the 30m parent **only after** all file SHA, NTP per-request uncertainty upper intervals, expected 4 original GET identity, pre-08:00 time, sufficient 4h/weekly warmup, symbol and rights scope gates pass. Original PRE is read-only, never re-created. No new pre-event data is fabricated.

- QUICK30 30m parent: `2026-11-08T08:00:00Z`→`08:30:00Z` (Saudi 11:00→11:30).
- QUICK30 POST authorized window: `08:30:02Z` to **before** `08:40:00Z` (Saudi 11:30:02→before 11:40).
- Exactly four bounded, one-attempt, read-only public BTCUSDT GETs during QUICK30 POST: 5m 80, 30m 22, bookTicker, rolling 24h ticker. Each request has before/after independent public unauthenticated NTP reference brackets. Response raw SHA, selected values and receipt journal, no raw HTTP body retained.
- Original 4h POST file `zs03-20261108T0800Z-post.json` is **not modified**; quick path output is `zs03-20261108T0800Z-quick30-post.json` and an offline `-quick30-e2e.json`.
- Real 03A 30m/6x5m reconciliation, 21x5m core, actual decision witnessed at QUICK30 POST, quote/spot/book validation. All original source windows; no relabelling synthetic.
- Fail-closed time/rights/source/order/market checks, and exclusive file create. A failed QUICK30 POST **must not be retried for the same event**. PRECHECK alone makes ZERO market GETs.
- A successful quick research E2E **does not scientifically close Stage03**; accepted E2E is just one independent piece of 22. Full real R2 N01–N12 scientific qualification, authentic publisher timestamp and full legal data rights still require external independent review.

## One immediate Windows precheck
At `D:\ZS Crypto Signals Latest Version` on correct clean PR39 branch, in regular PowerShell:

```powershell
git fetch origin stage03-r2-offline-dev-candidate-sd23
git merge --ff-only FETCH_HEAD
git rev-parse HEAD
$env:PYTHONPATH = 'D:\ZS Crypto Signals Latest Version\src'
py -3.12 -m unittest discover -s tests -p "test_stage03_field_quick30.py" -v
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
& '.\research\order025\run-stage03-quick30.ps1' -Phase precheck -ParentOpenUtc '2026-11-08T08:00:00Z'
```

**If tests or PRECHECK fail, DO NOT RUN POST.** All source evidence remains on the local D: drive. In the first new CI run on commit `e87b202633c2a022dc13b281ef0b348d8ab6bc0f`, all 5 Actions jobs were concluded failure **before steps executed**, and logs were inaccessible (404 blob). Do not claim code CI pass until steps actually execute; fallback is independent local targeted tests before real capture. Prior accepted main/PR CI is not overwritten by this unverified new head.

## Manual QUICK30 POST (NOT NOW, only within its actual window)
```powershell
& '.\research\order025\run-stage03-quick30.ps1' -Phase post -ParentOpenUtc '2026-11-08T08:00:00Z'
```
Immediately afterwards, offline:
```powershell
& '.\research\order025\run-stage03-quick30.ps1' -Phase review -ParentOpenUtc '2026-11-08T08:00:00Z'
```

Only share sanitized console status and SHA, no private raw or selected original market values publicly. No normal 4h POST attempt until original approved 15:00 window, if still needed and scientifically justified.

STATUS: `QUICK30_CODE_DELIVERED / SOURCE_PRE_EXISTS_OPERATOR_REPORTED / NEW_CODE_CI_INFRA_BLOCKED_NO_STEPS / LOCAL_TARGETED_TESTS_PENDING / REAL_QUICK_POST_NOT_EXECUTED / STAGE03_OPEN / STAGE05_FULL_HOLD`.
