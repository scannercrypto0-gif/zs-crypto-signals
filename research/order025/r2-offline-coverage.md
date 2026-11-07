# «STAGE03 R2» — synthetic-only implementation and coverage

Authority: [R2 owner packet](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6690686194) and [PM design review](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6690961949). Authorized **offline development/testing only**; no formula or scientific threshold was frozen by that review.

## Scope and permanent protections

- One isolated module: «src/zs_smart_gate/stage03_r2_offline.py». **No edits** to «03A», «03C», «stage03_qualification_readiness», «setup021», «stage03_order022» or frozen original evidence.
- Only typed source receipts with prefix «SYNTHETIC:» are accepted. No network, credentials, persistence, production scanning, source capture, «OOS», «Forward», signal IDs, Telegram, or trading.
- For an individual horizon the module calculates **six** group values from the **12** defined groups over «Intraday/Swing». Every result remains «DEV_CANDIDATE», «SCORE_UNAVAILABLE», score null, probability null, qualified false, publishable false, signal_id null, delivery_authorized false, and «SYNTHETIC_ASOF_ONLY_NOT_REAL_PIT». The V2 score aggregator is **never called**.
- Onset candidate parameters «0.5 ATR/20 bars», pivot «2/2, 12×4h level validity, 0.10 ATR break», and market snapshot age limits «5s/60s» explicitly remain «UNFROZEN». Strict clock uncertainty <1.5 seconds is the existing owner-approved **future protocol** bound, not evidence of a real clock in these synthetic tests.
- Missing group inputs give null with a reason. Nonexistent source receipts, later-arriving bars, unconfirmed pivots, stale snapshots, zero denominators and broken parent/child identity cannot be promoted to a qualified result.
- Old «ORDER022/ORDER025» original results are not rerun or used for choosing these candidate constants. Shared-parser replay acceptance remains scoped to arithmetic only.

## Coverage matrix

| Requirement | Implementation | Synthetic tests / expected controls | Scientific status |
|---|---|---|---|
| Both horizons, both directions, both modes | «evaluate_r2» + immutable «V2_GROUPS» | exact six groups, never qualifying, deterministic repeat | «DEV_CANDIDATE» |
| «N01/N08» | «close_parts» | 0.6 close example, direction reversal, zero-range rejection | Unfrozen |
| «N02/N09» | «path_parts» | path progression, efficiency, retention, missing-child reject | Unfrozen |
| «N03» | «onset_timing» | as-of first crossing before decision, missing/full impulse, no future | Early-success claim blocked |
| «N04» | «volume_continuity» | isolated spike 0.088889 vs sustained 0.6875, zero reference | Unfrozen |
| «N05/N10» | range/context formula | closed 1h/4h and daily/weekly as-of only; context not structural break | Unfrozen |
| «N06/N12» | «liquidity» | bid/ask+quote24, spread and turnover, crossed book, late/stale snapshot | Real PIT unverified |
| «N07» | «confirmed_pivots», «structure» | strict left/right, ties reject, confirmation at known time, CHoCH, consumed level | No repaint, no qualification |
| «N11» | 4h ATR and quote-volume formula | full prior window, zero/unknown reject, both directions | Unfrozen |
| Clock/availability/source | «ClockWitness», «asof», «check_bars» | independent synthetic test witness, <1.5s limit, conservative availability ordering | Synthetic-only, no real clock attestation |
| Frozen setup/source / no production | only new source/test files; existing hash constant asserted | no new network calls, no IDs, no publish, no score | Unchanged frozen baseline |
| Economic/statistical qualification | intentionally not implemented | result remains NOT_EVALUATED and no forward test | «N_REQUIRED=UNDETERMINED» |

## CI scope and handoff

New workflow «.github/workflows/03-r2-offline.yml»: pull requests only; Ubuntu/Windows × Python 3.11/3.12; permissions contents read; runs only the R2 synthetic test module. Existing «foundation-tests.yml» may also run automatically; acceptance requires checking **all jobs on the exact PR SHA**. No manual live workflow, market GET/WS, new data, actual clock witness, order, or Telegram is permitted.

