# ORDER-025 — Github-only custody for the ORIGINAL 010-B archives

**Status: PREPARED ONLY. NOT UPLOADED, NOT A REAL-DATA CI PASS, NOT SCIENTIFIC QUALIFICATION.**

Owner decision: GitHub is the primary development and verification environment. This does not overrule source licensing, source publication-time PIT, or Stage05 hold.

## 1. Verified repository facts (2026-11-05)

GitHub repository `scannercrypto0-gif/zs-crypto-signals` returned `visibility=private` via the connected GitHub API and the owner account has admin access. The uploader and manual workflow **re-query GitHub visibility** and refuse to proceed when it is not `PRIVATE`. Do not switch visibility to public while raw source is retained: GitHub makes code, releases, Actions logs and historical contents accessible according to public-repository rules. Restrict collaborators, fork access and third-party integrations; require MFA. The previous private dataset is **not automatically visible to this tool or to Actions** merely because the repo is private.

Existing accepted `main`: `05ced43dcfbc476a60030283004503945be82120`. The ORDER025 independent arithmetic verifier lives in still-DRAFT PR #37, HEAD `22280bd884140b0199fa495d13cadb50ce6b844e`. This custody PR is stacked on PR #37 until both receive independent reviews/owner merge approvals. Workflow dispatch requires the workflow file on the default branch: **no real-run claim before merge and actual owner upload**.

## 2. License gate — must be confirmed before uploading

[Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md), version 1.0 dated 2026-08-26:
- `CC BY-NC-SA 4.0` with additional Binance obligations; clause 3.4 excludes commercial use without written enterprise agreement.
- Clause 4.1 permits purely personal non-production backtesting and noncommercial research. Clauses 4.2–4.4 restrict commercial/live signal distribution, hosting/data feeds and integrations.
- Clause 1.4 states rights for already-downloaded data relate to the terms in force **when downloaded**. Establish original acquisition date and applicable terms; current online terms alone do not prove rights to upload the 010-B originals to third-party GitHub infrastructure.
- A PRIVATE GitHub repository restricts access but does **not automatically grant hosting rights**. Owner must confirm noncommercial research, legitimate transfer/storage under applicable terms (legal review or documented authorization if necessary), collaborators and no commercial distribution **before passing `--rights-reviewed`**. Do not take the flag as a legal opinion or a license grant.
- Keep attribution and required noncommercial/share-alike notices for any permitted sharing of derivatives. Do not publish raw archives, derived real-time feeds, or unlicensed derived contents.

**If hosting rights cannot be confirmed, STOP at offline `preflight` and retain bytes on Windows.** No upload, no automatic workaround.

## 3. Storage model and security boundaries

Use a *PRIVATE GitHub Release* on the **already private repository**, tagged `order022-private-010b-2025-v1`. Release assets are not committed to `main`, any source branch, Git LFS or a PR. Only authorized repository collaborators can access assets while repository access remains private. One owner upload is sufficient; release is never overwritten on retry.

The release includes **original unmodified bytes** of 12 `BTCUSDT/ETHUSDT-5m-2025-01..06.zip`, the old 010-B `manifest.json` and `dataset-index.json`, original `frozen-experiment.json`, `historical-price-only-report.json`, `private-run-receipt.json`, `research-results.sqlite`, `verified-restore.sqlite`, plus optional existing small metadata and a fresh `asset-index.json` containing only SHA-256, size, scope, report/protocol references, not market rows. A final `transfer-verification.json` proves the uploader **downloaded these exact assets BACK from GitHub and rehashed them**.

**GitHub Release assets are access-controlled, not cryptographic WORM or a substitute for independent backup.** Admins may delete/replace releases; the source/receipt SHA values detect later changes, and owner retains the original Windows copy. Reducing retention is not a license loophole. Do not publish a release link to outsiders. Unlike limited-life Actions artifacts, release assets remain until deleted; billing/quotas and platform acceptable-use requirements apply. The uploader refuses an already existing evidence tag and does not overwrite.

Maximum historical ZIP validation cap: **12 MiB each × 12 = 144 MiB** total compressed source, actual byte count measured from the files. SQLite/evidence caps: 128 MiB/file. Allow up to **~1 GiB additional free space** on owner and Actions runner for download/hash and restore; do not treat this as a measured dataset size. GitHub storage/Actions/bandwidth cost must be checked against the owner's plan before upload; no cost figure is fabricated. Only GitHub traffic, **zero Binance market requests**.

## 4. One owner copy/paste step (after independent approval and checkout)

