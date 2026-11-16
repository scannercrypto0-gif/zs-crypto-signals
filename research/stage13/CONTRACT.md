# Stage13 offline operational contract

Version `zs.stage13.synthetic-operations.v1`. Use a local append-only LocalOutbox and injected scanner, archive, Telegram, SQL, outcome and clocks. One bounded synchronous controller per quota session. Each scan costs three hypothetical weight units, including failed attempts. Quota and latency are per process; restart does not prove a durable production quota. p50/p95 are nearest-rank cycle latencies from the injected mock clock. Heavy research and scheduling are outside the scan loop.

The scanner only admits fully closed, fresh, complete synthetic observations within the fixture clock drift bound. Qualified fixtures derive a stable identity from source, candle close, symbol, direction and rule. Every downstream action receives the same canonical JSON and stable per-destination idempotency key. The mock archive is written and checked byte-for-byte before mock A/B/C, then mock SQL and outcome. Local acknowledgements bind the identity and payload SHA-256. Restart resumes explicitly by ID; restore also requires a separately retained checksum pin. Replay assumes the injected endpoints retain their idempotency ledgers. A real transport without that property must reconcile unknown sends before retrying. No automatic pending-job discovery or real endpoint adapters are implemented.

## MODULE_ACCEPTANCE_MATRIX

| Component | Mock evidence | Operational gate and missing evidence | Owner |
|---|---|---|---|
| Spot/source/qualified ID | MOCK_PASS on qualified fixture, stale/future, incomplete, drift and coverage veto | NOT_PROVEN_LIVE: Binance receipt custody, independently verified clock, real source provenance and qualification authority | Source and research owners |
| Windows runner/quota/health | MOCK_PASS on bounded cycles, duplicate scan, API saturation and latency instrumentation | BLOCKED: owner-authorized persistent Windows execution plus restart, outage, resource and soak evidence | Windows operator |
| Telegram A/B/C+JSON | MOCK_PASS on stable ID, payload digest, independent acknowledgements and retry after simulated lost response | NOT_PROVEN_LIVE: recipient identity and actual route receipts; explicit ambiguous-send reconciliation | Messaging operator |
| GitHub archive/recovery | MOCK_PASS on exact readback, corruption veto and pinned fresh-path restore | NOT_PROVEN_LIVE: target branch, durable storage, independent restore receipt and privacy review | Repository operator |
| SQL import | MOCK_PASS on injected key dedup and failure veto | NOT_PROVEN_LIVE: approved schema/import target and uniqueness proof | Database operator |
| Outcome evaluator | MOCK_PASS on identity and payload binding | NOT_PROVEN_LIVE: independent real outcome adjudication and replay | Research owner |

Operational decision: **NOT_READY / NO_TRADING_AUTHORITY**. All external adapters and unattended scheduler are NOT_IMPLEMENTED here.

## Separate owner-controlled live preflight

Before any future run, require PM review and a new owner approval pinning the exact code, Windows profile, permitted public Binance GET routes, symbols, weights, request and elapsed budgets, verified UTC source/uncertainty, and source freshness/completeness. Pin allowed Telegram roles/recipients and send budget, keep credentials private, and require receipt reconciliation for ambiguous outcomes. Approve the GitHub evidence target, retention/privacy review and restore verification, then separately approve SQL import target/schema/uniqueness. Record start/stop evidence, UTC, hashes and acknowledgement counters. Stop on scope, quota, clock, provenance, unexpected routing or recovery failures. Rollback stops the runner and preserves the append-only evidence for reconciliation. No live credentials or side effects in this package.

Proposed future soak for owner approval: 24 continuous hours and at least 288 scheduled scans at five-minute cadence, plus separate bounded restart/outage and corruption drills. Report missed cycles, resource health, weights, p50/p95 and recovery time. This is a proposal, not a measured or approved 24/7 run.
