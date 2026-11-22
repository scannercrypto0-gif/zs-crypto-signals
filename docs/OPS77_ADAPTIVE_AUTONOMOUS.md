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

## Actual cross-user S4U registration failure (2026-11-21)

The f98ce7a Windows administrator-run isolated probe reached registration but
returned 0x80070005, registered=false; no scheduled worker or network call ran.
This is not a successful scheduler/clock/reboot/logoff acceptance.
Microsoft documents that an administrator registering S4U as a different user
must provide that user's password:
https://learn.microsoft.com/en-us/windows/win32/taskschd/security-contexts-for-running-tasks

The probe now supplies a PSCredential in-process. Its dedicated, unused project
account receives a random password only when no existing task or Windows user
profile references that account. Existing nonproject accounts/admin membership
are rejected. No password is passed in a process argument, file, report or Git.
S4U and LeastPrivilege remain unchanged. Credential references are cleared and
the SecureString disposed. Windows SAM retains the account password hash; this
is not a claim that managed plaintext memory can be provably zeroed.
This finite diagnostic repair does not fix or certify unattended bootstrap
registration, reboot/logoff, or 24-hour operation. Those remain separate gates.
A new empty root must be used; failed evidence must never be overwritten.

## Actual batch-logon gate after registration (2026-11-21)

The 8981f5b administrator attempt registered and cleaned its finite task, but no
worker began. Operational events 101/104 recorded result 2147943785 (0x80070569),
which is ERROR_LOGON_TYPE_NOT_GRANTED. LastTaskResult 267011 was merely
HAS_NOT_RUN, not the underlying cause. No project profile was loaded.

Provision only SeBatchLogonRight for the marked nonadmin ZS_SG_Research account
using LSA additive account-right APIs. Preserve every other right and all deny
policies; an explicit account batch deny aborts. Group/GPO denies are not removed
and can still cause a real hold. No global secedit overwrite, admin membership,
UAC change or task-security bypass. The operating-system right persists for this
worker; native source, receipts and temporary compiler output remain on D.
Task failure receipts now retain sanitized scheduler event IDs and ResultCode.
Reference: https://learn.microsoft.com/windows/security/threat-protection/security-policy-settings/log-on-as-a-batch-job
Native compilation/nonadmin rejection tests do not establish actual LSA grant or
scheduled execution; those require the administrator-run pinned probe.

## Actual standard worker starts, then native clock provenance HOLD

8c8c84b Windows attempt added batch-logon right, registered and started the task
at 2026-11-21T14:00:26Z. Worker exit 2 stdout was
NORMAL_CLOCK_OS_PROVENANCE_UNAVAILABLE; stderr was empty. This is a real
scheduled process launch, NOT clock acceptance or complete probe success.
Native inspect() previously discarded its child stderr. Health now preserves
native stdout/stderr/exit/hashes on D and records the actual normal-token probe
before rethrowing the clock failure. No failed witness is accepted.

The previous diagnostic account now has an OS profile. Its password and profile
are not reset or deleted. A single reusable ZS_SG_Worker role is provisioned for
subsequent probes, with its credential saved only as Windows CurrentUser DPAPI
CLIXML in D:\ZS-SMART-GATE\secrets\ops77-worker\account.clixml. Owner/System/Admin
only ACL; worker cannot read the credential. Never publish this secret or its
ciphertext. Existing-account credentials are loaded, never reset. Missing or
orphan credentials cause HOLD. This supersedes the earlier diagnostic-only
no-password-file implementation; plaintext is still never written/exported.
New public receipts say plaintext_password_exported=false and explicitly
identify the local DPAPI store. The old account remains untouched for evidence.
Actual native clock failure root cause remains unestablished until its retained
child error is observed. No live calls, review or scientific GO is inferred.

## 2026-11-22: scheduled normal-token provenance failure isolated

