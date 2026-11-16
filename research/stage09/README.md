# Stage09 — Fixed-Range Volume Profile / POC / VWAP + Research Levels

Owner/PM authority: Issue #51 comment **6910753333**, 16 November 2026.
Source of scope: current `ZS_SMART_GATE_MASTER.md` and root `README.md`
on `main`. Fresh inspected baseline:
- `main HEAD=908b144be216c9b1f86203ea66844d1b5f462f91`
- `main TREE=ba547a3c1bd6caf52233ebe7b6efa63671c7f6c3`

This new independent `zs.stage09.fixed-range-levels.v1` contract is
**offline, synthetic-only and never a signal, score, TRADE_READY decision,
execution proposal or trading order**. The code does not activate
Binance/Telegram/SQL or alter the accepted Stage00–08 contracts. There
is no source acquisition code or secret/private artifact.

## 1. Frozen ranges and source-time contract

`ProfileWindow` supports four explicitly anchored kinds:

| Kind | Accepted bar type | Admission |
| --- | --- | --- |
| `1h` | contiguous `1h` `CandleWindow` | complete at decision |
| `4h` | contiguous `4h` `CandleWindow` | complete at decision |
| `DAILY` | contiguous `1d` `CandleWindow` | complete at decision |
| `PREVIOUS_COMPLETED_WEEK` | exactly one Monday-to-Monday `1w` `CandleWindow` | strictly last fully completed UTC week |

The first bar **must** start at the caller's explicit `anchor_at`;
bars must be contiguous, UTC-aligned, have the **same source ID**,
and be fully closed and `available_at <= decision_at`. Underlying
`CandleWindow.errors_at` also enforces OHLC correctness, independent
base/quote quantities, `close_at <= received_at <= available_at`,
nonnegative volumes and timeframe duration. Any missing bar or post-
decision receipt fails closed. An existing/current developing week is
**not** equivalent to the previous completed week: for a decision
during a Monday-to-Monday UTC week, only the immediately preceding
fully closed Monday-to-Monday candle is allowed. No weekly profile
can reuse an unfinished in-progress weekly candle.

Source identity is explicitly `SYNTHETIC_TEST_ONLY` with manifest SHA256
shape validation. The hash and source label prove **internal consistency**
only; they do **not** authenticate genuine exchange trades or data coverage.

## 2. Price bins, tie-breaks and POC

All numerical work uses finite `Decimal` inputs. Caller supplies a
strictly positive `bin_size` and nonnegative `price_origin`. Prices
belong to integer bin `floor((price-origin)/bin_size)`. Bin `k`
covers `[origin+k*bin_size, origin+(k+1)*bin_size)`; a bar's exact
upper high boundary is assigned to the **previous** bin, except a
single-price range (low==high), which occupies its own bin. No dynamic
price/bin optimization, percentile-based bins or implicit timeframe
weights are approved.

Volume per bin is BASE-asset volume. `POC` is the **center** of the
highest-base-volume bin; in a tie, choose the **lowest-priced bin**.
No interpretation of POC proximity as bullish/bearish is implied.

Optional value area is computed **only** if the caller explicitly supplies
a fraction in `(0,1]`. Starting with POC, expand to the immediately
adjacent bin with more base volume until that cumulative share is met.
Tied neighbors choose the lower-price bin. `VAL` is the chosen
lowest bin's **lower bound**, and `VAH` the highest chosen bin's
**exclusive upper bound**. This is a research value-area algorithm,
**not** a universal 70% threshold or a trading gate.
At most 2,048 price bins including intervening sparse bins can be
represented; this prevents unbounded scans.

Example: synthetic closed OHLCV bar low 100, high 102, close 101, volume
12 base, bin size 1, origin 0 => two occupied bins: 100 and 101, six
base each, and POC center **100.5** by lower-bin tie. An explicitly
requested 0.70 value-area fraction yields `VAL=100`, `VAH=102`.
This arithmetic does not validate a real-market volume distribution.

## 3. EXACT synthetic trade arithmetic versus OHLCV approximation

Two **mutually exclusive** modes are preserved in every receipt.

### `EXACT_SYNTHETIC_TRADES` — internal fixture precision only

The caller passes typed prints `TradePrint` (trade ID, event/receive/
availability timestamps, exact transaction price and positive base
quantity) plus a `SyntheticTradeCoverage` receipt. Admission requires:

