# SMART GATE — SD Coding execution handoff

**Cutoff:** 22 November 2026, approximately 15:09 Asia/Riyadh. Prepared at the owner's request. This document is a handoff, not a new test run or a production acceptance.

**ملخص عربي:** الربط البحثي الجديد اجتاز 28/28 اختبار Windows وأُعيد من GitHub. الحسابان A وB مسموحان للبوت التفاعلي، والإعدادات الثمانية محفوظة ومتحقق منها في مخزن مشفر على D. ضبط الساعة طُبّق فعلًا، لكن القياس اللاحق ما زال مرفوضًا. لم تبدأ جولة Binance/Telegram الجديدة، ولا الإشارات الإنتاجية، ولا اختبار 24 ساعة. يوجد أيضًا نقص حقيقي في verifier التأهيل العلمي. المطلوب استكمال هذه البوابات، لا إعادة اختبارات البوتات المقبولة أو طلب تفويض المالك من جديد.

## 1. Verified status at handoff

- **Not ready for qualified production signals or full live E2E.**
- Actual Windows Serve recovery was deployed. Owner logoff/sign-in continuity was observed and correlated with native Security events. The first actual boot recovery FAILED. Later boot fixes passed targeted software tests, but have no successful physical boot/recovery receipt without STOP.
- New durable source/custody/archive/private-query bridge: **28/28 Windows targeted tests PASS**, independently repeated **28/28 from a fresh GitHub source clone**. These tests use fake network transports; do not describe them as real Telegram delivery.
- Eight Telegram fields were actually copied, updated for interactive **A AND B**, and decrypt/readback verified in an owner-private CurrentUser-DPAPI store on D. Original secrets remain unchanged. No plaintext, ciphertext, tokens or account IDs are in this handoff.
- Windows Time tuning was actually applied by the owner from an administrator window. **The subsequent normal-token measurement is still BLOCKED.**
- No new Binance or Telegram API call was made during this work. No new live pilot, market24h, production alert, SQL production write, trading or merge.

## 2. Authority, constraints, and references

Read current GitHub main/MASTER/README and the latest Issue51/77 and PR76/78 before resuming; this is a dated snapshot, not a permanent release pin.

- Official mission: https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/77
- PM two production mismatches: https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/77#issuecomment-7076686518
- Genuine owner private research/Telegram authority used by the pilot: https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-7061701199
- Current engineering report: https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/77#issuecomment-7078844807
- Issue51 report: https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-7078845253
- PR76 parent handoff: https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/76#issuecomment-7078845531

The owner's latest chat explicitly restored **both A/B accounts for the interactive bot**. Do not retain the earlier A-only pilot setting. Main signals retain their separate A/B destination contract; archive C=A. Do not request secrets in chat.

Development and bounded private research authority are already granted. A genuine Windows administrator token is an OS requirement, not a new owner permission question. Do not bypass UAC. No automatic logoff/reboot: coordinate with the owner after saving work. All new project code, logs, caches, temporary files and evidence belong on D; necessary OS settings on C are authorized. GitHub is the authoritative durable project repository. Upload permitted redacted artifacts and verify independent readback; never upload secrets/ciphertext/personal data.

No merge, trading, unqualified directional alert, fabricated calibration or scientific approval. MASTER/README edits remain PM-owned. Preserve 03B3 and do not run it in parallel. Do not rerun previously accepted bot connectivity tests just to increase pass counts. Continue authorized work until an actual technical/external-evidence blocker; do not repeatedly ask for existing permissions.

## 3. Releases and draft dependencies

| Item | Exact snapshot |
|---|---|
| main | `7b7bb0ebdf0bb601cf1f468c0146c784cb8e0a5f`, unchanged by this work |
| Draft PR76 | https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/76 |
| PR76 HEAD | `809a8c19814e48c1ae77984ea216a88d2430b773` |
| PR76 TREE | `22592f3a4e74a6146812fcbd96577d89d2d3394c` |
| PR76 branch | `sd/full-market-normal-worker-20261121` |
| Draft PR78 | https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/78 |
| PR78 HEAD | `0263c7819c3004a91a79563f1f24f47c609b539d` |
| PR78 TREE | `5b506c82613444ccf929f1e73f9943d3f082b9fe` |
| PR78 branch | `sd/ops77-three-bot-bridge-20261122` |
| PR78 base | PR76 branch above, **not main** |

