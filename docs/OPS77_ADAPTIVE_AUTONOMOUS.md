# Issue77 / OPS24 adaptive and standing-authority contract

Authority: Issue51 comment7061389384; Issue77; PM review6004705942. Root MASTER/README remain PM-owned. Existing main7b7bb0e and Draft PR75 are not changed here.

## Adaptive legal admission V2

All returned REQUEST_WEIGHT and RAW_REQUESTS intervals are frozen from exchangeInfo; ORDERS is explicitly nonapplicable to this GET-only client. Unknown limiter types, duplicate/invalid intervals and missing weight headers HOLD. REST uses no subscriptions/stream sessions. Endpoint costs are pinned to the reviewed official REST reference SHA e7b6eade603cd0db0fc88e717ba67a58e19e0089, inspected2026-11-21 (48 Weight sections, no zero-cost REST route). No private order endpoint exists in the allowed client.

Preferred target is floor(cap*59/60), e.g.5900/6000 and11800/12000; it is not a GET count and is not a target to fill. Before a stable measured quorum, unknown shared-IP exposure reserves10% rather than pretending100 weight always suffices. Observed external-use jumps increase the adaptive margin using timeout/jitter exposure. The current provider count plus all in-flight worst-case weights is charged atomically; lower/out-of-order headers cannot refund use. Requests reserve every possible window intersecting send-minus1s through timeout-plus1s. Strictest applicable interval wins; lower provider limits apply immediately. No local estimate can guarantee unseen external IP activity will remain unchanged; quota admission is conditional on the provider's published/observed limits, and429/418 immediately stop activity.

RAW_REQUESTS has no generally exposed independent REST use header. When absent, its total REST use can only be bounded via an aligned shorter REQUEST_WEIGHT provider limit and the official minimum1 weight/request. For actual61000 raw/5m vs6000weight/min this yields at most30000 raw/5m. If that documented minimum/counter scope is unsupported, intervals do not align, or the provider envelope cannot fit the RAW ceiling, HOLD rather than assume zero external raw use. This explicit provider-envelope assumption needs review with the new policy. No raw/weight equivalence is silently asserted.

One exchangeInfo bootstrap GET is allowed before learning metadata; it is explicitly not a guarantee of spare unknown shared-IP quota. No other bootstrap endpoint/retry is allowed. Transport uses verified per-worker persistent HTTPS and never retries unknown acknowledgements. A durable two-phase conservative reservation precedes HTTP: a crash after global quota intent but before the cycle record can leak capacity, never create extra capacity. Such unknown intents remain nonreplayable, with carried worst-case costs.429/418 Retry-After survives restart; no missing ban expiry is guessed. Timed expiry permits only NEW snapshot intents; old unknown/same request is not resent. Complete original-receive reconciliation remains explicit and hash-verified.

Worker count now uses warm discovery latency, remaining causal time, request-body reservation space, Python working-set headroom and CPU concurrency. Two remains the measured minimum when sufficient. No unrelated4-worker cap remains.512MiB working-set,32MiB response reservation,1GiB spool, free-disk reserve,90s causal freshness/110s capture/120s watchdog are resource/safety contracts, not provider quotas. Reaching them yields HOLD; none is silently widened to obtain N/N. A larger causal contract needs separately versioned proof.

## Automatic standing release, not manual permits

ops24-standing-release.py reads the owner directive from GitHub, exact-head PM review records, PR76 merged state/current main/tree and byte-verified actual Windows and full-market receipts. It produces standing-authority.json; no owner_merge flag, digital owner signature or per-run approval is requested. Source review must include one exact machine-readable line:

    OPS24_RELEASE_ACCEPT <reviewed-source-HEAD> <TREE> PUBLIC_SPOT_READ_ONLY_NO_TELEGRAM_SQL_TRADING

A PM shared-account COMMENT is labelled as such, never a fictitious identity-separated formal APPROVE. The changed source has no such acceptance yet. GitHub branch protections are not bypassed; platform merge must actually exist. The branch API exposes protected state; private-plan protection/ruleset APIs currently return403, so no unsupported assertion that all rules are absent is made.

Worker startup independently refetches the real authority/review/merge records; a fabricated local accepted flag or modified directive is refused. An installed merge SHA may differ from reviewed premerge SHA only with the exact same tested TREE and a verified PR/main linkage. Offline startup may produce HOLD/status, never invent a cached release approval. STOP/Disable/release-file changes remain immediate revocation controls. A finite24h window is composed automatically once the reviewed release can be started; existing windows and missed slots are never erased for a restart.

