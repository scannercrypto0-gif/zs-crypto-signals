# PRE_STAGE06_00_05_ENGINEERING_ACCEPTANCE

**Disposition: BLOCKED for Stage06.** Scope follows [owner directive 6873534849](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6873534849). This report preserves the original evidence and the actual limits of each test.

| Stage | MASTER / README requirement | Implementation and verification | Evidence | Status |
|---|---|---|---|---|
| 00 | Windows bounded execution, pinned revision and technical stop | `launch-stage51-final-once.ps1`, `stage51-final-once.py`; clean pinned Windows tests and pre-existing immutable session claim verified. New launch blocked by consumed scope. | [Windows metadata](windows-23.json), [session receipt](../final-003-account-a-retry1/final-manifest.json) | PARTIAL |
| 01 | Public Spot source, bounded inventory, closed inputs | `e2e51.py` live receipt chain. Reused the authorized BTCUSDT sample and pinned later Spot capture. No evidence of complete exchange inventory. | [Live receipt](../final-003-account-a-retry1/final-manifest.json), [Spot capture](../qv1-market-1794400200/market-receipts.json) | PARTIAL |
| 02 | Scanner, frozen Setup and causal decision trace | Existing bounded real rejection chain exercised Scanner/Setup. Stage03 replay independently triggers on the 30m close. | [Live manifest and decision hash](../final-003-account-a-retry1/final-manifest.json), [replay](stage03-replay.json) | MATCH for the bounded previously observed BTCUSDT Scanner/Setup route |
| 03 | R0 identity, R1 exact 30m/six 5m and causal 1h/4h, R2 research results, source and clock binding | Pinned real captured bytes now replay through the existing R0/R1/R2 computation; separate recorded-source scope, exact reconciliation, conditional recorded clock intervals, policy hold, no signal/score. 20 affected tests passed. Missing prior 30m history remains explicit. Live multi-symbol acquisition and a current-head live R2 handoff were not observed. | [Replay](stage03-replay.json), [tests](stage03.stderr.txt), [prior capture and clock](../qv1-market-1794400200/execution-summary.json) | PARTIAL |
| 04 | Durable Windows custody, duplicates, backup, fresh restore, reopen and independent encrypted media | Seven journal tests passed across baseline and targeted correction. Online backup, fresh-path restore and a third Python process reopen passed on this Windows host. SHA pin checked on restore. No qualifying external encrypted device was mounted. Physical or off-device recovery is outstanding. | [Backup](stage04-backup.jsonl), [restore](stage04-restore.jsonl), [reopen](stage04-reopen.jsonl), [Windows tests](windows-fix-final.stderr.txt) | BLOCKED_EXTERNAL_EVIDENCE |
| 05 | 05A silence without qualification, 05B authorized archive to C=A, 05C private real A/B read-only, independent bot identity and dedup | Offline convergence and snapshot suites passed. Existing live chain showed 05A silent, 05B API acceptance and 05C reply binding for A. B remains unobserved in that session. Current R2 reply adapter tested offline only. | [Windows logs](windows-23.stderr.txt), [live trace](../final-003-account-a-retry1/final-manifest.json) | BLOCKED |

## Windows pins and results

- Clean baseline code `61804de9e907c9592094adedfd196289dc6a58c3`, tree `68d43228b6288c4a2b9ebc0d445fb1b23a1d90fa`. 21/23 passed, one failure and one error. The duplicate fixture substituted an identical source hash and the SQL trigger test left a connection open. Corrected the fixture to rehash a distinct valid payload under the same key and closed the SQLite handle before Windows cleanup. The two affected tests passed on `c7b29cae793ee0d4fca9a150769b6a5aca2bbfa0`. Full case coverage is 23/23 across baseline and corrective execution. See metadata for UTC, tool versions, exit codes and raw stdout/stderr hashes.
- Engineering code `1277f8b87da6be1acce363bb68db1b9e90fa416f`, tree `5ddc97e03a57122105b9b6cd66960c614d11eddd`. 20 affected Stage03 tests passed after the adapter change, including the four original universe cases. The pinned real capture independently replayed to `POLICY_HOLD / UNKNOWN`, which correctly preserves the research-only qualification state. The older 5m-discovery result remains historical.
- Local drill backup SHA256 `eb2948aa2c0e7f9deb2133ea1f19ebdc63a3c4562f4ea762179d07869c858ba1`. Backup, restore and fresh process readback matched payload SHA256 `4429b1fce70b4ad27591599eb4e1e2ffaa03c38f16b88913b60ec62b7dbd4018`.

## Live scope and recovery action

The existing FINAL-003 A-retry claim was present on Windows and corresponds to the published trace. The trace records 6 Spot GETs, 7 Telegram API calls, 2 sends, and zero 05A sends. A received an API-accepted reply with reply binding verified. B was outside that executed A-only retry. This execution made zero Binance and Telegram calls and left the claim intact. A fresh A/B integrated live proof requires a fresh bounded session authorization.

Connect an approved encrypted independent Windows backup device to complete the recovery drill. The source and restored journal paths belong on D. Only the explicit backup destination below targets the encrypted device. Verify that its disk number differs from D and that encryption is active before running. Use fresh paths.

```powershell
$env:PYTHONPATH = 'src;tests'
$backup = 'E:\\zs-pre06-drill.db'
Get-Partition -DriveLetter D,E | Select-Object DriveLetter,DiskNumber
Get-BitLockerVolume -MountPoint 'E:' | Select-Object VolumeStatus,ProtectionStatus
py -3.12 scripts/drill-stage04-windows-recovery.py backup D:\\zs-drill-source.db --backup $backup --external
# Save the emitted SHA separately, then remount the encrypted medium.
py -3.12 scripts/drill-stage04-windows-recovery.py restore D:\\zs-drill-restored.db --backup $backup --pin '<saved SHA256>'
py -3.12 scripts/drill-stage04-windows-recovery.py verify D:\\zs-drill-restored.db
```

## Governance and stack

[Docs draft #59](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/59) adds the same owner clarification to MASTER and README atop main. Deferred after complete system build: real qualified signal occurrence or delivery, predictive accuracy, profitability, OOS/Forward edge, numeric N01/N02/N04/N03/SEM qualification calibration. Continue to veto unqualified 05A dispatch. Preserve recovery and source-integrity obligations.

[PR #53](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/53) and [#54](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/54) are based on main. [#55](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/55) is based on #54, [#57](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/57) on #55, and [#58](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/58) on #57. Review #53/#54 contract overlap before accepting #54, then review #55, #57, #58 in base order. #58 standalone Round 2 is distinct from FINAL-003. No merge or Stage06 start.