PR76 and78 remain Draft/unmerged. PR78 is a stacked integration change, not a duplicate OPS24 deployment. No CI checks were reported on PR78 at the last query; do not claim CI PASS. PR75 governance was not modified. Do not create duplicate implementation PRs.

## 4. Local paths

| Purpose | Absolute path |
|---|---|
| PR76 development tree | `D:\ZS-SMART-GATE\validation\OPS24-20261121-source` |
| Pinned deployed809a8c1 source | `D:\ZS-SMART-GATE\validation\OPS77-boot-fix-source-20261122` |
| PR78 development tree | `D:\ZS-SMART-GATE\validation\OPS77-three-bot-source-20261122` |
| Fresh GitHub PR78 clone, detached0263c78 | `D:\ZS-SMART-GATE\validation\OPS77-three-bot-github-source-20261122` |
| Final local Windows tests | `D:\ZS-SMART-GATE\validation\OPS77-three-bot-final-tests-20261122` |
| Final GitHub-source Windows tests | `D:\ZS-SMART-GATE\validation\OPS77-three-bot-github-final-tests-20261122` |
| Evidence publishing checkout | `D:\ZS-SMART-GATE\validation\OPS77-s4u-evidence` |
| Evidence branch | `evidence/ops77-s4u-auth-20261121` |
| Independent evidence readback clone | `D:\ZS-SMART-GATE\validation\OPS77-s4u-evidence-readback` |
| Python3.12.10 | `D:\ZS-SMART-GATE\runtime\python-3.12.10-ops77\python.exe` |
| Owner Telegram secret store | `D:\ZS-SMART-GATE\secrets\telegram-owner-20261122` |
| First actual Serve root,2f39c1b | `D:\ZS-SMART-GATE\ops77-serve-recovery-20261122` |
| Improved Serve root,809a8c1 | `D:\ZS-SMART-GATE\ops77-boot-fix-recovery-20261122` |
| Clock tuning/rollback records | `D:\ZS-SMART-GATE\ops77-clock-tuning-20261122` |
| Old installed checkout, do not overwrite | `D:\ZS-SMART-GATE\repo`, HEAD25210a1... |

Tests require inbox Windows PowerShell5.1. `pwsh` is not necessarily on PATH. Codex's current directory on C is not a repository: always specify a D workdir.

## 5. PR76 implementation completed

1. Production task registration uses the dedicated nonadmin **Password/LeastPrivilege** profile instead of S4U. Credential handling validates owner-private DPAPI and worker SID; passwords are never process arguments or public artifacts. Scheduler stores its protected credential.
2. Serve **and market children** use `ReleaseClock`, binding HEAD/TREE/mapSHA/ACL. Native catalog verification covers all five binaries including auto-Valid ones; map/release drift is refused even on cached access. Actual observation reuse up to20s is documented; cached reads are not new independent samples.
3. `DEPLOYMENT_RECOVERY_NO_MARKET_V1` runs actual Serve with hard zero Binance/Telegram/SQL. Market children refuse this scope. It does not admit public market mode or bypass its source/G3/release gates.
4. SQLite WAL/FULL append-only lifecycle journal, singleton, actual PID/session/boot observations, STOP and abnormal-prior-session detection. Do not infer a physical power outage from an ungraceful prior process.
5. After the first boot failure: one-minute BootTrigger delay, bounded60s Windows boot observation instead of10s, explicit subprocess timeout/failure HOLD, sanitized persistent handling for previously uncaught ordinary exceptions. **Exact original boot exception was not captured; timeout is not a proven root cause.**

Entry points: `scripts/ops24-windows.ps1`, `ops24-install-recovery.ps1`, `ops24-recovery-audit.ps1`, `ops24-worker.py`; modules `ops24_release_clock.py`, `ops24_recovery.py`, `ops24_normal_clock.py`.

809a8c1 had14/14 targeted Windows tests and GitHub reproduction. Earlier2f39 had16/16. Do not rerun the old accepted standalone Health without a new defect.

## 6. Actual lifecycle evidence and current task state