- Declared `first_trade_id`, `last_trade_id`, `expected_count`,
  complete synthetic self-attestation and SHA256 of the ordered prints.
- IDs strictly consecutive, times nondecreasing, all events within the
  pinned window, all receipts available no later than the decision, and
  exactly the same synthetic `source_id`.
- Trades within **each** source bar must reproduce its open, last close,
  high, low, BASE quantity and QUOTE `sum(price*base_qty)` exactly.
  Missing a bar's prints or altering one quantity/hash makes the
  dataset unavailable.

POC binning uses each traded price's BASE quantity; exact arithmetic
VWAP is `sum(trade_price*base_qty)/sum(base_qty)`. This is
**EXACT_SYNTHETIC_FIXTURE_ARITHMETIC_NOT_VERIFIED_EXCHANGE**, not a
representation of authentic `Spot Trades/AggTrades`. The synthetic
coverage self-attestation is deliberately insufficient for granting
real-source authority. Future real exact ingestion needs independent
exchange/capture completeness, timestamps and provenance, separately
authorized and verified. No live connection exists in this module.

### `APPROX_OHLCV` — deterministic descriptive proxy

For each closed source bar, distribute its BASE volume equally among
bins touched by its inclusive low-to-high envelope (with exact-upper-
boundary handling above). This is **not the observed traded-price
histogram**. The approximate VWAP is a BASE-volume-weighted `HLC3`
(close+high+low)/3 over those bars, **not** trade-price VWAP.
Measured source QUOTE is retained as a distinct concept and never
silently copied from BASE. Supplying trade prints in approximate mode
fails closed rather than mixing precision levels.

Both modes require positive total BASE volume, bounded price span and
the same fixed anchor and availability policy. Their values are not
scientifically interchangeable.

## 4. Prices, distances and chronology of reactions

The snapshot returns `POC`, `VWAP`, each level's signed price delta
`decision_price - level`, absolute delta, signed/absolute fraction
relative to that positive level, source, reference availability,
profile window, and exact computation/method label.

Optional `reaction` bars are a **separate, chronologically later
sequence** with a shared source and one candle timeframe. Their first
bar MUST **open at or after** the frozen profile's actual
`reference_available_at`. Hence a bar that starts before that
reference became available cannot be used to assert a contemporaneous
cross/retest, even if it closed later. A missing reaction sequence is
`UNAVAILABLE`, not an inferred event.

The transparent raw descriptors are:

- `cross`: favorable-direction close-side flip across frozen POC
  from an adverse/equal previous close to a strictly favorable close.
- `retest`: **after** a recorded cross, a later closed bar's range
  contains POC while the close remains favorable.
- `hold`: two consecutive post-cross closes strictly favorable.
- `rejection`: after a favorable close, a bar whose range touches POC
  closes back on the adverse/equal side.
- `seconds_since_last_cross_available`: actual decision time minus
  **receipt availability** of the most recent known crossing, not an
  event timestamp misreported as knowledge time.

A `UP` snapshot flips price signs relative to a `DOWN` snapshot,
but neither direction is assumed from POC proximity. No predictive
score, weight, offset, or trade gate is assigned.

## 5. Research-only Entry/SL/TP scenarios

Optional `ResearchHypothesis` requires explicit direction, entry,
stop, target and independently specified fee/slippage **per side in
basis points**; stop < entry < target for UP, reversed for DOWN.
Every price must be positive, finite, and source evidence consistent.
Optional structure price is a caller-provided source-labelled,
time-available research level; it is **not** a verified Stage08 pivot
or a qualified support/resistance level unless separately proven.

- Gross reward-to-risk = `abs(target-entry)/abs(entry-stop)`.
- Round-trip cost bps = `2*(fee_per_side_bps + slippage_per_side_bps)`.
- Net hypothetical reward fraction after costs =
  `abs(target-entry)/entry - roundtrip_cost_bps/10000`.

These equations are illustrative **scenario assumptions only**; no
guarantee of fills, stop execution, liquidity or PnL. The output
retains `SCENARIO_ONLY_NOT_VALIDATED`, `trade_ready=False`,
`is_order=False` with no signal ID or score. No automatic entry,
SL, TP recommendation is made.

## 6. Future segregation and synthetic ablation

