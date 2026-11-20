# CLOCK73 — bounded offline correction and coverage acceptance proposal

Status: **ENGINEERING DRAFT / PM REVIEW REQUIRED**. No live run, no production enablement, no scientific qualification, no trading authority.

## Exact defect and bounded repair

`PublicCapture.healthy()` is a *pre-request* admission gate. After a successful final (11th) response is received, persisted to `response-11.private` and `requests.jsonl`, checked for size/status/weight and parsed, it must be returned to its caller. Using `attempts < MAX_REQUESTS` again *after* that response discards it. The repair keeps `MAX_REQUESTS=11` and blocks the 12th GET, while retaining hard post-response deadline, body/weight headroom checks and all transport/HTTP/JSON failures. Tests cover the final receipt, 12th denial, and both four-frame symbol packets.

Stop reason taxonomy now preserves the explicit `PauseScan` reason in the durable scan report instead of conflating window expiry, request exhaustion, HTTP and network failures. Results remain `PAUSED` on interrupted packets, and an attempt reserved in `events` is never claimed twice within the same boundary. A new snapshot/boundary is a distinct study, *not* permission to concatenate asynchronous observations into one point-in-time full-market receipt. Stored `requests.jsonl`, raw `response-<n>.private`, `body_sha256`, and `ScanLedger` result pins remain the evidence trail. On restart, inspect the persistent ledger and receipts; do not infer missing/unknown frames as validated.

## Two distinct acceptance targets

| Target | Scope | Actual constraints | Permissible outcome |
|---|---|---|---|
| **Bounded sample validation** | Up to 2 eligible pairs in one run | 3 discovery GET + (2 × 4 candle-frame GET) = exactly 11 GET; 90-second boundary entry, 110-second capture deadline, 120-second watchdog | If both pass four source-validated frames, report **2/2 sample verified**, not all eligible market |
| **Full eligible market** | Every eligible symbol in one *coherent* point-in-time snapshot | Observed 45 eligible would demand 3 + (45 × 4) = **183 GET**, beyond the 11-GET hard cap, 90s freshness, and watchdog; also needs current real weighted quota, latency and verified source timestamps | **NOT FEASIBLE UNDER CURRENT CONTRACT**; no `MARKET_COVERAGE_VERIFIED` unless 45/45 independently source-validated inside the same binding boundary |

### Architectural alternatives requiring new owner approval

1. **A — preserve bounded sample semantics (recommended immediate acceptance):** use 11 public GET maximum and explicitly label `BOUNDED_TWO_PAIR_SAMPLE_VERIFIED` as a sample-only condition. Keep overall market coverage partial, all missing symbols `QUEUED_UNSCANNED`; retain research-only policy block.
2. **B — redesign full-market acquisition as a separately reviewed contract:** assess exchange rate limits, weight and latency with a realistic instrument-by-instrument budget, API response caps, bounded concurrency, clock uncertainty, 90-second freshness, and watchdog. Freeze an immutable PIT inventory reference and record for every symbol/frame the as-of and receipt-time constraints; reject any source that arrives beyond the admissible boundary. A larger window, different bulk endpoints, saved historical data, or successive candle boundaries **changes the acceptance question** and needs a versioned source-availability/scientific review. No arbitrary quota increase, cross-boundary stitch, or postponed completion claim.

A third route could validate market subsets over independent snapshots, but such studies remain a **series of partial snapshots**, not a single complete snapshot. No 45/45 conclusion follows by summing distinct runs.

## Offline-only Windows acceptance and evidence

Use owner Windows **Python 3.12.10**, explicit fresh checkout of final `HEAD/TREE`, no external network, no `StartForeground`, no scheduling or upgrade. Run impacted suites (at least `tests.test_marketwide_capture`, `tests.test_marketwide_research`, `tests.test_marketwide_cursor` if present), capture raw stdout/stderr, exit code, test count, skips, HEAD/TREE, SHA256 per log, and `PM` independent review. Tests must demonstrate request 11 returns a valid second four-frame packet; request 12 forbidden; observed weight/body/time hard stops; journal hashes; durable cursor restart with no replay; explicit stop reasons; and compact foreground receipt without printing private JSON. No live SHADOW run from this task.

Do **not** infer `LIVE_E2E_NOT_PROVEN`, `QV1_REAL_POLICY_BLOCKED`, or `MARKET_COVERAGE_PARTIAL` are resolved by successful tests. New live pilot, merge, unattended scheduler, Telegram, SQL, production and trading require separate approvals under the PM order.
