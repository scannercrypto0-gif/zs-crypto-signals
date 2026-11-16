# Stage08 — Swing Structure / Trend, synthetic offline v1

Authority: Issue #51 comments **6909368190** (owner/PM consolidated order)
and **6909724545** (direct SD Coding instruction), 16 November 2026.
Base `main` at implementation start:
`2d2b9ba19174dc0d8286c156eac1167856c88a16`,
`TREE=b5fe8bce9268d6b237dedf39fb65aaffd1b60e10`.

This additive component **does not modify Stage00–07**, does not generate a
qualified `signal_id`, score or trade plan, and does not dispatch to a bot.
Its only accepted source scope is `SYNTHETIC_TEST_ONLY`; caller source labels
and SHA strings are **not** independent exchange authentication. It has no
network, database, scheduling or order capability.

## Input and temporal integrity

`SwingWindow` carries the venue-like `symbol`, UP/DOWN scenario direction,
exactly one `CandleWindow` 4h parent, **four consecutive 1h components**,
optional contiguous preceding 4h history, optional 8h observation,
optional contiguous closed daily and weekly histories, a manifest SHA256
and source scope. `analyze_swing(window, decision_at=...)` requires:

- One synthetic `source_id` across every supplied bar/receipt.
- UTC-aligned, complete and source-available bars by the explicit decision.
  `received_at >= close_at`, `available_at >= received_at` and
  `available_at <= decision_at` must hold for every used observation.
- History sequences are chronologically ordered without gaps or duplicates;
  final preceding 4h history must meet the parent 4h open exactly.
- The four 1h children exactly cover the 4h parent with equal opening,
  closing, extrema and separately measured BASE and QUOTE volume totals.
  Equality tolerance is **zero for synthetic fixtures**, not an adopted
  real-exchange tolerance.
- No higher-timeframe context closing after the parent event is eligible,
  even when the decision happens later. Optional daily and weekly data are
  never guessed, and unknown maximum-age policy is not invented.
- A missing optional 8h observation is `UNAVAILABLE`; provided 8h must
  span a UTC 8h-aligned interval, have source-available completion,
  and equal the aggregation of the **immediately prior** 4h bar and the
  current parent. The accepted `CandleWindow` duration table is not edited
  to create an implicit 8h candle.

No new live 1h/4h/8h/Binance retrieval is used.

## Pivot and structure policy, not a trading policy

A raw swing pivot has exactly **2 left + 2 right** closed 4h bars:

- `HIGH`: center high is strictly greater than all four other highs.
- `LOW`: center low is strictly lower than all four other lows.
- Any equal high/low within the five-bar window **disqualifies the tied
  candidate** and increments `tie_rejections`.
- A pivot is first **confirmed** only on closing the second right bar.
  Its `first_available_at` is the maximum actually recorded availability
  of all five evidence bars. `pivot_at` is a historical observation timestamp,
  not a claim that the pivot was known at that time.
- Each current 4h bar may cross a **previously confirmed** high/low reference
  with its closing price: UP iff previous close <= pivot high < current close;
  DOWN iff previous close >= pivot low > current close. A wick outside the
  level followed by a close back inside is `WICK_ONLY`, never a structure
  break. The same confirmed pivot is consumed at most once per direction.
- First close break from `UNKNOWN` state is `INITIAL_BREAK`.
  Subsequent same-side break is `BOS`; opposite-side break is `CHoCH`.
  The state is research structure only, not a qualification or trend truth.
  Event `first_available_at` is the maximum of break-bar, preceding bar
  and pivot confirmation availability, preventing timestamp backdating.
- Recorded pivots and decisions are **append-style immutable snapshots**.
  A later candidate or newly observed right bar never edits an earlier
  hash-bound receipt or turns a prior uncertain pivot into an earlier
  confirmed event. Delayed history may support later reconstruction but
  cannot establish an earlier first-known time.

A minimum of five 4h bars is needed to confirm one pivot. With fewer bars,
the entire source-aligned snapshot may still be a measured observation, but
`structure.status=INSUFFICIENT_HISTORY`. No mandatory arbitrary swing
threshold or higher-timeframe directional alignment is applied.

## Optional indicators and context

All numeric indicators use `Decimal` and **only prior source-available
4h closes plus the current closed 4h parent**; the weekly moving average
never borrows 4h samples. Each descriptor includes source identity,
event close, availability, unit, definition, required and available bars.

| Descriptor | Period, seed and minimum history |
| --- | --- |
| `EMA12` 4h | alpha = 2/(12+1), SMA of first 12 closes seed, minimum 12 |
| `EMA26` 4h | alpha = 2/(26+1), SMA of first 26 closes seed, minimum 26 |
| `RSI14` 4h | Wilder gain/loss, SMA first 14 differences, minimum 15 closes; both zero -> RSI=50, zero loss -> 100 |
| `MACD(12,26,9)` line | EMA12 - EMA26 on aligned observed closes; minimum 26 |
| `MACD(12,26,9)` signal | EMA9 of MACD line with SMA of first 9 MACD observations seed; minimum 34 |
| `50-week MA` | SMA of **50 consecutive fully closed, available weekly close values**, minimum 50 |
| daily and weekly context | latest observed closed 1d/1w close only, with exact source timestamps; minimum 1 |