Prerequisites: original D: files unchanged; local completed ORDER022 replay at `D:\ZS-ORDER022-PRIVATE-RUN-001`; the reviewed/merged scripts available in local repo; `Python 3.11+` and authenticated `gh` GitHub CLI on the owner's PC. Owner confirms legal private hosting rights **before** using the rights flag.

From repository root in PowerShell:

```powershell
$env:PYTHONPATH = "src"; py -3 scripts/order025-github-custody.py upload --original-root "D:\ZS-SMART-GATE\evidence\science-010B" --private-run-dir "D:\ZS-ORDER022-PRIVATE-RUN-001" --rights-reviewed
```

It will: recheck repo PRIVATE; require old exact manifest SHA `45116717abe2ddda7d906ab5bf97a5507a39720c64fbbd175e7daf2c4e67c738`, original dataset-index SHA `ce0a3716f24612ea04427b12454e420f9f7e10a0a9bedd622c0ac866a372da79`, and all 12 source archive byte hashes, unchanged by ORDER022 staging; verify report SHA `985abecf489ea23d1e46f9aace7152df8cf997cd94cce33dde440bdb34cea5ee` and frozen manifest/protocol/engine chain; upload only after all checks pass; re-download the private release and rehash **all** assets before asserting `OWNER_PRIVATE_GITHUB_TRANSFER_BYTES_VERIFIED`. If any check or upload fails, status remains BLOCKED; a partial private release must be reconciled manually, **never** overwrite source records silently.

For a non-uploaded check, run the same script with `preflight` instead of `upload`, omitting `--rights-reviewed`.

## 5. Real GitHub Actions run — separate explicit owner action

Only **after** code review/owner merge AND verified owner upload, manually run the workflow [`025-real-private-replay.yml`](../../.github/workflows/025-real-private-replay.yml) from GitHub → Actions → `ORDER-025 REAL private 010-B archives — manual only` → Run workflow on `main`. Confirm the checkbox that rights/private-custody prerequisites were reviewed.

The workflow is deliberately `workflow_dispatch` **ONLY**. It must never load private original assets during a PR or an untrusted fork execution. It:
1. Checks repository identity, visibility `private` and `main` ref, with `GITHUB_TOKEN` read-only access.
2. Downloads only original owner-uploaded assets from the fixed private release; independently validates the 12 SHA256 ZIPs, old manifest/index SHA and full asset index. Never downloads Binance sources.
3. Recreates local temporary `verified_5m_archives` and executes the already reviewed `scripts/order025-private-verify.py` on **actual archived market bytes**. The second counter shares the original CSV parser; do not claim fully independent provenance or market publication time.
4. On success, uploads only `audit-redacted.json` and `audit-receipt.json` as short-retention GitHub Actions artifacts. A separate write-scoped job then creates a **unique private release tag for this run** `order025-private-audit-RUNID-ATTEMPT` containing only those two small files and checks their SHA. The raw ZIP/database never go into artifacts, logs or Git commits; they stay in the original restricted release and temporary runner disk.
5. On failure, performs **no results-release publication**, keeps Stage03 OPEN and retains failure logs without raw rows. Any output from synthetic PR CI is not evidence of genuine archived market results.

The status on successful replay is `PRIVATE_OFFLINE_ARITHMETIC_REPRODUCED`, **not** `HISTORICAL_PIT_VERIFIED`, `SCIENTIFIC_PASS` or `QUALIFIED_SIGNAL`. Missing original `bid/ask/24h` + publisher/independent receipt authority still blocks full Stage03 science. Stage05 stays `FULL_HOLD`; no trading or Telegram.

## 6. Acceptance gates for owner and PM

- `PRIVATE_REPO_VERIFIED`: direct GitHub API was private; **PASS at preparation**; enforce again during upload/run.
- `LICENSE_HOSTING_RIGHTS_REVIEWED_BY_OWNER`: **BLOCKED** until actual owner confirmation.
- `ORIGINAL_12_ZIP_SHA256_TRANSFER_MATCH`: **BLOCKED** until owner upload and re-download receipt.
- `REAL_010B_ACTIONS_REPLAY`: **BLOCKED** until workflow merged/owner manually dispatched after upload.
- `REDACTED_GITHUB_EVIDENCE_SAVED`: **BLOCKED** until successful real workflow creates artifacts/release.
- `HISTORICAL_PIT_AND_FULL_QUALIFICATION`: **BLOCKED** regardless of transfer while historical book/24h/receipt evidence is absent.

Existing D1–D5 decisions, 12 normalizers, `N_REQUIRED`, untouched forward validation and Stage05 stay under separate scientific review and owner approval.
