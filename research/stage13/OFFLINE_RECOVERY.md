# Offline operational recovery before the Windows control screen

This increment adds a bounded, operator-invoked recovery page to the Stage13 synthetic controller. It discovers locally committed signal records, validates their stored receipts and replays only missing mock steps. Recovery stops at the first blocked record and returns the last verified cursor. The caller can continue through pages or restart enumeration after process restart. A repeated page reads verified acknowledgements without new mock effects. Recovery does not invoke the scanner or consume the hypothetical scan budget.

The integration drill uses real local SQLite journaling on Windows and injected mock endpoints. Reopening recreates the controller and journal object; endpoint idempotency state remains in the fixture. This is not evidence of endpoint idempotency across actual external failures, real delivery, a Windows service restart, or 24/7 operation.

## Readiness boundary

Current verdict: NOT_READY for real E2E. Governance and risk matrix: https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6923887024. Real qualification, current operational A/B/C delivery, archive readback, SQL and outcome replay, and sustained Windows recovery remain unverified as one chain. An application start/stop screen follows operational validation; the existing dry-run controls are not acceptance evidence for that chain.

## First executable approval scope to close

The next isolated external step is a public GET preflight, once the exact runner revision and UTC window are approved under the current governance. Target BTCUSDT and ETHUSDT at data-api.binance.vision, only /api/v3/time, /api/v3/exchangeInfo and /api/v3/klines. Five attempts, 120 seconds, proposed weight ceiling 40, no retries or credentials. Stop on an exhausted budget, redirect, server rate-limit, unclosed candle or inconsistent source receipt. Preserve UTC, request counts, permitted response hashes and exit reason. Independent clock witness, actual delivery, GitHub archive effects, SQL and Windows persistence require their own scoped gates. This read-only step alone does not qualify a signal.

## Read-only preflight executable

Run scripts/ops-spot-preflight.py on a clean detached checkout of the tested code. Pass the recorded approval identifier, exact HEAD and TREE, an approved UTC window of at most 15 minutes with at least 120 seconds remaining, and a fresh output directory on D:. Use an outer Windows process watchdog of 120 seconds to cover DNS/TLS or slow socket reads. The inner controller also checks its elapsed budget before and after each request. The CLI records a durable attempt before network I/O and never retries. It expects at most 26 estimated weight units under the 40-unit cap, and stops if the observed minute-weight header is missing or above 200. A successful result verifies public route and closed-bar receipts only. The independent clock and operational E2E remain open. The supplied approval ID is an audit reference, not software verification of owner consent.
