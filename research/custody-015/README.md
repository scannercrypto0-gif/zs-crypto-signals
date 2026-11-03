# Order015 GitHub-only custody migration

**Update after initial partial delivery:** the owner approved consolidated
48MiB capacity. See [completion and retrieval instructions](capacity-approval-015.md)
and `aggregate-anchor.json`. The initial 10MiB snapshot described below is
preserved historical evidence; the new supplement fills its raw capacity gaps.

Owner order: Issue25 comment6599386155. Governance baseline: main
`83c6f22b0d5392867426971c38e2b802b26ab32d`, MASTER v1.30.

## Immutable retrieval anchors

Evidence branch: `evidence-migration-015`; receipt commit:
`b871fdcc36824e8a3871c5c589290b0a367b8889`.
`anchor.json` pins the Stage04 manifest and archive hashes. The dedicated evidence
tree contains accepted Stage04 claims, receipts, capacity index and manifest.
Claims were committed and remotely read back before artifact receipts were
committed. A Git tree batch is used for this one-time connector migration; it
does not activate a runner, source or reusable live storage service. Journal
timestamps record executor assembly, not independently attested publication.

The lossless gzip/tar archive is split into bounded base64 transport records.
This does not divide a study to evade its cap: all chunks and journal overhead
are counted together, 10,308,600 bytes, below 10,485,760. Every original byte is
SHA-256 verified, with duplicate paths mapped to one object. Expanded original
bytes total 21,996,241; compression is explicitly recorded, not hidden.

## Retrieve without the owner's computer

1. Check out this code PR at its pinned head.
2. Independently check out the evidence receipt commit into `github-evidence`.
3. Set `PYTHONPATH=src` and execute:

```text
python scripts/restore-custody-015.py --snapshot github-evidence --destination restored-from-github
```

No D drive or owner C directory is used. Network is disabled inside the restore
process. The clean Ubuntu Actions workflow performs these exact two GitHub
checkouts; artifacts with expiring retention are not the permanent evidence.

`restored-from-github/inventory.json` is the comprehensive per-file matrix:
684 paths, original SHA-256, original byte count, disposition, license decision,
review state and GitHub container URL. Each included file is stored exactly as
`objects/<original-sha256>`. The common commit and manifest anchors above apply
to every included row. `materialize()` reconstructs a requested historical
relative tree only if every requested member was included. A missing raw input
fails closed; no disk fallback or automatic market re-download exists.

493 paths / 387 unique objects are included. 187 paths are capacity-blocked
raw archives (deduplicated in the inventory), two NTS session files are withheld
for security, and two unnecessary server certificates are replaced by the
existing sanitized certificate-fingerprint/hostname report. No exporter secret
was stored or uploaded. Historical absolute locators remain historical evidence,
never future execution defaults. Historical tools are unmodified opaque audit
copies; future research entry points in `scripts` accept explicit temporary paths.
The deployed Windows Runner and 03B3 experiment are not modified or invoked.

`github-start-presence.json` is an additive, per-SHA classification overlay from
GitHub trees before migration: 176 paths already existed in main/PR snapshots,
508 were local-only. Apply GITHUB_PRESENT_VERIFIED to matching inventory rows;
the remaining rows retain the original transfer classifications. The overlay
lists exact original GitHub ref/path pairs. Historical operational Windows
deployment defaults remain archived; they are not invoked by these workflows
and are not a fallback custody location.

`scripts/custody-migration-build-015.py` and `custody-presence-015.py` preserve the
one-time migration assembly implementation, including its explicit temporary
`incoming/portable` scratch layout. They are not the retrieval interface and
cannot reconstruct withheld source bytes. Use `restore-custody-015.py` for
future verification. The migration builder deliberately fails if original
input bytes or the full hash inventory are absent; no disk/network fallback.

## Rights and scope

Binance Vision data and applicable derived research outputs are attributed to
Binance Vision, governed by CC BY-NC-SA 4.0 for noncommercial research. This
license also applies to the four representative monthly archives and applicable
derived research objects; it does not silently relicense the application code.
See https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md
and https://creativecommons.org/licenses/by-nc-sa/4.0/ .
Tardis terms clauses9.1/9.6 permit internal Customer User/cloud storage; no raw
Tardis bytes were uploaded under this capacity budget, and no external data
redistribution is authorized. Only non-reconstructable research summaries are
retained. Reviewer eligibility must be verified before any raw Tardis release:
https://docs.tardis.dev/legal/terms-of-service .
Original PyPI wheels retain their dist-info license/notice files. CI uses a
separate pinned SHA-256 wheel lock for Windows/Ubuntu Python3.11/3.12, with no
dependency cache and no skipped crypto tests. The existing native Windows API
timezone test is explicitly NOT_APPLICABLE on Linux; its one skip is allowlisted
by exact test ID and reason. It executes on both Windows matrix jobs. All other
skips fail CI, including any skipped NTS test. No dependency credentials
or package-registry secrets are required.

## Acceptance limits

`GITHUB_ONLY_CUSTODY_PARTIAL_WITH_BLOCKERS`, never FULL_REPRODUCIBLE. The restore
reproduces four existing January archives (186/1488 rows for each asset) and a
deterministic synthetic bounded-inference vector; this is not a new DEV/OOS
market qualification. Full six-month replay and historical liquidity replay
remain blocked by missing raw custody. Prior frozen SHA identities are preserved
in exact original reports/code snapshots, not rewritten.

Stage04 integrity is APPLICATION_ONLY; no WORM, immutable server history or
independent UTC claim. Scientific state remains PIT_FAIL_HOLD,
FULL_V2_UNAVAILABLE, NO_QUALIFIED_SIGNAL, FORWARD_NOT_ARMED. No main merge,
MASTER/README edit, live probe, paid service, trading or Telegram production.
PM1.3 independent acceptance is pending.