`retrospective_profile_observation` accepts the hash-bound original
snapshot and **separately supplied future** closed bars. It refuses
foreign sources, pre-decision bar overlap and unavailable future
receipts. The first fully eligible future bar begins at the next UTC
frame boundary after the decision; an initial gap is
`CENSORED_GAP` and missing bars are `CENSORED_NO_BARS`, not fills.
Only descriptive `last_close - frozen_POC` is reported.
Future-bar mutation does not alter decision-time features or their SHA.

`synthetic_ablation` compares three **descriptive** same-snapshot
variants: price-only last closed candle close-minus-open sign
(no profile), price relative to POC (VWAP removed), and price
relative to VWAP (POC removed). It counts up/down/neutral cases,
agreement and disagreement with the price-only baseline across
verified synthetic receipts. There is **no** legitimate false-positive
rate or prediction accuracy without separate retrospective outcomes
and a carefully split real sample. Therefore both fields are `None`
and the result marks `DESCRIPTIVE_ONLY_NOT_OOS`. Overlap and
correlated historical opportunities remain a scientific audit issue;
this demonstration cannot establish a trading edge or policy.

## 7. PM acceptance matrix

| Requirement | Implementation / tests | Current boundary |
| --- | --- | --- |
| 1h/4h/day/prior completed week anchors | `evaluate_profile`; time and weekly tests | synthetic only |
| Bins, ties, POC and opt-in value area | `_bin_profile`, `_value_area`; bin/tie tests | user-supplied bin size |
| Exact versus approximate volume/VWAP | `_verified_trades`, `_bin_profile`; trade/coverage/hash and HLC3 tests | exact fixture ≠ exchange proof |
| Point-in-time source/availability | `_validate_bars`; foreign/late/missing tests | no live feed |
| Distances, cross/retest/hold/rejection | `_distance`, `_reactions`; UP/DOWN reaction tests | frozen POC, no gate |
| Entry/SL/TP and costs | `_hypothesis`; direction, costs, structure tests | never TRADE_READY |
| Future isolation | `retrospective_profile_observation`; future mutation/gap tests | descriptive outcomes only |
| Baseline and ablations | `synthetic_ablation`; synthetic comparison test | no predictive claims |
| Data quality/limits | finite, source SHA, volume, span, coverage guards | real completeness unverified |
| Owner Windows evidence | targeted command below | **BLOCKED_NO_OWNER_WINDOWS_ACCESS** |

## 8. Windows-local targeted receipt

Run **only on the authorized owner's Windows PC** (PowerShell 5.1 and
approved Python 3.12.10 environment). Do not rerun accepted Stage00–08
or run any live Binance/Telegram/SQL task. Keep raw logs on local `D:`:

```powershell
$ErrorActionPreference = "Stop"
git fetch origin
git checkout sd/stage09-fixed-range-vp-vwap-20261116
git pull --ff-only origin sd/stage09-fixed-range-vp-vwap-20261116
$head = (git rev-parse HEAD).Trim()
$tree = (git rev-parse 'HEAD^{tree}').Trim()
$dir = Join-Path 'D:\ZS-LOCAL-CI' ("stage09-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -p test_stage09_fixed_range_profile.py -v 1> (Join-Path $dir "stdout.txt") 2> (Join-Path $dir "stderr.txt")
$exitCode = $LASTEXITCODE
"HEAD=$head"
"TREE=$tree"
"EXIT=$exitCode"
Get-FileHash (Join-Path $dir "stdout.txt") -Algorithm SHA256
Get-FileHash (Join-Path $dir "stderr.txt") -Algorithm SHA256
```

Report the exact tested `HEAD/TREE`, actual count, pass/failure/skips,
`EXIT`, and separate SHA256 for the two raw files. Authored test count
is **not** a successful execution result. This ChatGPT session has
**no authorized owner-Windows access**, so required owner-local test
evidence remains `BLOCKED_NO_OWNER_WINDOWS_ACCESS`.
Hosted workflow failures must remain failures. Review and exact-SHA
merge permission remain PM/owner responsibilities.

## 9. Boundaries

One Draft PR only. Never modify accepted Stage00–08 components,
`ZS_SMART_GATE_MASTER.md` or root `README.md` from SD Coding.
Never activate production, live Binance, Telegram, SQL, trading, chats,
credentials or private owner artifacts. Do not claim OOS/forward edge,
accuracy, a real exchange's complete trade feed, TRADE_READY, or
a scientifically adopted policy from synthetic fixtures.
