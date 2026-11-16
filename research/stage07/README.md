# Stage07 — intraday early-move offline research contract

Authority: Issue #51 comment **6895007048**; PM review PR #64 comment
**6895483352**. This is a synthetic-only, research-only engineering slice.
The owner has **not** authorized real Binance/Telegram, production, trading,
SQL, real signal/score promotion or any merge.

## Temporal contracts

- `evaluate_window`: requires an entirely closed and source-available `30m`
  parent reconciled with exactly six `5m` children. This is a **30m close
  decision**, not evidence of prediction within the unfinished parent.
- `evaluate_partial_window`: explicitly separate **PARTIAL_PARENT_30M**
  research path for **3–5 fully closed and available `5m` children** of a
  still-open `30m` parent, with six prior closed `5m` history candles.
  Parent `30m` is used **only** as a source/timing anchor; no future parent
  price, high/low, volume or later `5m` candle is read. The partial snapshot
  keeps its exact last observed `5m` close, versioned research identity,
  source/availability evidence and frozen reference price. No partial candle
  is re-labelled as a fully closed candle. In particular, this is not
  live/predictive qualification.
- All used `CandleWindow` inputs carry source identity, UTC open/close,
  actual reception and availability. Source mismatch, invalid/tampered SHA
  text, non-finite numerics, missing history, noncontiguous windows, future
  or stale-to-decision observations fail closed. Source eligibility is still
  **SYNTHETIC_TEST_ONLY**, not `APPROVED_REAL_SOURCE`.
- Optional `15m` comparisons for full parents must exactly cover the parent
  and reconcile against the corresponding `5m` halves. Missing comparison
  is an explicit feature-unavailability reason, not invented context.
- No `Setup v1.1` or six-green-`5m` universal prerequisite.

## Features, formulas, and units

Directional sign: `s=+1` for UP, `s=-1` for DOWN. `p0` is opening
price of observed candles and `p1` the last observed closing price.
All calculations use `Decimal`, never an approved score or policy weight.

- Directional return `s*(p1-p0)/p0`, dimensionless.
- Price acceleration: difference of the last two signed consecutive
  `5m` close-to-close changes, quote-price delta per five-minute step.
- Base-volume second difference: `v[-1]-2*v[-2]+v[-3]`, base-asset units.
- Directional movement counts: increasing highs/lows for UP; decreasing
  lows/highs for DOWN, each out of five adjacent pairs.
- Parent candle body and favorable/adverse wick lengths divided by full
  high-low range; undefined zero denominator is `UNAVAILABLE`.
- Return/path efficiency: signed opening-to-close movement over sum of
  absolute child candle bodies, not a trading return.
- Favorable gain retention: signed movement divided by maximum favorable
  excursion; pullback depth: favorable excursion minus signed movement,
  divided by that excursion. Missing/zero excursion is explicitly unavailable.
- Range expansion: current six-child summed high-low ranges divided by
  previous six-child summed ranges; second-half over first-half range.
- Base and quote volume changes compared with an **equal-count prior**
  history window. Quote volume is never inferred from base volume.
- Price-volume agreement: descriptive Boolean of positive signed price
  change and positive base-volume change. Momentum transition and
  continuation/fade are raw signed price deltas.
- Partial mode computes only prefix-valid directional return, equal-length
  volume changes, close acceleration and price-volume agreement, with
  `5m` feature provenance. It never substitutes a full `30m` value.

Zero denominators, unknown sources and unavailable comparator values are
reported; no invented thresholds, weights or scientific acceptance.

## Retrospective labels (not features)

`retrospective_labels` accepts a hash-verified decision snapshot and
separately supplied **future** fully closed `5m` candles. Its reference is
the **last actually available close at the decision**, frozen in the
research receipt. It does not derive the reference from future candles.
The threshold `move_fraction` is caller-selected scenario research,
strictly between zero and one, not a qualification policy.

Each horizon **1, 2, 4, 8, 12 and 24 hours** has its own result with:
horizon end, observed-until timestamp, status, censor reason, examined
count, lead-hours (if unambiguous), and event availability timestamp.
First-touch statuses: `DIRECTIONAL_MOVE_TOUCHED`,
`OPPOSITE_MOVE_TOUCHED`, `AMBIGUOUS_OHLC_ORDER`;
otherwise `CENSORED_GAP`, `CENSORED_HORIZON`, or
`NO_DIRECTIONAL_MOVE` only when a complete horizon is observable.
Same-bar opposite touches are ambiguous; they do not become fills.