Not completed in this order: independent real UTC/PIT evidence; publisher timestamps; source rights; real book/24h availability; calibration on future independent DEV; full D3 DOWN inventory/NO_FILL economic outcome; D5 N_REQUIRED, qualified statistical controls, untouched OOS and Forward, scientific acceptance and Stage05.

**Disposition:** «STAGE03_OPEN / STAGE05_FULL_HOLD / DEV_CANDIDATE / FORMULAS_UNFROZEN / HISTORICAL_PIT_UNVERIFIED».


## «009A» — bounded functional completion on existing «PR #39»

Authority: [PM 1.6 authorization #6706906310](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6706906310). This extends the *synthetic-only* calculation and Stage03 contract wiring, **not** scientific edge validation or source/PIT approval. «007A/008» historical results are preserved, not rerun.

| Group | Calculation / inputs | «009A» integration verdict | Still blocked |
| --- | --- | --- | --- |
| «N01» | closed 30m OHLCV | reused 007A + R2 functional bridge | live source PIT / qualification |
| «N02» | 6 contiguous 5m children | reused 007A + bridge | live source PIT / qualification |
| «N03» | 5m onset with previous ATR and externally supplied explicit full-impulse trace | synthetic boundary / unknown=UNAVAILABLE | approved and independently proven full-impulse predicate / historical event trace |
| «N04» | child quote volume continuity | reused 007A + bridge | live source PIT / qualification |
| «N05» | closed 1h/4h context | reused 007A + bridge | live source PIT / qualification |
| «N06» | separately received book + rolling 24h USDT quote volume | unit/window/eligibility/as-of checks, independent numeric reference | authenticated original book/ticker24 source and as-of |
| «N07» | confirmed pivots, mode, 4h ATR_prev, level consumption, liquidity | fixed 8-bar unreachable call to 32-bar existing synthetic fixture, causal positive/negative tests | original confirmed structure/mode and real liquidity/PIT; parameters UNFROZEN |
| «N08» | closed 4h OHLCV | reused 007A + bridge | live source PIT / qualification |
| «N09» | four contiguous 1h children | reused 007A + bridge | live source PIT / qualification |
| «N10» | last closed+available 1d/1w, prior ATR, context-only direction/mode | independent arithmetic + late weekly rejection | historical 18-week warmup and mode/availability attestation |
| «N11» | 4h ATR and quote volume | reused 007A + bridge | live source PIT / qualification |
| «N12» | N06 shared liquidity with separate Swing horizon | unit/window/as-of tests + bridge | real original book/ticker24 and clock |

**Bridge contract:** `src/zs_smart_gate/stage03_r2_functional.py` calls the accepted `assess_readiness` and existing `evaluate_r2` with their **independently typed original input objects**, verifies matching source IDs/price/quote-volume/as-of/parent-and-child windows, then emits a deterministic SHA256 packet. A candidate remains `RESEARCH_CANDIDATE / NOT_EVALUATED / SCORE_UNAVAILABLE / signal_id=None`; source disagreement or failed qualification-readiness becomes `REJECTED`. Neither bridge nor R2 invents `base_volume` from quote turnover. In the one synthetic fixture, the caller explicitly provides both base and quote volumes. The packet digest is a reproducibility fingerprint, **not** independent receipt/custody/PIT certification.

**Fail-closed:** R2 accepts only `SYNTHETIC:` source receipts and synthetic witness; `N03` lacking a defined impulse trace returns unavailable, and positive synthetic trace is labeled unapproved. `N06/N12` enforce explicit USDT quote and rolling-24h ticker semantics, but existing synthetic-fixture defaults do not attest any real provider feed. `N07` still needs confirmed 2-sided pivot evidence and pre-open level; a delayed middle pivot confirmation cannot be silently filtered out. `N10` remains context only, never a reversal trigger. `03C score_v2` and production `DETECTED_SIGNAL` are not invoked.

**Previously accepted tests:** no new run of 007A or 008 is authorized. The closed 008 CI job is disabled for subsequent 009A commits; remaining automatic bounded PR regression jobs verify edited code without market requests. No MASTER/README edit, no Stage05, no Telegram, trading, live market, publication, or merge.