The result explicitly reports whether the last closed 4h candle agrees
with the research direction, how its closing price compares with latest
known daily/weekly closes, and whether inferred 4h structure state agrees
with the input direction. Conflicts remain `CONFLICTS` or `UNKNOWN`, not
hidden, weighted or resolved as a trading gate. Missing features have
`INSUFFICIENT_HISTORY`, null value and auditable provenance.

## Retrospective outcomes are independent

`retrospective_swing_observation` requires an internally SHA-bound
research snapshot and **separately supplied future** closed, available 4h
candles. It rejects decision-straddling bars, invalid source, gaps and
future/unavailable receipts. The reference is the **original decision's
4h close**; the first fully eligible future 4h bar starts at the next
UTC 4h boundary. Missing its initial interval is censored, not silently
counted as continuous observation. The result is a descriptive close
return, not a forecast, stop/target hit, executed fill or trade.

## Minimal synthetic baseline and counterexamples

- Baseline: candle open-to-close directional sign of the current 4h parent.
  Research alternative: confirmed non-repainting structural state after
  close-breaks. The `compare_synthetic_structure` function counts agreement,
  disagreement and unavailable pairings across at most 128 verified, synthetic
  receipts; it emits **no** prediction accuracy or false-positive rate.
  No unapproved selection rule or weight is implied.
- Counterexample: a locally highest historical bar with only **one**
  subsequent right bar is not a confirmed high at that time. Another
  high that ties it within the two-right confirmation span invalidates
  the candidate. A wick above the level is not a close-break event.
- Tests cover the delayed confirmation, ties, wick-only, initial UP/DOWN
  breaks, `BOS`, `CHoCH`, and future modifications leaving the original
  decision snapshot intact.
- This synthetic comparison is only a deterministic behavioral baseline,
  not a measured false-positive rate, profitability, calibrated trading
  rule, `DEV/OOS`, `Forward` or a scientific edge.

## PM requirement coverage

| Required control | New test evidence |
| --- | --- |
| UP/DOWN and bounded research-only outputs | `test_full_bundle_up_down_no_authority` |
| Source/time/chronology/strict 4x1h | `test_source_mismatch_and_future_receipt_fail_closed`, `test_gap_duplicates_order_and_reconciliation`, `test_utc_alignment_and_missing_history` |
| Complete source-reconciled optional 8h | `test_8h_optional_absent_and_reconciliation`, `test_8h_non_aligned_parent_rejected` |
| Confirmed pivots, ties, delay and nonrepaint | `test_strict_pivot_confirmation_right_two_and_delayed_availability`, `test_tie_rejects_equal_high_low`, `test_nonrepainting_confirmation_and_future_mutation` |
| Close vs wick, BOS and CHoCH | `test_wick_only_then_close_initial_then_choch_down`, `test_bos_after_previous_confirmed_uptrend`, `test_directional_initial_down_break` |
| Indicator warm-up, 50w and 1d/1w | `test_indicator_minimum_history_and_ema_rsi_macd`, `test_weekly_50_not_reconstructed_from_4h`, `test_daily_and_weekly_context_not_inferred` |
| UTC offsets, retrospective separation and censoring | `test_timezone_utc_offset_normalizes_without_changing_snapshot`, `test_outcome_separate_future_source_and_no_trade`, `test_future_initial_gap_censored_not_observed`, `test_tamper_research_receipt_outcome_rejected` |
| Non-finite/invalid inputs | `test_nonfinite_and_bad_manifest_fail` |
| Baseline vs structural state | `test_synthetic_baseline_agreement_is_not_predictive_claim` |

## Owner Windows PowerShell 5.1 proof (not run by SD Coding)

**Only on the actual authorized owner PC**, with the approved Python
3.12.10 environment, run from a clean checkout of the PR branch,
not from `main`. The raw private output stays on `D:`:

```powershell
$ErrorActionPreference = "Stop"
git fetch origin
git checkout sd/stage08-swing-structure-20261116
git pull --ff-only
$head = (git rev-parse HEAD).Trim()
$tree = (git rev-parse 'HEAD^{tree}').Trim()
$dir = Join-Path 'D:\ZS-LOCAL-CI' ("stage08-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -p test_stage08_swing_structure.py -v 1> (Join-Path $dir "stdout.txt") 2> (Join-Path $dir "stderr.txt")
$exitCode = $LASTEXITCODE
"HEAD=$head"
"TREE=$tree"
"EXIT=$exitCode"
Get-FileHash (Join-Path $dir "stdout.txt") -Algorithm SHA256
Get-FileHash (Join-Path $dir "stderr.txt") -Algorithm SHA256
```

Provide **actual** HEAD/TREE, test count, EXIT and both SHA256 digests.
Author-written tests are **not** evidence of successful execution. This
chat has **no access to the owner's Windows machine**; the execution
status is `BLOCKED_NO_OWNER_WINDOWS_ACCESS`. No accepted Stage00–07
suite is rerun. Hosted CI status must be reported accurately and
branch-protection/review rules respected.

## Release boundary

This is a **Draft PR** for PM inspection, not accepted engineering and
not an authorization for merging, production, live Binance/Telegram,
new one-shot sessions, SQL provisioning, real scoring or trading.
Any governance document updates are PM-owned and not included in
this Stage08 coding PR.