Actual G3 deployment receipts (noninteractive normal task, original hash-linked reboot/logoff/restore/STOP observations) remain required before Serve. ops24-task-probe.ps1 performs an isolated finite normal-token scheduler test with zero market/Telegram/SQL, cleans its unique task, and explicitly labels real reboot/logoff untested. Registration failure is a genuine Windows privilege defect, not missing owner permission. InstallDisabled/Verify/Status/Start/Stop/Disable/Restore/Rollback/Health/Evidence have explicit deterministic paths.

No claim of endless operation follows from a finite24h journal. Actual48 source boundaries/288 health slots and observed uptime must first pass. Ongoing24x7 transition, real reboot/logoff and Stage00-13 delivery/science readiness stay separately observable; this code does not fabricate these proofs.

## Current science/delivery boundary

Clock bounded operational equivalence is accepted by PM; independent cryptographic UTC is not proved. A real source/candidate replay is not qualified signal science. This OPS24 release cannot send Telegram, SQL or trading. Issue77 owner-private TEST delivery and real Stage00-13 adapters are a coordinated separate integration scope; true production alerts require independent directional scientific GO and actual route/ACK/recovery proof. Existing synthetic Stage13 is preserved and cannot be relabelled LIVE.


## Actual scheduler diagnostic and profile-independent toolchain

Normal-user registration initially returned0x80070005. The owner's elevated isolated probe registered and launched a least-privilege task, but Scheduler event201 recorded0x80070002 and no Python probe; that is NOT a successful worker or reboot test. The diagnostic is retained, not reclassified as a clock defect. New task diagnostics capture direct stdout/stderr/exit/LastTaskResult before cleanup.

A stdlib-only D-local Python3.12.10 runtime is copied byte-for-byte from the existing installed PSF-signed3.12.10 executable/libraries (no new download, site-packages, registry edit or venv mutation). Its2126-file manifest contains original/copy SHA256; native Python signature is Valid/PSF. All executable/stdlib prefixes were actually verified under D. Original Windows runtime and Python remain untouched. Worker startup also uses the absolute hash-pinned installed Git binary; task XML declares its working directory and isolated Python mode, rather than inheriting the Codex environment. A finite diagnostic wrapper writes original native output to D, without a persistent elevated process.


## Measured V2 shared-IP burst correction

The first new-head live round71d41f9 stopped conservatively at4/55 after21 actual GET/140 estimated weight. Observed header use220 included80 external points, and real exchangeInfo now advertised RAW_REQUESTS300000/5m (not historic61000). This original PARTIAL result is retained. A millisecond response spacing inflated a20-point shared-IP jump into an unrealistic sustained579 points/s forecast. V2.1 uses a full sliding second of unexplained consumption plus a time-decaying prior high-water forecast; it does not divide a burst by milliseconds. Absolute provider counters, concurrent worst-case reservations, preferred target and large-burst fail-closed checks are unchanged. New adversarial tests distinguish an80-point microburst from a real4000-point pressure event. This is a measured implementation correction, not a silent removal of shared-IP safety.


## Actual S4U administrator-token finding and standard-account setup

The owner-created71d41f9 task executed Python and returned NORMAL_USER_TOKEN_REQUIRED: Windows S4U supplied the admin-member owner's full token despite LeastPrivilege XML. The guard is retained; no elevated worker is accepted. The one-time administrator-only standard-role probe instead creates/reuses one app-marked local standard account (never an administrator), with a random password kept only by Windows SAM and not exported. It grants RX to this immutable D source/runtime, state-only writes and read-only protected release/STOP files, runs an isolated S4U probe and removes the task. Existing unrelated accounts are not modified. This requires a real admin setup command, not owner reauthorization or a UAC bypass.

The eventual standard worker receives no owner GitHub credentials. Owner bootstrap first verifies actual GitHub review/merge/source/Windows records online; an SHA-bound cache protected by native owner/System/Admin-only mutation ACLs may then be consumed read-only by the separate worker. Startup checks the actual OS ACLs and separate worker SID; mutable/self-owned caches fail closed. Routine owner-side release refresh still checks live GitHub authority. This is not a fabricated approval flag. Actual reboot/logoff, reviewed deployment and continuous24h still require their own measured receipts and remain open.


## Owned-file DACL correction and original hash verification

The first standard-account setup accepted the shortened Windows48-character description, then a recursive icacls combination left empty protected file DACLs. It did not change file bytes, create a market worker or send a message. The owner recovered2925 source/runtime objects using their existing WRITE_DAC rights, through a scoped DACL-only native call (no SACL/owner mutation, privilege escalation or system path change). All2126 runtime hashes match the original manifest; the immutable source checkout remains clean. The flawed icacls sequence is removed. An actual Windows regression intentionally empties an owned temporary file DACL and verifies restoration of explicit owner/System/Admin FullControl, worker RX and unchanged bytes. This original failure and repair remain evidence, not PASS reclassification.