Actual 8acea8a scheduled Health produced normal_token=true and session 0, but
clock BLOCKED. Retained native stderr establishes SERVICE_SID_QUERY_FAILED at
sc.exe showsid. No signature/registry/time check had been accepted by fallback.
Replace only this identity-lookup operation with OS NTAccount translation of
NT SERVICE\W32Time and NT SERVICE\autotimesvc, Microsoft's documented service
name-to-SID mechanism. Keep exact service SID shape/distinctness, registry ACL,
binary signatures, source and numerical clock limits. Do not grant SCM access
or administrative membership to the worker. The original sc.exe binary remains
included in integrity checks; historical receipts remain unchanged.
Native comparison tests verify translated SIDs match actual original sc.exe
showsid on the normal operator. Actual S4U worker Health still needs execution;
operator comparison is not evidence of acceptance under the worker identity.
Reference: https://learn.microsoft.com/en-us/windows/win32/api/winsvc/ns-winsvc-service_sid_info

## Scheduled signature HOLD, 2026-11-22T05:59:54Z

Actual 4b17381 S4U worker resolved both service identities and reached
SYSTEM_BINARY_SIGNATURE_UNVERIFIED. Normal-token scheduled execution is proved;
clock acceptance remains BLOCKED. Earlier inspection retained output only if
the collector exited nonzero, losing rejected signature details on exit zero.
Persist raw collector stdout/stderr/hash for every diagnostic collection before
validation, with COLLECTED_UNVALIDATED explicitly separate from acceptance.
Also retain each Authenticode StatusMessage. No signature verifier is loosened.

A bounded direct credential-authenticated standard-user inspection collected
five Valid Microsoft signatures, but this differs from S4U and cannot substitute
for scheduled evidence. Initial direct attempt failed inherited PSModulePath;
that failed receipt is preserved. Native Windows module-path retry collected
all five signatures. Actual standard-user self-registration of a finite S4U
no-trigger diagnostic was refused 0x80070005, no task registered. These attempts
made zero market/Telegram/SQL calls; no elevated credentials were used. Actual
S4U status messages therefore still require the administrator registration path.
Source account/DPAPI credential remains unchanged. Do not weaken signature checks
or claim cache warming, trust repair or equivalence on this evidence alone.

## 2026-11-22: exact S4U signature results and controlled Password comparison

2d39930 actual scheduled profile retained four NotSigned results (sc.exe,
w32tm.exe, w32time.dll, autotimesvc.dll), empty signer fields, and svchost.exe
Valid/Microsoft Windows Publisher. The same files validate in credential-
authenticated direct standard-user inspection. Native normal-operator query
reports Catalog signatures for all five. This establishes a logon-context
validation difference, NOT that system binaries are unsigned/tampered, and NOT
an exact diagnosis of the internal catalog/RPC/crypto failure.

Use the existing managed standard worker credential for a finite scheduled
Password-logon comparison. Preserve LeastPrivilege, normal-token guard, actual
registry/signature/SID/source and numerical clock gates. Password-logon requires
Windows Task Scheduler to retain its protected account credential during task
registration; this is OS configuration (C permitted), not plaintext project
storage. The owner-DPAPI project credential remains on D, no reset/export.
The actual probe XML is preserved locally and its hash/logon type recorded;
the disabled installation template remains S4U historical/deployment template.
Only the isolated finite probe selects Password; production bootstrap is NOT
silently changed or enabled. Cleanup unregisters the finite task. No claim that
all scheduler-managed secret remnants are independently proven erased.

The comparison requires actual administrator registration. It is not a proven
fix until the same-user scheduled Password result is observed. Never ignore
NotSigned, accept operator witness as S4U proof, or install new trust roots.
The verifier still rejects any invalid binary signature. Additional receipt
SignatureType is informational, not an alternative acceptance criterion.
Microsoft references:
https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-logontype-principaltype-element
https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/get-authenticodesignature

## Explicit catalog-member verification implementation (pending actual scheduled test)

Password-logon actual daa6222 still returned four NotSigned/None signatures and
one embedded Valid signature. Its profile preserves original status messages;
changing S4U alone was not a proved fix. Direct credential-authenticated Python
inspection, including loaded user profile and corrected profile environment,
still returned five Valid Catalog signatures. Therefore no exact Windows
internal catalog-discovery cause is asserted and no OS trust-store/ACL repair
is attempted speculatively.

