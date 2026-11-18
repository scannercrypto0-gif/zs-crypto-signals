# Windows Time and standing public read-only authorization — Orders 003/004

Main ad949a595814385dc70572a860b0539aa15d7d12 and PR71 comment 6948025124 govern the current runtime. Historical permits, NTS proposals and receipts are retained as historical research. The active Windows Time/Spot path uses standing authority without a per-run owner approval, digital signature or approved UTC window. It remains explicit operator invocation, foreground only, one Windows Time stripchart of four samples, at most five credential-free Spot GET attempts, estimated weight ceiling 40, observed minute-weight guard 200, no retry/proxy/redirect, and a 120-second parent watchdog. The optional historical NTS code is not the Windows runtime dependency.

Invoke on a clean Windows checkout with PYTHONPATH=src and Python 3.12:
`py -3.12 scripts/ops-spot-preflight.py --live-read-only --output D:/ZS-LOCAL-CI/fresh-receipt-dir`.
A fresh path avoids overwriting evidence. Stop with Ctrl-C; timeout kills the diagnostic subprocess. Do not use command exit 0 as clock approval: exit 0 means the Spot source preflight succeeded. The machine-readable clock decision and qualification states remain separate. Raw market bodies and Windows command output stay private on D:. Public receipts retain command exit codes, source, observed offset/RTT, request parameters, monotonic and UTC markers, digests and veto codes. Windows system settings and the clock service configuration are untouched.

| Scope | Permission and evidence |
|---|---|
| Windows time inspection and allowlisted stripchart | STANDING_AUTHORIZED; status and four samples observed. Operational acceptance BLOCKED: source/configuration queries denied and candidate tolerances unreviewed. |
| Binance Spot public source | STANDING_AUTHORIZED; five requests passed on follow-up. First run stopped at fourth attempt on unverified quota headroom and is preserved separately. |
| UTC research witness, QV1 and scientific evidence | BLOCKED; unauthenticated Windows/NTP path lacks independent cryptographic UTC and does not populate scientific registries. Optional NTS research is preserved. |
| Telegram A/B/C, operational GitHub archive, SQL and outcome effects | External effects outside standing authorization. Default-off injected readiness envelope only, real route and outcome evidence NOT_EVALUATED. Normal PR evidence publishing is authorized. |
| Windows scheduling, soak and trading | Not run; live E2E NOT_PROVEN. Trading remains disabled. |

## Decision sheet for operational tolerances

Proposed only: allow time.cloudflare.com, no local CMOS or unknown peers; synchronization age <=600s, four distinct offset samples, absolute offset and conditional proxy uncertainty <=0.5s each, wall/monotonic divergence and sample spread <=0.05s. These limits are engineering proposals for closed 5m/30m handling, not a trigger-time accuracy guarantee. A 0.5s cap is small relative to one candle; the runner still requires a verified closed anchor and must not reuse an old status after a step. Conditional proxy uses Windows root dispersion + half root delay + half the largest stripchart RTT; asymmetry, unauthenticated source/spoofing, and unrelated status/stripchart endpoint paths limit interpretation. Independent reviewer and owner should confirm the source allowlist and tolerance values, then resolve command access and verify measurements before an accepted operating policy is wired. No automatic fallback grants acceptance. No new per-run approval packet for read-only connectivity is needed.

Historical gates 00–13 and gates 1–6 remain in the final acceptance matrix. This update closes the standing read-only invocation and measured diagnostics portion only. No operational acceptance, genuine qualification, route reconciliation, stability run, or production deployment follows from these observations.