The first eligible bar must **open at or after the decision**. Since
`5m` bars are UTC-aligned, the first required whole bar begins at the
next five-minute boundary. A supplied bar straddling the decision is
rejected. A missing initial eligible bar is conservatively censored as a
gap; an incomplete terminal horizon is censored rather than inventing
unobserved time. Rows expose overlap restrictions separately.
`result_sha256` is an internal integrity fingerprint, **not independent
authentication of any exchange or timestamp**.

## Synthetic false-positive research demonstration

`compare_research_candidates` operates on record-label pairs,
deduplicates overlapping **24h** study windows by symbol (conservative),
and reports separate assessment for a fixed descriptive directional-sign
baseline versus price+base-volume agreement. Removing the volume
condition is the indicated ablation. A false positive here means a
selected direction whose first observed event is opposite, or whose
fully observed horizon contains no directional move. Ambiguity, gaps
and censored horizons are excluded from the false-positive denominator
and counted explicitly. Positive events are descriptive touches, not
proof of successful trading.

This deterministic synthetic comparison is **not** a statistical estimate
of real-market false-positive rates or predictive edge. There are no
real-source cohorts, DEV/OOS, forward validation, confidence intervals
or calibrated threshold adoption in this PR. Those remain scientific
work for separate review and authorization.

## PM finding-to-evidence matrix

| PM item | Source/test coverage | Honest limit |
| --- | --- | --- |
| 1. Intra-parent pre-move | `evaluate_partial_window`; `test_partial_prefix_uses_no_parent_future_ohlc`, `test_partial_rejects_future_closed_bar_and_history_gap` | prefix starts at third closed `5m`, not intrabar live ticks |
| 2. Six horizons, censor/overlap | `retrospective_labels`; `test_independent_horizon_censoring_after_first_hour`, overlap comparison test | no outcome on real market observations |
| 3. Frozen reference and gap | snapshot price/receipt, next eligible closed-bar policy; label gap and tamper tests | high/low within one bar have no order |
| 4. PIT/UTC/source/mutation | actual future-only mutation, timezone, partial/source/reconciliation, double-touch tests | all fixtures synthetic |
| 5. False-positive baseline/ablation | `compare_research_candidates`; synthetic true/false/overlap tests | no independently measured predictive accuracy |
| 6. Nonfinite/invalid inputs | source/sha guard and `core.decimal` finite guard; targeted nonfinite test | no real feed attestation |
| 7. Windows verification | command below, pinned SHA/TREE, `stdout/stderr` digests | execution and owner receipt **PENDING** |

## Owner Windows PowerShell 5.1 verification

Run on the owner's actual `Windows` checkout using the approved
`Python 3.12.10` environment, **after** retrieving the exact final PR
head; do not accidentally test `main` or rerun accepted Stage00–06:

```powershell
$ErrorActionPreference = "Stop"
git fetch origin
git checkout sd/stage07-intraday-research-20261115
git pull --ff-only
$head = (git rev-parse HEAD).Trim()
$tree = (git rev-parse 'HEAD^{tree}').Trim()
"HEAD=$head"
"TREE=$tree"
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -p test_stage07_intraday.py -v 1> stage07.stdout.txt 2> stage07.stderr.txt
$code = $LASTEXITCODE
Get-FileHash stage07.stdout.txt -Algorithm SHA256
Get-FileHash stage07.stderr.txt -Algorithm SHA256
"EXIT=$code"
```

Supply test counts, full `HEAD/TREE`, `EXIT` and two raw-log hashes
to PM while keeping raw logs and private owner artifacts on `D:`.
Test authoring, execution on the owner's machine and independent PM
review are separate evidence layers. No test success is asserted merely
by adding tests or publishing this documentation.

## Release boundaries

This PR is a **DRAFT** and requires PM re-review. The owner must separately
authorize exact-SHA merge as applicable. No automatic production, live
source, Telegram routing, SQL or trading.
