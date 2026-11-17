# Order 005 — Windows Time, QV1 and signals engineering

**Disposition: PARTIAL / NOT_READY.** Windows 11 Python 3.12.10 executable code tested at `2fd55a2964d5419d58973d684089cc3a45ef2068`, tree `73caa3b055e4c482b6927a56e462ef5669df3e3d`. The evidence commit also supplies the missing hosted foundation test dependencies. Unchanged main baseline `ad949a595814385dc70572a860b0539aa15d7d12`.

## Gate receipts

| Gate | Evidence and disposition |
| --- | --- |
| 1 — Windows engineering | PASS for 790 offline tests, including a Windows Job Object timeout killing a stuck child and grandchild while an unrelated process survived, injected operator interruption returning 130, and exit-code passthrough. The initial base-Python run failed importing certifi. Re-run with the existing D: NTS staging dependencies passed. |
| 2 — Operational clock and source | CLOCK BLOCKED. Status and four Cloudflare stripchart samples succeeded. Source and configuration RPC both returned 2147942405. Fresh Spot run stopped at 3 public GETs, planned weight 23, minute header 203 against guard 200. The earlier quota stop and earlier 5/5 public readback remain preserved. No additional requests after this stop. |
| 3 — QV1 | Recorded BTCUSDT inputs and clock bracket hashes verified, Setup detector re-run, NO_TRIGGER / NO_BREAKOUT. Context/liquidity/reconciliation recorded research checks passed. Production remains QV1_POLICY_REVIEW_REQUIRED; no signal ID exists. Fresh ETHUSDT full QV1 capture was not completed. |
| 4 — routes/custody | Recorded research payload written once and independently reopened with exact SHA and one record. Injected fixture destinations cover loss of acknowledgement, reconciliation and duplicate prevention. Telegram A/B/C and operational archive readback have no new actual delivery evidence. SQL provisioning and live database testing deferred. |
| 5 — signals E2E | Authenticated recorded research and local custody replay PASS. Positive destination/outcome fixtures are separate test evidence; no common real qualified signal was generated, dispatched or evaluated. |
| 6 — daily operations | Watchdog/restart protections exercised in scoped tests. Stability soak and continuous workflow NOT_EVALUATED. |

| Stage | Acceptance under this order |
| --- | --- |
| 00 | Public/read-only and standalone Windows guards exercised. |
| 01 | Prior public Spot readback passed. Latest run quota-stopped after time and market discovery validation. |
| 02 | Existing detector recomputed on recorded BTCUSDT. |
| 03 | Recorded research replay passed; production qualification blocked. |
| 04 | Local research record integrity, restart and duplicate prevention passed. External operational archive deferred. |
| 05 | Fake adapters and delivery reconciliation tested; no Telegram calls. |
| 06 | Existing offline outcome components exercised by suite; real outcome and production SQL deferred. |
| 07–09 | Existing offline intraday, swing and profile regressions exercised by suite. |
| 10–11 | Existing offline futures and BTC context regressions exercised by suite. |
| 12 | Existing offline research regressions exercised; predictive performance NOT_EVALUATED. |
| 13 | Watchdog pass; active clock policy, qualified integrated cycle and soak blocked. |

## Operational time decision

The process has a medium integrity token with the Administrators SID marked deny-only. The service security descriptor and NtpServer registry configuration are readable and the configured NTP server agrees with status. Those observations do not establish the RPC access check or substitute for the failed live queries. Resolve with one elevated, read-only local check of `w32tm /query /source` and `w32tm /query /configuration`, retaining their exit codes. No elevation, service, registry or security setting was changed by this order.

Proposed `WINDOWS_TIME_OPERATIONAL_V1` requires four distinct observations of time.cloudflare.com, absolute offset and conditional uncertainty at most 0.5 s, sync age at most 600 s and wall/monotonic divergence plus sample spread at most 0.05 s. Observed absolute offset at most 1.688 ms, sync age 184.9 s and conditional proxy 70.9 ms in one short run. The proxy is Windows root dispersion + half root delay + half max measured probe RTT. One run supports a local baseline only. Asymmetric routing, independent probe path differences, holdover, and unauthenticated NTP constrain the inference. Before adoption, review measurements across normal runs, reconnect and sleep/wake, and freeze exact limits and the reviewed content hash. The policy pin is unset. Even accepted operational Windows Time would not certify independent cryptographic UTC.

## Qualification proposal for independent review

Reuse the existing detector and exact 30m-to-six-5m reconciliation. Require causal closed 1h/4h context, matching source and symbol, eligible Spot/USDT listing, timestamped book and rolling 24h quote volume from the same symbol, and independently accepted clock evidence. Record eligible no-trigger events, ineligible data and shadow detections separately. The replay manifest in the receipt pins joined market evidence and prints detector and evaluator hashes. The published historical BTC receipt contains the original seven Spot receipt entries; fresh full ETH collection and broad history remain unverified.

Freeze source, causal timestamps, event identity, eligible universe, baseline, fees/spread/slippage assumptions, outcome horizon, overlap exclusions and scientific acceptance criteria before OOS selection. Use chronological DEV/OOS partitions separated by at least the outcome horizon, event/time block inference for correlated symbols and overlapping labels, an untouched holdout, then prospective observation. Include spread/fee stress and coverage analysis, and publish negative and censored outcomes. Select N01 and context/liquidity thresholds only from a reviewed frozen DEV protocol; there are no adopted numeric research thresholds here and no real model edge/trade is claimed.

## Reproduction and CI

From the tested Windows code, set PYTHONPATH to `src` plus the D: staging dependencies listed in [NTS_QV1_002](NTS_QV1_002.md). Put TEMP/TMP on D:. Run `py -3.12 -m unittest discover -s tests -v`. For recorded replay, run `py -3.12 scripts/ops-qv1-recorded-replay.py research/stage51/closure/live-stage03-stage04-20261114/qualification.json d2221b6b7849bff258a50367d9fef1507e31e17f9e67aedd30d30309fccaeccb <fresh-D-directory>`. The live command used the clean tested code with `py -3.12 scripts/ops-spot-preflight.py --live-read-only --output <fresh-D-directory>`. See [checksums and raw sanitized receipts](windows/order005/SHA256SUMS). Raw live response bodies and original Windows command output stay on D:.

Prior hosted runs [44084348650](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/44084348650) and [44084348684](https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/44084348684) failed before test execution. Sampled Windows job annotation in each cites account payment or spending limit. Local Windows test results are independent of hosted status. No trading, external operational effects, scheduler, soak or merge.

