# ORDER-025 — Owner's private independent replay verification (read-only)

Requires the previously completed **actual** ORDER022 private run directory `D:\ZS-ORDER022-PRIVATE-RUN-001`, containing original `historical-price-only-report.json`, `private-run-receipt.json`, `frozen-experiment.json`, all 12 `verified_5m_archives/*.zip`, `research-results.sqlite` and `verified-restore.sqlite`. It does **not** ingest new market data.

From a checkout of the reviewed ORDER025 **Draft PR** (only after the owner authorizes use of that reviewed code), open «PowerShell» in the checkout root:

```powershell
$env:PYTHONPATH = "src"
py -3 scripts/order025-private-verify.py --private-run-dir "D:\ZS-ORDER022-PRIVATE-RUN-001" --expected-report-sha "985abecf489ea23d1e46f9aace7152df8cf997cd94cce33dde440bdb34cea5ee" --output "D:\ZS-ORDER025-AUDIT-PRIVATE.json"
```

The `--output` path must be **new** and outside any Git working tree. This is one command with no network, market API, download, trading or Telegram.

It verifies the owner's reported report SHA against actual bytes, original private receipt and frozen manifest SHA, source SHA of all twelve original ZIPs, pinned code and setup, replay counts with an alternate predicate/counter independent from `evaluate_rows`, all four original event-list digests (second check with existing evaluator), plus SQLite original/restore table digests. **The ZIP parser is shared with ORDER022**; count logic is independently written, so this is not a source-parser-independent scientific audit.

The new output contains only:
- Four per-symbol/DEV/OOS raw, suppressed, admitted, +12 close up/not-up/missing counts, plus hashes.
- Report and frozen-manifest SHA, contract/protocol SHA, source ZIP **count** verified.
- Explicit `HISTORICAL_REPLAY_PIT_UNVERIFIED / QUALIFIED_FULL_SETUP_NOT_PROVABLE / STAGE05_FULL_HOLD`.

No private raw candles, symbol timestamps, absolute private paths, ZIP files, databases or license-violating feeds are included. Send **the redacted JSON only** to PM/Audit after confirming that release of the summary is permitted by the rights governing the dataset.

A successful run proves the available private bytes are reproducible with both counters and match prior report/hash, **not** that the original market fields were knowable at the past decision time or that any pattern yielded executable net P&L.

If the script returns `AUDIT_BLOCKED`, retain originals unchanged. Common blockers: report hash mismatch, missing ZIP, frozen manifest mismatch, invalid SQLite restore, or code SHA mismatch. Any source/code mismatch needs independent review; never edit original `010-B` or silently recompute a new manifest.

**Existing OOS was already examined.** It cannot be treated as an untouched set for a newly revised hypothesis; ask owner for permission to use a new independent confirmation window or prospective read-only shadow capture *before* looking at outcomes. Avoid claims of calibrated probability/precision or a scientific PASS on owner-only report counts.
