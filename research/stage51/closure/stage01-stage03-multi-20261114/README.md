# Stage01 / Stage03 bounded live acceptance

**PASS — both stages MATCH in the owner-authorized multi-asset engineering scope.** The Windows run completed 11 public Binance Spot GETs under a 175-second process watchdog. The first GET to decision upper UTC bound was 11.923 seconds. The scanner evaluated the explicit four-asset pool (BNBUSDT, BTCUSDT, ETHUSDT, SOLUSDT); all passed existing eligibility rules. The existing deterministic offset-zero selection chose BNBUSDT and BTCUSDT. This evidence covers the bounded pool.

| Requirement | Code / check | Evidence | Status |
|---|---|---|---|
| Stage01 Spot listing, rolling 24h volume and book, eligible selection | existing scanner, shared symbol-scoped endpoints | [capture](capture.json), [stdout](stdout.txt) | MATCH |
| Stage03 each symbol has closed 30m, six 5m, 1h and 4h, exact OHLC/base/quote reconciliation | per-symbol request binding, existing R1 and exact reconciliation | [result](result.json) | MATCH |
| Causal timing and manifests | Netnod conditional authenticated UTC bounds, 1.196570 s availability and 0.241796 s decision, separated by 0.268364 s | [capture](capture.json), [offline replay](replay.txt) | MATCH |
| Independent R0/R1/R2 outcomes | distinct event, manifest and feature hashes, POLICY_HOLD for both, no signal or publishability | [result](result.json) | MATCH |
| Fail closed and reproduce | 4 affected tests; swapped symbol request receipts, premature decision and invalid close rejected; byte-exact replay | [unittest](tests.stderr.txt), [checks](replay.txt) | PASS |

Code `105d57d099671c2f45631f73a55e6b5577cd0795`, tree `7dc7b20712fe27344ef95b17869ee4bf2a95dbc6`. Capture SHA-256 `8aee74b4d185cdb8e36167ba16f0bb774d13232062e9f20360c84c23dee50ddb`. Raw file checksums are in [SHA256SUMS](SHA256SUMS).

Stage01 and Stage03 no longer block Stage06 development in the owner's agreed bounded scope. Stage04 local continuity has its separate accepted evidence and Telegram is covered by the owner's prior confirmation. Predictive performance and production qualification remain deferred. No Telegram calls, private keys, trading, production activation, merge or Stage06 work.
