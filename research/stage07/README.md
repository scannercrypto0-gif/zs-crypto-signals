# Stage07 — Intraday pre-movement research v1

Owner/PM authority: Issue #51 comment 6895007048. Base main at
`2a6fe9f42b4732d8a2885183a28d578d1c140eec`.

This additive module is **research-only, synthetic-only, offline**. It never
publishes, qualifies, generates a signal ID/score, accesses Binance/Telegram,
or changes Stage03/Stage06. No database or private owner artifacts.

Contract: `ResearchWindow` carries a fully closed 30m parent, six adjacent
5m children, at least six adjacent prior 5m candles, and optional two 15m
comparators. Each bar is a `CandleWindow` with explicit source, received and
available timestamps; all must be available by the supplied decision. Parent
and children reconcile exactly for synthetic fixtures. No partial bar is
promoted. A missing history, source mismatch, gap, unavailable receipt or
incomplete comparator returns a nonpublishable UNAVAILABLE reason.

Directional research features include signed return/efficiency, price and
base-volume second differences, base/quote volume changes relative to prior
30m, favorable/adverse wicks and body proportions, favorable gain retention,
pullback, range expansion, directional higher high/higher low (or lower low/
lower high) counts, positive direction body count, volume-price agreement,
early-vs-late momentum, continuation/fade and optional split 15m comparison.
Ratios with a zero denominator are explicitly unavailable. Features report
unit, event close, observed source and availability; any inferred policy
thresholds and weights are deliberately absent. Six green candles and Setup
v1.1 are **not prerequisites**.

`retrospective_labels` is **separate** from feature generation. It accepts
future closed and source-available 5m bars only at retrospective `as_of`,
requires a caller-chosen positive scenario threshold, rejects a bar that
straddles the decision, labels both-direction same-bar hits ambiguous and
caps observations at 24h. Its reference is the first complete future bar's
open, so any lead time is research-only and cannot claim a fill or forecast.
Multiple windows may overlap; not an independent sample claim. A robust
economic/validated alternative is still an external scientific requirement.

## Windows targeted test

Run using the owner's approved `Python 3.12.10` environment on a clean
checkout of this exact branch:

```powershell
$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -p test_stage07_intraday.py -v 1> stage07.stdout.txt 2> stage07.stderr.txt
$exitCode = $LASTEXITCODE
Get-FileHash stage07.stdout.txt -Algorithm SHA256
Get-FileHash stage07.stderr.txt -Algorithm SHA256
"EXIT=$exitCode"
```

Do **not** claim Windows acceptance until the owner supplies actual command
exit code, test count and both log digests. Hosted checks are advisory, but
real branch-protection rules remain binding. Targeted tests are author-supplied,
not independent owner evidence. No accepted Stage00–06 suite is reopened.

## Open scientific work

- This initial deterministic slice does not establish real predictive edge,
  statistical false-positive rate or a representative baseline/ablation.
- The retrospective label is a single earliest-touch candidate outcome;
  per-horizon survival/false-positive/ablation evaluation will need properly
  separated datasets and a new scoped engineering review.
- Provenance is source-labelled synthetic custody, **not** Binance authentication.
- No `MASTER`/`README` changes are proposed by SD Coding.