Implement a distinct explicit catalog-member path using Windows WinVerifyTrust
WTD_CHOICE_CATALOG and CryptCATAdmin SHA256 SIP hashing. Provision a protected
read-only DISCOVERY_ONLY catalog-location map under the operator; NEVER accept
its status as a witness. The actual standard worker recomputes the binary's
SIP hash/member tag, verifies the specific member/catalog/chain with native
WinVerifyTrust, independently checks the catalog's own embedded Microsoft
Authenticode signature, whole catalog/binary SHA256 and protected Windows ACLs.
Only NotSigned auto-discovery can use this separate evidence; HashMismatch,
NotTrusted, unknown signature failures, changed bytes, nonzero native code,
unqualified signer and mutable/out-of-store catalogs remain rejected. Original
NotSigned results are retained; no failed result is rewritten to Valid.

Native module loads wintrust.dll by absolute GetSystemDirectoryW path, closes
all native state/catalog handles, and bounds file/catalog bytes. Diagnostic
map discovery has a 30-second process-tree watchdog; signature child queries
have 10-second timeouts and task Health retains its overall finite watchdog.
Partial catalog details persist on failure. New Native-catalog evidence requires
independent PM review; the assessment explicitly says so. No independent UTC,
revocation freshness, reboot/logoff, 24-hour or production GO is implied.

The finite Health probe uses the map only for this diagnostic path. Existing
Serve/default observer and production disabled deployment are not silently
activated or migrated. Owner OS configuration permission covers the existing
standard account and protected Scheduler credential; project code/maps/receipts
remain on D and allowed artifacts on GitHub, secrets/ciphertext stay local.

Windows native positive test proves real sc.exe membership and Microsoft-signed
catalog. A changed .text byte fails native WinVerifyTrust even with the original
real signed catalog. Metadata-negative tests reject altered member/binary/catalog,
non-Microsoft signers, mutable or absent catalog ACLs, original HashMismatch and
boolean/uncertain native return codes. Clock fixtures in these tests are synthetic
and do not establish actual scheduled clock acceptance.

SDK references:
https://learn.microsoft.com/en-us/windows/win32/api/wintrust/ns-wintrust-wintrust_catalog_info
https://learn.microsoft.com/en-us/windows/win32/api/mscat/nf-mscat-cryptcatadmincalchashfromfilehandle2
https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-winverifytrust

## Actual 28b5b2a result: signature gate passed, service-read access still denied

Actual scheduled Password Health finished worker exit 0 with normal_token=true.
The explicit catalog member/signature/protected-store verification passed in
session 0. Clock remained BLOCKED because sc.exe query W32Time and w32tm status
returned AccessDenied. Four stripchart samples succeeded (maximum absolute
observed offset 0.0220374s), but service state/source/last-sync/root dispersion
were unavailable; no total uncertainty or clock acceptance is inferred.

Prepare only SERVICE_QUERY_CONFIG | SERVICE_QUERY_STATUS | READ_CONTROL
(0x20005) for the dedicated nonadmin ZS_SG_Worker SID on W32Time. Native service
DACL helper adds missing allow bits, preserving existing ACEs/denies, owner and
SACL. No SERVICE_START/STOP/CHANGE_CONFIG/USER_DEFINED_CONTROL, deletion,
WRITE_DAC/WRITE_OWNER rights are granted to the worker. Administrator setup is
required by Windows. No grant has actually run in the normal agent session.

A protected original DACL backup remains in the owner-only D credential vault;
only before/after hashes and nonsensitive scope are reported publicly. Existing
backup is not overwritten. No other service or SCM policy modified. Denies are
not removed; a higher policy can still block and must remain HOLD. Idempotent
setup checks the actual resulting allow mask, not fabricated query outcomes.
Actual query/clock success still requires the next standard scheduled probe.

Pure descriptor tests compile native helper and prove added bits are read-only,
original denied stop ACE/old allow ACE/owner/group/audit remain, and repeat is
byte-identical. Normal caller mutation is rejected before OS changes. No actual
Windows service security is modified by these tests. This patch leaves clock
math and catalog verifier blobs unchanged; accepted tests are not rerun broadly.

Reference: https://learn.microsoft.com/en-us/windows/win32/services/service-security-and-access-rights
