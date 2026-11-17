# ZS-FINAL-LIVE-E2E-SIGNALS-001 — Windows engineering receipt

Main f99147db8efe3633f351dd224a718de266716161; existing draft PR #71 base evidence 2dca98eb1b1e3f029990ce66ac0615b2113dd5c1. Prior failed and successful evidence retained. PM review 6942174110 remains the applicable independent review; this increment is submitted for separate review.

| Stage | Current evidence state |
|---|---|
| 00 Windows | OFFLINE_PASS: local diagnostics foreground start/stop and local journal reopen. Windows service, real outage and sustained resource metrics NOT_EVALUATED. |
| 01 Spot | LIVE_PROVEN for historical five-GET public preflight only; prior UTC format failure retained. |
| 02 Setup | OFFLINE_PASS under accepted engineering scope; genuine trigger in this operational workflow NOT_EVALUATED. |
| 03 Qualification | BLOCKED: real policy, source and signer registries empty; signed fixture evidence is not authority. |
| 04 Custody | OFFLINE_PASS on SQLite recovery and mock archive readback; live archive and restoration BLOCKED. |
| 05 Telegram | OFFLINE_PASS on A/B/C ports; qualified live routing, ambiguity reconciliation BLOCKED. |
| 06 Outcomes/SQL | OFFLINE_PASS on independent pre-existing components and mock transport bindings; isolated real SQL and outcomes tied to live signal NOT_EVALUATED. |
| 07 Intraday | OFFLINE_PASS in previously accepted engineering scope; live evidence NOT_EVALUATED. |
| 08 Swing | OFFLINE_PASS in previously accepted engineering scope; live evidence NOT_EVALUATED. |
| 09 Profiles | OFFLINE_PASS in previously accepted engineering scope; live evidence NOT_EVALUATED. |
| 10 Futures | OFFLINE_PASS synthetic contextual evidence; optional independent feed NOT_EVALUATED. |
| 11 BTC context | OFFLINE_PASS synthetic context; real universe coverage NOT_EVALUATED. |
| 12 Predictive research | OFFLINE_PASS engineering; actual scientific results BLOCKED_REAL_DATA_NOT_VERIFIED / NOT_EVALUATED. |
| 13 Operations | OFFLINE_PASS on readiness controller and corruption/replay tests; actual integrated cycle and soak BLOCKED. |

## Dashboard and recovery

On Windows with Python 3.12 and Tk, use a clean checkout, then run `py -3.12 scripts/ops-dashboard.pyw --output D:/ZS-LOCAL-CI/dashboard-run-unique`. The directory must be fresh. Start launches fixed offline diagnostics and Stop terminates that child only. Closing waits for the child to exit. Read stdout/stderr and the exit record in the output directory. Restart with a fresh directory and keep prior logs. The separate fixture controller can reopen a previously committed journal and run bounded recover_page, stopping on invalid evidence and preserving verified acknowledgements. This dashboard is offline only: actual cycles, counts, endpoint status, pending live work and resource metrics remain unknown. The Windows widget test exercises Start and Stop with a real Tk window withdrawn by the test.

## Independent time — endpoint verification and remaining trust work

Netnod documents Stockholm key establishment at sth1.nts.netnod.se and port TCP 4460, and NTS-secured NTP over UDP 4123. Under RFC 8915, authenticate the configured TLS identity and chain with reviewed trust roots, verify ALPN ntske/1 and negotiate the timestamp endpoint/port. Require exact negotiated endpoint match to the approved target, AEAD verification, unique request identifier and request/response binding. Historical PR71/Stage03 artifacts contain observations, not current authorization or a defensible absolute UTC accuracy certificate. No DNS lookup, NTS packet or Binance probe made under this order.

The recorded adapter expects four transcript-bound observations from an injected verifier, including request IDs, session, source digest, UTC-at-receive bounds and monotonic send/receive ordering. The verifier must attest both the sample fields and transcript, not just a user-supplied flag. The adapter rejects missing synchronization, excess widths, reordered/replayed/mutated samples and overlapping intervals. Pin independently calibrated uncertainty, drift and age before using these brackets for real qualification. No production trust roots or signer admitted.

References: [Netnod NTS operation](https://www.netnod.se/netnod-time/how-to-use-nts), [RFC 8915](https://www.rfc-editor.org/rfc/rfc8915.html).

## Combined authorization package for independent review

Use the tested code and tree in the Windows receipt for offline review. The real time client, real policy admission and operational adapters must each have their own clean pinned executable before activation. Exact operator profile, UTC start/end and destinations are pending. A missing field blocks activation.

- **Gate 2 (time + source), time and source owners.** Propose maximum one NTS-KE session and four UDP requests, 120 seconds, no retries, pending independent approval of negotiated timestamp host/address, trust roots and accuracy envelope. If separately authorized, use original public Spot preflight paths /api/v3/time, /api/v3/exchangeInfo, /api/v3/klines for BTCUSDT and ETHUSDT only, at most five GETs, weight 40 and 120 seconds. Preserve private transcript and raw source bytes on D and publish only verified, sanitized hashes and metadata. Stop on endpoint or signature mismatch, missing witness, rate cap, stale data or loss of synchronization.
- **Gate 3 (real policy), owner and independent research reviewer.** Sign exact policy/evaluator and per-source SHA, symbols/frames, coverage and time criteria, holdout evidence and thresholds, key fingerprint, validity/revocation rules. No signature, real policy proposal or accepted science is fabricated by the executor. Block without all fields.
- **Gate 4 (destinations), separate messaging/archive/database owners.** Telegram pinned HTTPS Bot API identities/roles and redacted destination IDs with local protected secrets; proposed 10 calls, maximum 2 authorized diagnostic sends, no unqualified 05A. GitHub dedicated isolated ref, one sanitized artifact <=1 MiB, pinned restore into new directory and exact SHA. SQL isolated staging via approved connection, one transaction plus duplicate verification, rollback on divergence. Log digest/count/route/receipt without secrets; hold ambiguous operations for reconciliation.
- **Gates 5–6, Windows operator and PM.** First one signals-only foreground cycle with preceding approvals, version and endpoint caps; verify true same-ID route, authorized storage, staging dedup and mature censored outcomes. Stop on missing proof, preserve journal, reconcile uncertain acknowledgements before replay. Review 24h/288 cycles as a distinct authorization with resource, latency, missed-cycle and zero-duplicate requirements. No persistent task or soak authorized here.

## Disposition

PARTIAL_LIVE_PROVEN / BLOCKED. Gate 1 has targeted Windows evidence. Gates 2–6 lack current independent time, approved real policy or operational receipts and separate activations. No trades or live side effects under this order. Hosted evidence runs 44042091901 and 44042091858 remain FAILED; sampled GitHub jobs report payment/spending-limit startup blocks. Windows tests are separately scoped evidence.
