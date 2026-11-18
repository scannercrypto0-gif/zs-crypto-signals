# ZS03 P0 targeted integrity correction 002 — owner decision / field manifest DRAFT

Authority: https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6704475456

Status: DRAFT_ONLY / NO_MARKET / NO_MERGE / STAGE03_OPEN / STAGE05_FULL_HOLD

## 1. Clock identity and limitations

The revised evaluator requires EXACTLY ONE IPv4 NTS peer. A selected source (^*) in chronyc -n sources, the single NTS key row in authdata, Remote address plus Authenticated=Yes and NTP tests in ntpdata, and Reference ID in tracking MUST agree, including packed hexadecimal IPv4 identity. Zero/multiple/mismatched entries fail closed. Multiple-source chrony operation is NOT certified. These sequential snapshots are not atomic; a source switch will block.

Previous real run https://github.com/scannercrypto0-gif/zs-crypto-signals/actions/runs/42354587847 recorded a conditional bound of 0.115796s at one instant on an earlier SHA; it is historic evidence only. NO new NTS request is authorized by this fix. The hard criterion is still uncertainty strictly less than 1.5 seconds for a REAL future event. The constant local 0.100-second stamp margin is an UNMEASURED OPERATIONAL ASSUMPTION, not an independent metrological guarantee. It needs explicit real-host calibration and review before event-specific PIT can be claimed. The causal condition latest_possible_input_available <= earliest_possible_decision must be evidenced separately.

## 2. Owner-controlled private raw evidence model — OPTIONS, NOT IMPLEMENTATION AUTHORITY

OPTION A (RECOMMENDED FOR ONE SMALL FIELD FEASIBILITY EVENT AFTER OWNER ACCEPTANCE):
1. Subject to all event gates, capture allowed private raw event bytes, source metadata, source licensing record, received/decision timestamps, raw SHA256, byte length, immutable event ID, code SHA, and exact request counters. Verify readback on a fresh read-only environment.
2. Transfer an ORIGINAL receipt with digest, byte count, event ID, timestamps and source/code references to the OWNER or a truly independent auditor in a separately controlled system outside the raw writer's GitHub permissions. A digest merely inside the same repository is NOT independent. The transfer, time, rights, retention and distinct access control must be demonstrated; none is claimed here.
3. On independent recovery, use scripts/p0-owner-receipt.py with raw bytes and the PRIOR owner/auditor-held SHA256+size; fail on missing/modified content. Its offline tests only simulate that anchor, and cannot prove when or by whom it was anchored.
4. On unreadable raw, expired records, failed owner receipt, failure to establish separate control or rights, STOP (CUSTODY_BLOCKED).

THREAT MODEL: an external already-held digest can reveal post-anchoring raw/history changes; it CANNOT detect pre-anchoring manipulation, secretly coordinated writers/auditors, compromise of both custody locations, administrator deletion of both copies, fabricated source or timing upstream of hash, or a missing independent receipt. Private unprotected GitHub branches and previous Rulesets HTTP 403 mean neither WORM nor writer/admin tamper resistance is proved. Define approved raw/receipt retention and recovery permissions BEFORE any field action. Temporary Actions logs are not durable storage.

OPTION B: evaluate stronger server-enforced retention and separated administrators, possible paid private-repo/third-party locking, cost/quotas/constraints. Requires a distinct owner financial/technical decision, without making the repository public, changing rules, or purchasing anything in this PR.

OWNER DECISION LINE: Choose and explicitly accept A for one limited feasibility event with documented residual risks, OR request B cost/protection analysis. Neither has been authorized for a live event, so INDEPENDENT_EXTERNAL_RECEIPT_PROOF = BLOCKED.

## 3. Future event draft manifest — NOT ARMED OR FROZEN

- Event ID: ZS03-P0-ONE-SHORT-EVENT-FEASIBILITY (PROPOSAL ONLY).
- Source: Binance public Spot market data for BTCUSDT and ETHUSDT ONLY; no account credentials or orders.
- Host: GitHub Actions Ubuntu TEMPORARY DEVELOPMENT HOST, conditional on fresh clock readiness and access control, not Windows production qualification.
- Duration: at most 60 minutes; specific future start/end NOT SCHEDULED.
- Max physical REST GET attempts including retries: 12 total.
- Max WebSocket subscriptions: 12 total.
- Total new payments: USD 0; stop on charges.
- Source legality/rights: Terms, private GitHub storage and redistribution/attribution rights UNVERIFIED; evidence retention blocked pending validation.
- Request weight/quotas: exact endpoints and published Spot weights/limits UNVERIFIED; no calls pending confirmation.
- Data plan: closed candles, local bid/ask/spread and liquidity with source/receive/decision time, clock evidence, raw bytes, SHA256 and independently anchored receipt; event specification not frozen.
- Real UTC: source identity, actual source readouts, monotonic drift and uncertainty <1.5 seconds checked for EVERY event; not established in advance.
- Stop/hold: every missing timing, custody, rights, quota, source, approval or byte verification => NO CONNECT.
- Science: a one-event feasibility test never closes Intraday/Swing, UP/DOWN, N_REQUIRED, OOS, Forward, D1/D2/D3/D5, probability, profitability, or Stage03 scientific qualification.
- Approval: new owner signed window, storage/receipt option, rights/quotas, scope and cost authorization REQUIRED. The earlier 72h proposal is not a requirement.

## 4. Gate decisions

- SOURCE_IDENTITY_OFFLINE_TESTS: CI-dependent, not a fresh real NTS proof.
- SYNTHETIC_READBACK: previously PASS only within synthetic scope.
- OWNER_EXTERNAL_ANCHOR_ACTUAL: BLOCKED.
- PROSPECTIVE_EVENT_UTC: BLOCKED.
- SOURCE_RIGHTS_WEIGHT_QUOTA: BLOCKED.
- EVENT_MANIFEST_FREEZE: BLOCKED.
- SCIENTIFIC_D1_D2_D3_D5_OWNER_SIGNATURE: BLOCKED.
- BINANCE_MARKET_REQUESTS_NEW: ZERO.
- STAGE03: OPEN; STAGE05: FULL HOLD; PR40: DRAFT/UNMERGED.

Next: PM independent review of corrected code + CI; owner custody option and event-specific separate approval BEFORE any market request.
