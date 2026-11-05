# ORDER-025 — Private GitHub custody for the ORIGINAL 010-B archives

**Status: PREPARED ONLY / NOT UPLOADED / REAL-SOURCE ACTIONS NOT RUN / SCIENTIFIC QUALIFICATION NOT GRANTED.**

**Owner amendment (2026-11-05):** [ORDER-025](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6656960128) removes the former hosting-rights signoff and associated uploader/Actions acknowledgement. There is **no hosting-rights flag, workflow checkbox, or additional signoff prerequisite** in this execution path. The amendment does not alter third-party terms or authorize public distribution. Separate owner authorization for merge and one-time private transfer remains mandatory.

## 1. Governance and dependencies

Repository `scannercrypto0-gif/zs-crypto-signals` was verified **PRIVATE** at preparation. The uploader and Actions job both re-check visibility and fail closed unless PRIVATE. Restrict collaborators, forks and third-party integrations, use MFA, and never switch the repository to PUBLIC while the original archives are retained.

Base `main=05ced43dcfbc476a60030283004503945be82120`. The independent arithmetic verifier is in [Draft PR #37](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/37), HEAD `22280bd884140b0199fa495d13cadb50ce6b844e`. This PR #38 is stacked on #37; **merge #37 first only after owner approval**. Then retarget #38 to current main, inspect its actual five-file delta, rerun CI on the updated head and obtain distinct owner merge consent for #38. The real manual workflow must be present on `main`; neither draft PR is a live execution authorization.

## 2. Storage and security

Use a **PRIVATE GitHub Release** tagged `order022-private-010b-2025-v1`. Do not commit original ZIPs or databases into Git, PRs, public workflow artifacts, logs or public releases. The source release is access-controlled but **not immutable/WORM**: the original Windows copy remains retained. An existing tag must never be overwritten.

Store original unmodified 12 monthly `BTCUSDT/ETHUSDT Spot 5m 2025-01..06` ZIPs, original `manifest.json`, `dataset-index.json`, `frozen-experiment.json`, `historical-price-only-report.json`, `private-run-receipt.json`, `research-results.sqlite`, `verified-restore.sqlite`, and optional existing bounded metadata. The new `asset-index.json` lists original SHA256 hashes and measured file sizes only, without market rows or absolute host paths. After uploading, download every asset back, rehash against the index, and publish `transfer-verification.json` as the **mandatory completion receipt**. The real replay **rejects** a missing, invalid or symlinked completion receipt, unexpected files, wrong sizes and wrong hashes. Partial releases require manual reconciliation; never silently overwrite or declare success.

Each compressed ZIP is limited to 12 MiB (12 files = at most 144 MiB). Individual evidence files are capped at 128 MiB. Plan for at least ~1 GiB private temporary space, verify available GitHub storage/bandwidth/Actions quotas and access settings before any authorized transfer; no measured costs are claimed. This custody route makes **zero Binance market requests**.

## 3. One-time source upload — only after owner merge and transfer authorization

Prerequisites: approved code merged and available on the owner's PC; original `D:` files unchanged; original completed replay at `D:\ZS-ORDER022-PRIVATE-RUN-001`; a functioning `Python 3.11+`, authenticated `gh` CLI, permitted private release write access, restricted collaborators and sufficient storage quotas. Owner explicitly authorizes this separate private data transfer. No public release or new source download.

From the checked-out repository root, the **updated command without any hosting-rights flag**:

```powershell
$env:PYTHONPATH = "src"; py -3 scripts/order025-github-custody.py upload --original-root "D:\ZS-SMART-GATE\evidence\science-010B" --private-run-dir "D:\ZS-ORDER022-PRIVATE-RUN-001"
```

For a non-uploading dry verification, use `preflight` instead of `upload`. The uploader checks the original manifest SHA `45116717abe2ddda7d906ab5bf97a5507a39720c64fbbd175e7daf2c4e67c738`, dataset-index SHA `ce0a3716f24612ea04427b12454e420f9f7e10a0a9bedd622c0ac866a372da79`, all 12 original ZIP hashes, frozen protocol/engine/Setup and original report SHA `985abecf489ea23d1e46f9aace7152df8cf997cd94cce33dde440bdb34cea5ee`. It checks PRIVATE visibility, uploads original bytes once, re-downloads all assets and verifies the SHA/receipt chain. `OWNER_PRIVATE_GITHUB_TRANSFER_BYTES_VERIFIED` proves custody only; NOT scientific PIT.

## 4. Real-data GitHub Actions replay — separate owner action

After the merged code and complete source release are verified, the owner manually runs [`025-real-private-replay.yml`](../../.github/workflows/025-real-private-replay.yml) through **Actions → ORDER-025 REAL private 010-B archives — manual only → Run workflow on main**. This workflow has `workflow_dispatch` only, **no hosting-rights input**, no schedule, no pull-request real data access.

The read-only job checks repository identity, `main` ref and PRIVATE visibility; downloads only the previously uploaded private source release; requires the final `transfer-verification.json`; independently checks original asset sizes/hashes and executes `order025-private-verify.py` on the real archives in the runner temporary directory. The verification includes the 12 ZIPs, the owner report SHA, four DEV/OOS counter groups, event digest and restored SQLite records. The arithmetic checker shares the original CSV decoder; it is **not** independent provider publication-time/receipt proof.

On success, only `audit-redacted.json` and `audit-receipt.json` enter a 30-day Actions artifact; a separate `contents:write` job publishes those two redacted files in a run-unique **PRIVATE** results release. Raw ZIPs, raw candle rows and SQLite files never go into output artifacts. Failed verification creates no successful result release.

## 5. Acceptance status

| Gate | Status before owner transfer |
| --- | --- |
| Repository PRIVATE and fail-closed checks | PREPARED; recheck at upload/run |
| Source integrity, old SHA and frozen contract | SYNTHETIC CI ONLY; original bytes not yet accessed |
| Owner merge approvals, #37 then #38 | PENDING |
| Owner one-time transfer approval | PENDING |
| Original 12 ZIP GitHub transfer and mandatory final receipt | NOT RUN |
| REAL GitHub Actions source replay / redacted result release | NOT RUN |
| Historical publisher/receipt PIT, decision-time bid/ask/24h | UNVERIFIED |
| D1–D5, 12 normalizers, effective N and untouched forward validation | UNAPPROVED / UNDETERMINED |
| Stage03 scientific closure / Stage05 | STAGE03 OPEN / STAGE05 FULL HOLD |

A successful real-archive arithmetic replay cannot independently prove `HISTORICAL_PIT_VERIFIED`, `SCIENTIFIC_PASS` or a publishable signal. No trading, Telegram, Stage05 unlock, new market downloads, or live data capture are authorized by this PR.
