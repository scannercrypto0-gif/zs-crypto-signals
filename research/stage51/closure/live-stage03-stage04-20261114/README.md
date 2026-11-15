# Stage03 → Stage04 live acceptance — 2026-11-14

**MATCH for the authorized one-symbol live research and Windows journal path.** The BTCUSDT candle closed at 07:30 UTC (10:30 Riyadh). Windows ran code `fcb91d106d51386d1e17265425fba6eb5399d395`, tree `c7f596da397cf30a857c6701a64a83ad875d4692`. The original acceptance report remains historical.

| Check | Result | Evidence |
|---|---|---|
| Public Binance Spot capture | 7 GETs, one symbol, no account keys | [Market receipts](market-receipts.json) |
| Exact 30m/six 5m reconciliation, causal 1h/4h and liquidity | PASS | [Capture](qualification.json) |
| Netnod recorded conditional clock intervals | Four samples, availability 1.235751 s, decision 0.224783 s, causal gap 0.261474 s | [Clock summary](clock-summary.json), [markers](capture-markers.json) |
| R0/R1/R2 decision | POLICY_HOLD / UNKNOWN, research-only, no signal or delivery. The legacy 5m Setup diagnostic returned NO_BREAKOUT. | [Journal write](stage04-write.json) |
| Windows custody | Idempotent second insertion, exactly one row, SQLite integrity verified. Fresh Python process reopened and matched the payload. | [Write](stage04-write.json), [reopen](stage04-reopen.json) |
| Focused Windows tests | 12 passed | [Raw test output](tests.stderr.txt) |

Capture SHA256 `d2221b6b7849bff258a50367d9fef1507e31e17f9e67aedd30d30309fccaeccb`. Canonical journal record SHA256 `fa48a37cc35203b21e6bd3ac241eb34e8f81a5a6ab081bf60c7440e1c972d274`.

The remaining pre-Stage06 item in the owner's narrowed scope is independently encrypted external Stage04 backup and recovery. Telegram was outside this test. No production enablement, trading, merge or Stage06 start.
