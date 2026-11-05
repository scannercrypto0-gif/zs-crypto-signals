# ORDER-022 — one-command private offline import (owner-controlled)

**Reference:** [PM 1.4 approval / Issue #25 #6655440249](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6655440249).
**Scope:** A one-time research-only run **after** access to original 010-B private files has been verified. This is not a permanent Windows runner and not a live Binance experiment.

## Why this runner exists

The old report says 010-B data was retained privately on
`D:\ZS-SMART-GATE\evidence\science-010B`, but the ChatGPT/GitHub
development environment **cannot read the owner's unmounted Windows D: drive**.
A successful GitHub CI is not proof that those private bytes exist now.
We must not invent market data, original arrival times, or actual
Setup v1.1-eligible signals.

The tool checks **existing** 010-B evidence against two recorded hashes:

- Old frozen `manifest.json` SHA256:
  `45116717abe2ddda7d906ab5bf97a5507a39720c64fbbd175e7daf2c4e67c738`.
- Old `dataset-index.json` SHA256 if present:
  `ce0a3716f24612ea04427b12454e420f9f7e10a0a9bedd622c0ac866a372da79`.

Old 010-B `manifest.json` must contain the prior **twelve exact monthly
BTCUSDT/ETHUSDT Spot 5m ZIP SHA256 pins**. The script verifies the original
twelve archived ZIP bytes against those **previously frozen** hashes;
it does not generate new source fingerprints and then claim those
self-generated values are independent evidence. The old `dataset-index.json`
is checked if discoverable; missing index is reported as missing, not
fabricated or replaced. A conflicting index hash is an explicit blocker.

## One command on the owner machine, only after files are present

From a local checkout of accepted `main` (or an independently reviewed
version of this helper PR), open «PowerShell» in the repository root:

```powershell
$env:PYTHONPATH = "src"
py -3 scripts/order022-private-import.py --source-root "D:\ZS-SMART-GATE\evidence\science-010B" --out "D:\ZS-ORDER022-PRIVATE-RUN-001"
```

`--out` must name a **new nonexisting private folder outside any Git
worktree and outside the source directory**. It is *not* uploaded to GitHub.
The script searches locally to depth five for the previous manifest/index
and 12 exact named ZIPs. It does not connect to a network.

It stages 12 SHA-matching ZIPs privately using same-volume hard links when
possible (otherwise local copies), verifies them again, runs coverage/integrity
checks, and **freezes** the dataset-bound experiment manifest before the
first actual DEV/OOS calculation. It invokes the existing ORDER-022 offline
runner unmodified and keeps separate DEV/OOS outputs and an independent
«SQLite» restored copy.

Output is private: `local-010b-catalog.json`, `inventory.json`,
`frozen-experiment.json`, `freeze-receipt.json`,
`historical-price-only-report.json`, `research-results.sqlite`,
`verified-restore.sqlite`, `private-run-receipt.json`, and a private
`verified_5m_archives` directory. Successful return means technical replay,
**not** verified historical PIT, actual execution returns, or a
`DETECTED_SIGNAL` qualified by bid/ask/24h gates.

If a prerequisite is missing, the command returns
`BLOCKED_OFFLINE` with a specific error code, makes **zero** market requests,
and never re-downloads sources. An intermediate failure leaves trace files
in the uniquely named private output; use a **new output path** for any
fresh attempt. Do not edit/overwrite a frozen experiment or re-use
already-evaluated OOS in a different study.

## Minimum owner action if no access can be granted to the executor

Check these files on the owner's actual PC and share **only metadata**
(first), not all raw market ZIPs:

```powershell
Get-ChildItem 'D:\ZS-SMART-GATE\evidence\science-010B' -Recurse -File |
  Where-Object { $_.Name -in @('manifest.json','dataset-index.json') -or
                 $_.Name -match '^(BTCUSDT|ETHUSDT)-5m-2025-0[1-6]\.zip$' } |
  Select-Object FullName,Length
```

This reveals which files are there. The owner may then run the one-command
private helper on their own PC, and share the small **redacted
`private-run-receipt.json` plus partition count summaries** with «PM 1.4».
Avoid posting raw ZIPs, SQLite databases or full private file paths publicly.
If no files exist locally, the proper next decision is recovery from the
original private backup or separate explicit authority for a bounded
historical-only source download, **not** an implicit live permission.

## Scientific and engineering holds

- Original bar timestamps do **not** establish original exchange publication,
  independently synchronized collector UTC or known-at-decision market data.
  `HISTORICAL_REPLAY_PIT_UNVERIFIED` remains.
- Without historical `bid/ask/24h` snapshots, the study returns only
  `PARTIAL_PRICE_VOLUME_PATTERN_NOT_DETECTED_SIGNAL`. Full v1.1
  qualification is **UNKNOWN**, not a zero-market-event claim.
- `setup021` 20/1.20/90s gates are untouched. Real OOS cannot tune them.
- Cost parameters are declared but no executable return is calculated
  without valid time-aligned execution data.
- `STAGE03_OPEN / STAGE05_FULL_HOLD / NO_TRADING / NO_TELEGRAM /
  NO_NEW_BINANCE_GET / NO_PRODUCTION / NO_AUTO_MERGE`.

«GitHub Actions» tests only local synthetic-byte negative cases and an
absent-owner-drive scenario; **not** the actual 010-B market results.
