# ORDER007 — Windows-local release and original UP/DOWN evidence (bounded engineering handoff)

Date: 18 November 2026. Binding authority: PR71 issue comments
6972514747 (amendments 007-A and 007-B) and 6975634280.

**This is executable engineering code, not successful Windows installation or
scientific market acceptance.** The owner has not supplied computer-control
access to this GitHub coding session. Exact final PR HEAD/TREE is to be
verified in the PR handoff comment after all source commits.

## Files and scope

- `scripts/order007-windows.ps1`: `Install`, `Verify`,
  `StartForeground`, `Status`, `Stop`, `Disable`, `Uninstall`,
  `Restore` and `Rollback`. Versioned `installed.json` with Git
  HEAD/TREE and Python **3.12.10**. Installation always **DISABLED**.
  No Windows scheduled task or service creation and no unattended launch.
- `scripts/order007-shadow.py`: one bounded, stop-aware, foreground,
  public-read-only invocation of existing Order006 marketwide capture,
  SQLite cursor, time checks and process-tree watchdog (120 seconds).
  `Stop` requests cancellation before the next public GET; an in-flight
  request has a timeout. No 24/7 claim. Any incomplete source/time/policy
  returns a truthful partial/block, not a qualified `sig-`.
- `src/zs_smart_gate/order007_original_source.py` and
  `scripts/order007-original-capture.py`: two-symbol maximum per
  manually invoked capture; original `exchangeInfo`, 24h ticker, book
  and 22×5m + 30m/1h/4h requests. Bounded GET, weight, byte and
  time limits are inherited from `PublicCapture` (`MAX_REQUESTS=11`,
  `MAX_WEIGHT=140`, observed IP guard `5500`, deadline `110s`,
  watchdog `120s`). Raw original payloads and locally verified
  SHA256 records stay on D. Captures can be late, ineligible, gapped
  and clock-unverified and are clearly classified as such.
- `src/zs_smart_gate/order007_science.py` and
  `scripts/order007-science-intake.py`: verify private packet hash,
  source version, symbol/event uniqueness and `UP/DOWN` source admission;
  emit a sanitized dataset ID, per-direction counts, missingness/rejection
  and **SCIENCE_NOT_APPROVED**. Does not touch OOS/forward, backfit costs,
  invent real positives or populate policy registries.
- `scripts/order007-windows-acceptance.ps1`: full suite in Python
  3.12.10 with exact source HEAD/TREE, raw stdout/stderr bytes and
  SHA-256, real EXIT/count/skips, Git clean tree/fsck and restore
  readback. Receipts remain on D.
- `tests/test_order007_release.py`: new deterministic offline
  guard tests. **Authored != executed**.

## D: custody and release structure

```text
D:\ZS-SMART-GATE\
  repo\                  # pinned Git commit; no untracked code
  .venv\                 # Python 3.12.10 virtualenv
  config\                # private operator configuration
  state\installed.json   # release HEAD/TREE; installed disabled
  state\DISABLED
  state\marketwide-cursor.sqlite
  data\shadow-*\         # raw read-only market and clock source receipts
  data\original-*\       # private original multi-asset market payloads
  outbox\                # local only, never external delivery
  logs\
  temp\
  cache\
  backups\
  validation\PR71-*\     # raw Windows stdout/stderr, test receipt, restore
```

Windows-owned operating-system Task Scheduler/Time Service metadata
may live on C, but this package does not create scheduled tasks or
change Windows time configuration. A project-owned file or log is not
allowed on C. The installer refuses a non-D root and reparse paths.

## Owner Windows commands — all project artifacts on D

Start from **Windows PowerShell 5.1**, with Git and Python 3.12.10
already installed. The PR handoff provides the **exact final** HEAD/TREE.
The full command block there pins the source, installs disabled,
verifies and performs the Windows-only full suite. If dependencies
used by historical tests are missing, the exception is captured in
the actual stderr; use the previously approved, verified D-only
dependency staging path via `-ExtraDependenciesPath` rather than
unreviewed network installation. Do not install GitHub Actions runners.

After the final Windows test, separate optional operator-invoked
research-only foreground commands are:

```powershell
$root = 'D:\ZS-SMART-GATE'
& "$root\repo\scripts\order007-windows.ps1" -Action Status
# Only when deciding to perform a read-only bounded diagnostic:
& "$root\repo\scripts\order007-windows.ps1" -Action StartForeground -LiveReadOnly
# Separate source collection, up to two symbols, only when public
# market and bandwidth use are desired; stop if source/clock unverified:
$stamp = Get-Date -Format yyyyMMdd-HHmmss
$env:PYTHONPATH = "$root\repo\src"
& "$root\.venv\Scripts\python.exe" -B "$root\repo\scripts\order007-original-capture.py" --live-read-only --symbols BTCUSDT,ETHUSDT --output "$root\data\original-$stamp"
& "$root\.venv\Scripts\python.exe" -B "$root\repo\scripts\order007-science-intake.py" --data "$root\data" --output "$root\validation\science-intake-$stamp.json"
```

The last three commands **are NOT part of package installation or
Windows unit-test acceptance**. They are separate *manual* opt-ins for
a public read-only sample and do NOT establish marketwide coverage.
The 22×5m source collector does not magically supply a broad historical
DEV/OOS/forward cohort. Repeat only after examining the actual request
weights and exclusions, and freeze science protocol before OOS.

## Engineering acceptance matrix (status before owner Windows execution)

| Gate | Evidence / exact blocker |
|---|---|
| Branch reconciled with Windows-only main | Two-parent non-force merge; latest main docs/scanner guard preserved; remote workflows removed from release tree |
| Windows package files authored | YES, scripts committed; Windows install **NOT_RUN** |
| Package validation | **PENDING_OWNER_WINDOWS_RUN**, no actual new exit/hashes |
| Real foreground Shadow run | **NOT_RUN_BY_THIS_SESSION** |
| 24h / 288 boundaries | **NOT_AUTHORIZED / NOT_RUN** |
| Original multi-asset 22×5m and MTF data | Collector implemented, genuine new dataset **NOT_COLLECTED_BY_THIS_SESSION** |
| Scientific UP admission | `SCIENCE_NOT_APPROVED`, missing genuine validated split, clock and policy |
| Scientific DOWN admission | `SCIENCE_NOT_APPROVED`, same |
| PIT D1–D5 / 12 normalizers | Unresolved independent scientific policy decisions |
| Windows Time operational policy | `REVIEWED_POLICY_SHA256=None`; clock **BLOCKED** |
| Real 05A/B/05C Telegram, archive, outcomes | **UNAUTHORIZED / NOT_PROVEN**, SQL deferred |
| PR71 engineering merge | **BLOCKED** until final-head Windows raw receipt, PM independent review and branch safety |
| Trading or exchange private credentials | Never authorized |

## Exact next acceptance

Run full Windows suite at the final commit and preserve original
`unittest.stdout.raw.txt` and `unittest.stderr.raw.txt` on D.
Report `tested_head`, `tested_tree`, `tests`, `skipped`, `exit`,
`test_pass`, `clean_worktree`, `fsck_exit`,
`restore_verified` and the two SHA256 fields in `receipt.json`.
PM must independently inspect byte/hash evidence. Under amendment 007-A
the owner permits engineering merge without a new per-merge question
**only if all conditions are actually satisfied**. Scientific/clock,
real destinations and a 24h soak remain independently blocked.

No automatic deployment, GitHub-hosted tests, real Telegram/SQL,
operational GitHub archive sends, production `sig-`, trading or money
movements are performed by this package.
