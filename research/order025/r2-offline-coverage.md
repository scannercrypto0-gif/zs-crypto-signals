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
