# ZS03 P0 owner Windows real field package — implementation and stop gates

**Authority:** Owner #6707985618; PM location clarification #6711956376; current PR #39. This document does not grant an external exchange license or declare scientific closure.

## Executable contents
- `src/zs_smart_gate/stage03_field_clock.py`: two independent public UDP NTP references (`time.cloudflare.com`, `time.google.com`), one query each, origin echo validation, leap/stratum checks, monotonic duration and conservative absolute UTC uncertainty (offset, RTT, server root delay/dispersion, margin). Public NTP is **unauthenticated** and never counts as cryptographic NTS proof.
- `stage03_windows_field_capture.py`: two manual phases, 4+6 fixed `BTCUSDT` public Spot read-only REST GETs, pre/post two-server NTP brackets per market request, no retry, independent source/arrival intervals, original payload SHA256 plus minimum selected fields **private local D:**, write-once per-event receipts and record SHA256. No Binance keys, account operations, Telegram, trading or scheduler.
- `stage03_windows_field_review.py`: strict original evidence integrity, source/time windows, rights receipt SHA, 4h prior context, 18w, 24h USDT quoteVolume, non-atomic book/ticker freshness and observed decision witness.
- `stage03_field_real_e2e.py`: read-only real-source replay via the **existing** Stage03A `assess_readiness`, real immutable candle windows, 4h⇔4×1h reconciliation, 21×5m core, research identity/decision. Does not relabel original data as synthetic or bypass synthetic-only R2 guards. Real N01–N12 qualification remains separate; no numeric score/signal ID.

## Rights and scientific honesty
Official public endpoint documentation: https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md . Review the currently applicable https://www.binance.com/en/about-legal/terms and any geographic restriction. Vision historical dataset license (https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md) is **not** automatically a live Spot REST commercial license. A documented maintainer clarification distinguishes `data-api.binance.vision` from `data.binance.vision`: https://github.com/binance/binance-public-data/issues/502 . Operator must review private noncommercial use/retention before attestation; if unclear STOP/no GET. Attestation is a factual operator statement, **not** provider legal authorization. Do not put raw or selected provider market data in public GitHub.

Observed local Windows clock ~60ms offset is not an independently bounded event clock by itself. Two independent NTP reference brackets may show `u<1.5s` under their measured protocol path; NTP is not authenticated, publisher timestamp is unknown, provider rights not independently certified, and original historical 2025 publisher/PIT evidence cannot be reconstructed. There is **no automatic full scientific PASS**. Only qualified, independently reviewed evidence may close mandatory E11/E15/E20 etc.

## Manual safe execution (PowerShell, normal user)
All commands run from `D:\ZS Crypto Signals Latest Version`. On first use, confirm exact checked-out PR39 SHA and clean tree. No reset/force.

```powershell
Set-Location -LiteralPath 'D:\ZS Crypto Signals Latest Version'
git fetch origin stage03-r2-offline-dev-candidate-sd23
git merge --ff-only FETCH_HEAD
git rev-parse HEAD
& '.\research\order025\run-stage03-field.ps1' -Phase clock
& '.\research\order025\run-stage03-field.ps1' -Phase rights
```

After reviewing terms, the rights phase asks for one exact phrase and creates a no-overwrite local document. For a *new future* 4h UTC parent open (00/04/08/12/16 UTC, never 20 UTC), use:

```powershell
$parent = 'YYYY-MM-DDTHH:00:00Z'
& '.\research\order025\run-stage03-field.ps1' -Phase pre -ParentOpenUtc $parent
& '.\research\order025\run-stage03-field.ps1' -Phase post -ParentOpenUtc $parent
& '.\research\order025\run-stage03-field.ps1' -Phase review -ParentOpenUtc $parent
```

**Timing is mandatory:** PRE only 20 minutes to 10 seconds *before* parent opens; POST only 2 seconds to 10 minutes after it closes, four hours later. Execute these commands at their different times, **not as one pasted multi-line block**. If phase fails, do not rerun same event (receipt file exists even on failure); use a future event only after reviewing stop reason. Source clock preflight may fail due to UDP123/DNS; do not weaken the witness gate. Review is offline and may run after both phase files exist. It writes to `_local_evidence\zs03-field\zs03-<tag>-real-e2e.json`.

Expected review: `NETWORK_UTC_BOUND_UNDER_1_5_S` where supported, `RESEARCH_CANDIDATE` or honest `REJECTED/INVALID` depending on market, `score=None`, `signal_id=None`, `publishable=false`. It cannot mark `STAGE03_CLOSED` automatically.

## Evidence handoff
Only return console status, PR SHA, local record SHA256 and independently reviewed redacted notes, not full market JSON or private host details. Code/CI remain on GitHub; owner private evidence stays on D:. The session with GitHub tools cannot remotely execute Windows commands or claim a real field run.

Progress: `STAGE03 7/22 VERIFIED =31.8%; 9 PARTIAL; 6 BLOCKED; DELTA=0.0pp`. Merge/postmerge only after full required scientific/source/E2E evidence and applicable repository review gates. `Stage05 FULL HOLD`.