- Original c7d11d8 scheduled normal-token Health passed; actual2f39c1b Serve ran session0/normal token. These are physical Windows receipts, not mock tests.
- Owner logoff/sign-in: Security4647 at **10:43:20Z**, then4624/type2 at **10:43:36Z** on22 November, correlated with unchanged PID24736 and Serve session.96 hash-verified journal rows/95 heartbeats across the compared interval. Scope: sign-out/sign-in continuity. No Security4634 was captured; do not claim it.
- First physical reboot: boot11:04:44Z; task tried11:04:55Z and exited1. No postboot heartbeat. SQLite quick_check was ok. **REBOOT_AUTORECOVERY_FAIL**, not PASS.
- A later diagnostic launch used standard credentials in **session1**, not Scheduler session0; it cannot prove autostart. It was stopped gracefully.
- Improved809a8c1 was installed. STOP was then requested during display troubleshooting. The next reboot occurred with STOP present, so it is **not a successful clean recovery test** of the new version.
- `ZS-SmartGate-OPS24-446c7f3979`: Disabled.
- `ZS-SmartGate-OPS24-7ae3882535`: Ready, not Running; STOP_REQUESTED remains. See adjacent `tasks-observation.json` for enabled flags/results/times. Do not confuse Ready with actively serving.
- `ZS-WindowsRunner-Independent-Simulation` and `ZS-WindowsRunner-OneShot-Diagnostic` are disabled. This does not authorize changes to03B3.
- Full physical network-loss/resume, process-crash recovery, STOP/Restore/Rollback and actual24h market soak remain incomplete. Local SQLite tests do not close these physical gates.

## 7. Display incident resolved by owner

The flicker persisted with the runner stopped. Task Manager also flickered. Native window observation did not capture a recurring new visible console; no display-driver crash was established. Win+Ctrl+Shift+B did not fix it. No GPU driver or display registry was removed/changed.

**Owner subsequently confirmed replacing the monitor power cable resolved the issue.** Do not continue GPU changes or attribute the flicker to Codex/the runner/driver as a proven cause. Detected OptiPlex7040/IntelHD530/DELL E2016H details were diagnostic context, not a cause.

## 8. Clock tuning: actually applied, still BLOCKED

Owner ran `ops77-tune-clock.ps1` at HEAD0263c78 from an administrator window. Receipt12:05:05Z/15:05 Riyadh is in adjacent `clock/apply.json`; original settings in `clock/before.json`.

| Setting | Before | Applied |
|---|---:|---:|
| MinPollInterval |6|6|
| MaxPollInterval |8|6|
| UpdateInterval |360000|100|
| FrequencyCorrectRate |4|2|

Source remains `time.cloudflare.com,0x8`. Project limits, source trust and service ACLs were not relaxed. The helper refuses managed/domain clocks and running ZS tasks, snapshots original D records, bounds resync, restores configuration on apply failure, and supports explicit Restore. Microsoft's high-accuracy configuration is not a timing guarantee.

**Final normal-token measurement12:06:59Z/15:06:59 Riyadh:**

- status=`BLOCKED`; blocker=`CONDITIONAL_UNCERTAINTY_UNVERIFIED_OR_HIGH`.
- Conditional uncertainty **3.8480093s**; root dispersion **3.7609734s**; root delay0.0944755s.
- Sync age34.0933237s; four observed offsets approximately within1ms. Small offset alone does not establish bounded uncertainty.
- Unchanged operational policy: uncertainty/offset ceiling0.5s; max step0.05s; max sync age600s; quorum4. The separately versioned prospective V2 bound<1.5s is a different contract; do not reinterpret frozen operational/scientific receipts under a different policy.
- WitnessSHA `1e7c7fa4d6547abdd7b0cd690be722a2ea99bad535fb7c61c3c6f876ea2525dd`.
- Full private witness: `D:\ZS-SMART-GATE\ops77-clock-tuning-20261122\normal-witness-<SHA>.private.json`. The permitted assessment is copied alongside this handoff; private ACL identity material is not published.
- Before tuning uncertainty0.75734775s also failed. Only one post-restart observation was collected. Clock convergence is NOT proven; do not claim tuning solved the issue.
- Source/config RPC still return normal-user AccessDenied; the existing reviewed bounded protected-registry equivalence addresses that separately. The current blocker is dispersion. Independent cryptographic UTC remains NOT_PROVEN.

