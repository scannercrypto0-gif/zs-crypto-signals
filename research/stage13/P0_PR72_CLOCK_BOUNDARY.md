# P0 / PR72 — Windows Time privilege boundary and release decision record

**Status:** `ENGINEERING_PATCH_STAGED / NORMAL_USER_BRIDGE_NOT_ESTABLISHED / OPERATIONAL_POLICY_UNAPPROVED / SHADOW_BLOCKED`

This file is an engineering note, **not** an owner or independent-policy approval. It does not amend MASTER or README.

## Observed inputs (2026-11-18, owner Windows 11)

- Normal user `w32tm /query /source` and `/configuration`: Access Denied `0x80070005` in last proven diagnostics.
- Elevated `sc query W32Time` plus `w32tm /query /status`, `/source`, `/configuration`, `/peers`: 5/5 exit 0, and `w32tm /resync` exited 0. These are *administrative inspections*, not a normal-user authorization proof.
- Installed main is `DISABLED`, no scheduled service. Prior SHADOW inventoried 3,750 and queued 37 eligible, attempted 0, with clock blocked. No claim of scan completion.
- The only software release clock acceptance policy remains `WINDOWS_TIME_OPERATIONAL_V1` in `src/zs_smart_gate/ops_windows_time.py`, with `REVIEWED_POLICY_SHA256 = None`.

## Completed scope in PR72

1. Elevated collector uses fixed absolute `System32` binaries and five read-only command+argument allowlists. A custom arbitrary executable is not accepted.
2. Each spawned command has configurable 1–15s limit (default 8s). A timed-out process is killed; exit `124` is recorded. Launch/wait errors record exit `127`. Failure is **not** a grant of time authority.
3. Raw redirected stdout/stderr are retained, each hashed SHA-256; report is UTF-8, includes durations, times, timeout flags, exact commands and administrator SID. Files have a unique new evidence folder under `D:\ZS-SMART-GATE\validation`, never overwrite older receipts.
4. Preflight refuses non-admin, missing disabled marker, shadow lock, custom root, or reparse-point directories.
5. Targeted offline regression tests check policy gating and negative conditions, and a local Windows 5.1 acceptance script captures exact SHA, TREE, Python 3.12.10, logs and both user/elevated evidence.

## Remaining engineering/security review — mandatory stop

The collector **does not authenticate evidence for an unprivileged SHADOW process**. SHA-256 of a file stored on an owner-writable drive detects transfer changes but does not prove authorship or prevent a malicious local writer from replacing the file and recalculating its hash. In particular, setting `runtime_witness_authorized` to true in local JSON has no effect and MUST NOT be interpreted as authority.

A production-quality normal-user bridge would require a reviewed protected private signing key and pinned public verification key, signed canonical allowlisted command results, short TTL, nonce/challenge binding, verified caller/release identity, anti-replay and drift checks, no unreviewed auto-promotion, and verified Windows file/key ACLs. No signing identity has been provisioned or approved, and no such bridge is asserted in this PR. Enabling the unprivileged consumer on plain D: evidence is explicitly rejected.

**Alternative only by later explicit owner decision:** an administrator-only *single* bounded SHADOW foreground process, with the exact release and approved time policy, monitored 120s watchdog, no scheduler, and a documented rollback. This is not automatic, not the default, and not authorized by this document. It increases privilege exposure and must be separately risk-accepted.

## Independent clock-policy approval outstanding

Candidate source is `time.cloudflare.com`; proposed caps are absolute offset 0.5s, conditional uncertainty 0.5s, last-sync age 600s, monotonic/wall divergence and sample spread 0.05s, and four distinct stripchart samples. Confirm measured Windows source and peers against the allowlist. Samples are not authenticated independent cryptographic UTC. Independent policy reviewer and owner must approve source/limits and canonical digest *before* code can pin `REVIEWED_POLICY_SHA256`.

## Windows acceptance and rollback

Run the exact-HEAD/TREE isolated worktree acceptance script in this PR, on the owner's Windows 11 machine, PowerShell 5.1 and Python 3.12.10. Start the parent unelevated; the optional `-CollectElevated` switch starts **only** the narrow collector through visible UAC. It does not enable a service, alter ACLs, change Windows Time settings, install a scheduled task, trigger SHADOW or change installed `main`.

Evidence is kept on `D:`; receipt includes observed PINs, raw stdout/stderr hashes, command exits, test counts and explicit unresolved policy. Failure of tests or privilege separation is `BLOCKED`, not masked as skipped acceptance. To roll back engineering evaluation, discard the isolated Git worktree after retaining its raw evidence; the installed release remains untouched.

**Closure requested:** PM independent engineering review of the new exact HEAD and Windows raw evidence, independent policy review, separate owner merge/risk authorization. If either clock policy or runtime identity gate fails, **do not run SHADOW**. No Telegram, trading, SQL writes, operational GitHub effects or unattended process are authorized.
