# ZS-OPS-NTS-REAL-PREFLIGHT-AND-QV1-GOVERNANCE-002

Main f99147db8efe3633f351dd224a718de266716161, draft base 9468eb300c853f7de562e3adf59ae4447ade0657. All previous evidence is preserved.

## Windows preflight executable and trust model

`scripts/ops-nts-preflight.py` defaults to zero network. It checks clean HEAD/TREE, D: custody, the approved Windows profile and UTC window, a separately provided permit digest, and an independently approved CA bundle digest. A digest is not proof of who authorized a permit. Use a Windows parent watchdog to terminate the actual Python process at 120 seconds, covering DNS and slow sockets. Keep output in a new restricted D: directory. The executable never modifies Windows time or schedules itself.

Netnod documents NTS-KE TCP/4460 and timestamp UDP/4123, and the Stockholm KE hostname sth1.nts.netnod.se. Its technical documentation distinguishes the timestamp host sth1-ts.nts.netnod.se. Historical 194.58.207.79 is a candidate address, not a current allowlist decision. The client requires the independently approved public IPv4 to resolve from the timestamp hostname and to equal the authenticated negotiated NTS-KE server record and UDP port. A changed or hostname-only negotiated address stops this specific adapter. KE TLS must use TLS 1.3, approved root bundle, matching DNS SAN, ALPN ntske/1 and NTPv4/AES-SIV-CMAC-256; derive independent directional key material using the RFC 8915 exporter. Require at least four distinct cookies, fresh random unique identifier, origin match and AEAD verification for each sample. No retries, proxies, redirect, service keys or certificate override.

The client derives receive-time conditional uncertainty from authenticated packet timestamps, root delay/dispersion and round trip, detects unacceptable host wall/monotonic discrepancy, and uses monotonic ordering to bracket markers. It reports conditional bounds only. Netnod's UTC(SP) traceability statement about local scales does not independently establish absolute accuracy for this endpoint/session/path. Review the reference chain, root error, acquisition uncertainty and calibration age/drift before admitting any real witness. Do not pass this tool's conditional report directly into the real registries. Packet files contain cookies and stay private. Exporter keys are not persisted, so an independent reviewer must reproduce fresh authentication or use separately approved independent attestation.

Primary sources: [Netnod setup](https://www.netnod.se/netnod-time/how-to-use-nts), [technical host separation](https://tech.netnod.se/en/time-services/NTS), [Netnod UTC traceability](https://www.netnod.se/ntp/netnod-and-ntp), [RFC 8915](https://www.rfc-editor.org/rfc/rfc8915.html), [RFC 5905](https://www.rfc-editor.org/rfc/rfc5905.html).

## Proposed authorization text — pending PM and owner

> Approve one foreground Windows time run of the exact tested HEAD/TREE in the published receipt. Profile: [owner confirms Windows account]. Window: [start/end UTC, 120 seconds execution within it]. Permit NTS-KE TCP/4460 to sth1.nts.netnod.se and exactly four UDP/4123 requests to the timestamp hostname's approved negotiated IPv4 [independently reviewed]. Pin the reviewed CA bundle SHA-256 and verify approved public IPv4, TLS SAN/chain, ALPN and authenticated packets. Stop on mismatch, timeout, failed proof, wrong profile or budget, and preserve private packets on D and publish sanitized hashes.
>
> Separately approve optional Spot reads during that run only if explicitly selected in the permit, with their own absolute UTC window. Permit public GET to data-api.binance.vision: time twice, scoped exchangeInfo once, klines once each for BTCUSDT and ETHUSDT. Cap five attempts, weight 40 and 120 seconds, no retry. The combined parent watchdog still caps total elapsed time at 120 seconds. Stop without qualification on unverified timing, future/stale inputs, redirect, throttle, or unexpected payload. Preserve raw response bytes on D and publish sanitized digests.

Permit JSON fields: schema=zs.ops.nts-operator-permit.v1, head, tree, windows_profile, timestamp_ip, ca_sha256, time={start_utc,end_utc}, and optional separate spot={start_utc,end_utc}. Hash the file independently. Invoke `py -3.12 scripts/ops-nts-preflight.py --live --permit <D: file> --permit-sha256 <pin> --ca-bundle <D: file> --output <fresh D: directory>` with PYTHONPATH=src plus the approved dependency directory, inside the 120-second watchdog. Without --live the executable exits 2 without traffic. Windows staging dependencies tested: pyOpenSSL 25.3.0, cryptography 46.0.5, cffi 2.0.0, pycparser 3.0, typing-extensions 4.15.0. The test CA fixture is certifi 2026.2.25, SHA-256 fc9165a12403263e7ebfbdad7be7a3eac0fa5d325d3c70465f28d3690072ca28; it is a proposal, not an approved trust store. Pin verified wheels and clean dependency installation before actual execution.

## Real QV1 approval record — unsigned and blocked

Candidate scope is Intraday UP, BTCUSDT/ETHUSDT public Spot only, closed 30m plus six exact 5m components and causal 1h/4h context, valid bid/ask and rolling 24h quote volume. Proposed engineering ceiling is strict clock bound <1.5 s for prospective evidence; witness freshness must be set by independently verified drift/validity. The research detector fingerprint is 005d92f81637d35f7ff258f1e789f9836bad73f0f5b5363da21abb63525ea973. Pin exact evaluator, strategy and platform manifests at the tested code revision; separately supply signed source receipt hashes, span and missingness counts, context window, liquidity measurements, calibrated thresholds, holdout findings and effective revocation times. Owner + independent reviewer must approve signer/key fingerprint, custody, expiry and revocation and the final policy thresholds. No validated scientific thresholds or real risk acceptance are asserted here. APPROVED_REAL_POLICIES, VERIFIED_REAL_SOURCES and VERIFIED_REAL_WITNESSES remain empty. No fixture is promoted.

## Destination seam and disposition

The new EffectGate is default OFF. Explicit injected permit and qualification verifiers and a role-specific adapter are mandatory for each A/B/C, archive, SQL or outcome effect. It reserves signal+role+digest locally before an effect, verifies the exact receipt, and on restart reconciles an unresolved reservation rather than automatically invoking the effect again. Fault tests exercise that for all roles and reject payload conflicts. No real adapter has been bound and no destination evidence has been created. Actual A/B/C identity and receipts, archive independent verified readback, staging SQL transaction and duplicate import, and causal outcome adjudication require their own pinned adapters and separate permission. Dashboard remains offline.

| Gate | Status and dependency |
|---|---|
| RFC framing, AES-SIV, cookie/ID/origin, unsynchronized and clock-step rejection | PASS in Windows offline fixtures |
| NTS + Spot orchestration | PASS with injected transports only; verified live session and absolute accuracy BLOCKED |
| Time approval packet | BLOCKED pending reviewer endpoint/IP, trust roots, dependency wheel hashes and UTC/profile signoff |
| QV1 real policy | BLOCKED pending source manifests, independent timing signer, scientific rules and approvals |
| Delivery/recovery | PASS on injected boundary and SQLite reopen; actual destination adapters BLOCKED |
| Real integrated E2E / soak | NOT_EVALUATED. No trading authority. |
