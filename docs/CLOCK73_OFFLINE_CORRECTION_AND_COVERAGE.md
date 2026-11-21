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

## CLOCK74 coverage design review — 21 November 2026

This section evaluates the current contract without changing its runtime limits. Let N be the eligible inventory count frozen by one discovery receipt. The current four-frame REST acquisition requires R(N)=3+4N GETs and, using the checked-in endpoint estimates, W(N)=20+80+4+8N weight. Thus N=2 needs 11 GETs / 120 weight; N=45 needs 183 GETs / 464 weight. Forty-five is the previous observed count, not a fixed future universe size.

| Criterion | A — bounded two-pair validation | B — full frozen eligible inventory |
| --- | --- | --- |
| Admission | Existing 11 GET / 140 estimated weight; actual minute headroom guard 5500 | Proposed versioned request/weight reservation derived from N; current 11/140 limits prohibit this execution |
| Scope | At most 2/45 source-validated pairs in that historical inventory, 4.4444% overall | All N pairs, all four frames, one declared boundary and final causal decision |
| Concurrency | Existing sequential acquisition | Proposed at most four workers, subject to measured owner-Windows results and shared atomic budget admission |
| Time | Existing 90-second boundary admission, 110-second capture deadline, 120-second watchdog; individual input validation also applies | Same limits evaluated first; no promised full coverage if acquisition cannot meet them |
| Source | Per-request symbol/frame/anchor, byte hashes and closed-bar checks | Same checks plus a complete expected-symbol/frame matrix, a single frozen inventory identity and final revalidation of all inputs |
| Recovery | Durable reservation; ambiguous/incomplete packets stay paused | Durable request and pair/frame states, atomically reserved budget and explicit cutoff; late restart ends that snapshot incomplete |
| Acceptance | Two complete packets may establish 2/2 sample acceptance while market coverage stays partial | Full coverage requires N/N admitted packets at the final common decision, with no missing, stale, late or unresolved input |

### Time feasibility and safe concurrency

There is no new live latency measurement in CLOCK74. The following figures are analytical scenarios. If discovery and candle request latency each equal L seconds, four workers need approximately 3L + ceil(180/4)L = 48L for 45 pairs. Adding an illustrative four seconds for clock observations gives 16, 40, 76 and 100 seconds for L=0.25, 0.75, 1.5 and 2.0 seconds respectively. These figures omit decoding, disk flush, queueing, jitter, retry and decision costs. Sequential acquisition needs 183L plus those costs, so even L=0.5 gives at least 91.5 seconds before clock/processing overhead.

The remaining usable window is 90 seconds minus actual boundary age at entry and reserved clock/finalization margin. Four workers therefore remain a proposal, not an established safe performance level. The existing eight-second per-HTTP timeout gives a worst-case four-worker request envelope of about 368 seconds before overhead, exceeding both freshness and watchdog bounds. A measured p95 cannot establish a worst-case completion guarantee. A future coordinator must stop accepting responses at the actual deadline, return partial coverage, and retain original bodies. It must not extend the clock/freshness window to make N/N pass.

The live API quota and IP headroom must be read from permitted response metadata at the time of a separately approved experiment. Estimated weight 464 alone does not authorize a call or prove sufficient headroom. Shared reservations must cover concurrent in-flight requests before sending them, remain durable after restart and respect server rejection/backoff. Endpoint weighting and rate-limit metadata are documented by Binance; active limits are supplied through exchange information and response headers. No runtime API query or new pilot was performed for this comparison. [Binance REST limits](https://developers.binance.com/en/docs/products/spot/rest-api), [public market endpoints](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market).

### Coherent snapshot, completeness and recovery

Freeze inventory ID I and common closed 30m anchor B. Require 22 consecutive closed 5m bars per pair for directional predicates, exact six-5m parent reconciliation, and the closed 1h/4h anchors causally available for B. Record request admission, response receipt, available-at and payload digest for every input. Use the same symbol and source identity throughout.

Full acceptance must be evaluated at one final decision D after all expected inputs are available. Re-evaluate the oldest market, book, ticker and candle inputs for freshness at D. A pair that passed at its earlier individual decision cannot automatically count as valid at D. This is a coherent acquisition interval against frozen inventory I; the REST endpoints do not establish an atomic simultaneous exchange-wide price snapshot. The exact cohort and interval must be explicit in any future acceptance contract.

The completion manifest must enumerate every eligible pair and four required frames, distinguish reserved/received/validated/committed/unknown states, preserve all original response bytes and verify hashes at reopen. A crash after reception but before acknowledgement requires reconciliation with existing bytes and request journal before reuse. A consumed or uncertain request reservation must not be silently refunded. If the same snapshot cannot finish before its original cutoff, close it as partial and start a separately identified boundary when authorized. Results from different inventory IDs/boundaries are never added together as one complete snapshot.

A stream-backed cache could reduce cold-start REST work, but needs an additional source protocol, connection/reconnect and gap-repair design, causal cache snapshots and separately approved continuous-operation scope. It is a subsequent architectural option, not implemented or activated here.

### Decision submitted for owner / PM review

Recommend accepting A for the present engineering repair after exact-head Windows evidence. Its acceptance wording is **two complete four-frame research packets within a bounded sample**. Keep overall eligible-market coverage partial unless every eligible pair was evaluated in that same snapshot.

B requires a new architectural decision before implementation or live measurement: choose cold REST with a measured bounded worker pool, or approve design of a continuously maintained source cache; specify source/time/freshness semantics and a reviewed dynamic total/in-flight budget. No increase to request, estimated weight, clock, freshness or runtime limits is made by CLOCK74. The code repair can be reviewed independently of that architectural decision.

### CLOCK74 repeatable Windows acceptance

scripts/clock74-windows-acceptance.ps1 accepts explicit ExpectedHead/ExpectedTree and runs nine affected suites through scripts/clock74-offline-tests.py on a clean isolated checkout under D:\ZS-SMART-GATE. It uses Windows PowerShell 5.1 and Python 3.12.10, blocks socket/urllib access during Python tests, preserves raw redirected streams, per-suite statistics and SHA-256, and checks source cleanliness before/after. Its PowerShell summary test parses and executes only the existing hash/printing block against synthetic local fixtures. It does not invoke StartForeground or install/restore the active runtime.

The eight original affected suites are retained. Added acceptance tests cover final-response size/total-byte/deadline/observed-weight failures, estimated-weight boundary behavior, complete private JSON preservation with compact Python stdout, and actual PowerShell 5.1 SHA pointers plus fallback stop reason. Final receipts and remote verification are delivered in the CLOCK74 handoff.