If SD chooses to restore the prior configuration, after reviewing source/backup and stopping project tasks, run the following **from an administrator window**. Restore has NOT been executed:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "D:\ZS-SMART-GATE\validation\OPS77-three-bot-github-source-20261122\scripts\ops77-tune-clock.ps1" -Head "0263c7819c3004a91a79563f1f24f47c609b539d" -Action Restore
```

Reference: https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/configuring-systems-for-high-accuracy

## 9. PR78 implementation and hard limits

- `stage05_runtime_bridge.py`: concrete verified source replay, LocalOutbox, archive planning, fresh snapshot lookup, private A/B poll/reply, STOP and operational-clock guards.
- Durable `ingress.sqlite` cursor: acknowledge only after local terminal disposition; changed contents under the same updateID fail. A per-poll reply cap leaves later updates unacknowledged. `processed` reports only newly committed updates.
- Unknown sends are not retried after restart. Third-party/cross-account, stale/future messages and stale snapshots are rejected. Distinct A/B accepted-route labels prevent counting two replies toA as proof ofA/B.
- `stage05_delivery.py`: explicit research-test mode refuses signal distribution and labels archive captions TEST. Interactive replies say TEST / RESEARCH ONLY / NOT A TRADING SIGNAL. No invented score or new signal ID.
- `ops77-telegram-pilot.py` and launcher: finite180s private research run, at most6 market attempts/46 Telegram attempts/40 polls. Clean pinned code, exact-head Windows receipts, actual fetched owner decision, current operational clock, private route validation and original public response hashes are required. No new getMe smoke solely to repeat accepted connectivity; current webhook protection is meaningful.
- A local singleton does not prove no remote consumer; real API conflicts remain failures.
- Owner DPAPI store onD was actually verified8/8, with A/B allowlists. Do not rerun its preparer on the same Target: it requires a fresh directory. Original store was not deleted.

**Critical remaining qualification gap:** `APPROVED_REAL_POLICIES`, `VERIFIED_REAL_WITNESSES`, `VERIFIED_REAL_SOURCES` in `stage03_qv1_policy.py` are empty. `VerifiedUpstream.read` concretely admits rejection records only. PR78 therefore does NOT solve genuine QV1 qualification and main-bot production signals remain ZERO. Changing flags or populating registries with unsupported assertions is not a fix. The pilot cannot enable a trade signal via a command-line switch.

A real qualified-source verifier, versioned policy, calibrated/qualified source-witness evidence and the required independent acceptance remain necessary. Implement authorized engineering and evidence qualification, but do not manufacture scientific approval. SCORE_UNAVAILABLE alone is not the explanation for UNKNOWN: source/policy/time/trust gaps are separate.

**Separate operational gap:** the new CurrentUser-DPAPI store belongs to the owner, not the dedicated scheduled worker. No worker secret provisioning or machine-wide encryption was implemented. The launcher is a finite owner normal-token session, not an unattended service deployment.

## 10. Tests and published evidence

Final bridge evidence: https://github.com/scannercrypto0-gif/zs-crypto-signals/tree/ab3303899892b1e6cba9e7086ba396224ec343b6/evidence/OPS77-THREE-BOT-BRIDGE-20261122

Both final runs: **28/28 PASS**,0fail/error/skip/Python-network, Windows11/Python3.12.10/PS5.1:

- `test_stage05_runtime_bridge`:10.
- `test_ops77_bridge_launchers`:2; actual PS5.1 parsing and normal-token refusal before clock writes.
- `test_stage05_operational`:7.
- `test_stage05_real_telegram`:9. Despite its name, network transports are fake in these tests; do not claim real API acceptance.

Independent evidence fetch verified55 manifest file lengths/SHA-256. Original26/26 at0b5acb6 and the8-test unpinned development receipt are retained and labelled; they do not replace final28/28 at0263c78.

Earlier immutable evidence packages on the evidence branch:

| Package | Commit / scope |
|---|---|
| `evidence/OPS77-SCHEDULED-CLOCK-PASS-20261122` | `fdbea690e60c253216de102453ca666124cb4584`, c7d actual scheduled Health |
| `evidence/OPS77-SERVE-V2-20261122` | `3c77cda5cd4c4f56360d0933b95a494468923086`,16/16 at2f39c1b |
| `evidence/OPS77-SERVE-ACTUAL-20261122` | `5911799e5feb2ca01c2c43670f18bbc122373f2c`, actual Serve |
| `evidence/OPS77-LOGOFF-CONTINUITY-20261122` and `OPS77-LOGOFF-CORRELATED-20261122` | `345c8a9bf54f8514741253625c77a16bb29892e3`, continuity/native events |
| `evidence/OPS77-REBOOT-FAILURE-AND-BOOT-FIX-20261122` | `c0e710a5b1924c74c9056513e3344c7a880acadf`, actual FAIL and809 fixes14/14 |
| `evidence/OPS77-DISPLAY-INCIDENT-20261122` | earlier diagnosis before owner identified the cable; preserve history, use final owner resolution above |

Old56/56 market coverage and previously successful three-bot connectivity are inherited historical receipts referenced by Issue77, NOT rerun here and NOT tests ofPR78. Main's00–13 acceptance is bounded engineering; Stage13 mock harness is not real scientific/live E2E validation.

## 11. Uncommitted historical WIP preserved, NOT accepted

`D:\ZS-SMART-GATE\validation\OPS77-integration-source`, branch `sd/stage13-real-source-integration-20261121`, remains unchanged with:

- Uncommitted `stage07_intraday.py` edits and untracked `stage13_real_source.py`, `stage13_context_source.py` prototypes.
- Older untracked development copies of `stage05_runtime_bridge.py` and its test. **PR78 is the newer tested source for these; do not overwrite it with old copies.**

The original prototype bytes and stage07 patch are archived under adjacent `wip-not-accepted/` as non-importable txt/patch files. They were not inserted into executable PR78 code and have no acceptance/test claim. Review and test before any reuse. The patch is recovery material, not an instruction to apply blindly.

## 12. Resume sequence

1. Re-read latest governance and heads; verify clean source, exact pins and normal token. Do not accidentally run a similarly named old checkout.
2. Keep STOP/no active market while solving clock dispersion. Take a small number of bounded, spaced measurements to assess convergence, or actually repair source/configuration. Do not loosen0.5s or infer acceptance from offset alone. Do not issue Binance/Telegram requests simply because clock attempts failed.
3. Only after clock acceptance, use the finite private pilot with exact-head Windows evidence. Coordinate READY before human BTCUSDT queries from A/B; verify each actual account route. Existing bot smoke is not to be repeated gratuitously.
4. Implement/qualify the genuine QV1 verifier and evidence chain. Archive/query research success cannot close production-signal science.
5. Finish worker-identity secret provisioning and actual BOOT/LOGOFF/network/STOP/RESTORE/ROLLBACK, then the24h market soak within its gates. Coordinate owner actions; do not interrupt unsaved work.
6. Publish original permitted receipts, source SHA, tests and manifest; independently fetch/readback; update Issue77/51 and appropriate draft. No auto merge or inflated FULL MATCH.

The following pilot command is **NOT executed** and must not override clock/readiness failure. It is for a normal owner session after all checks, not an administrator window:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "D:\ZS-SMART-GATE\validation\OPS77-three-bot-github-source-20261122\scripts\launch-ops77-telegram-pilot.ps1" -Head "0263c7819c3004a91a79563f1f24f47c609b539d" -WindowsEvidence "D:\ZS-SMART-GATE\validation\OPS77-three-bot-github-final-tests-20261122" -Root "D:\ZS-SMART-GATE\ops77-telegram-private-pilot-20261122-a"
```

## 13. Operator notes

- Never request tokens/chat IDs in conversation; configured secrets already exist. Do not print environment values or credential files.
- A real administrator window may be needed for OS changes; it is not a reason to request delegated permissions again. Prior copy/paste failures concatenated two commands: provide each complete command on its own line, no backtick continuation.
- Git push uses the existing authenticated helper: `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' ...`.
- Per-call commit identity used: `git -c user.name=Codex -c user.email=codex@openai.com commit ...`; do not mutate global Git configuration.
- Use `rg -g '*.md'` rather than passing Windows literal wildcard paths. Do not mix shells for filesystem mutation or delete preserved evidence.
- Stop request is intentionally preserved. No new live session is running for SD to inherit.

**Final state:** `ENGINEERING_BRIDGE_TESTED / CLOCK_BLOCKED / QUALIFICATION_VERIFIER_MISSING / PRIVATE_LIVE_PILOT_NOT_RUN / PRODUCTION_NOT_ACTIVE / NO_MERGE`.
