# ORDER-021 — Simplification matrix, dependencies, and proposed gates

> **SUPERSEDED FOR STAGE03 CLOSURE — OWNER/PM 2026-11-08.** This is a retained historical research record, **not** an active Stage03 closure checklist. The only active Stage03 closure gates are **C1–C4** in [MASTER](../../ZS_SMART_GATE_MASTER.md) and [Issue #25 PM audit](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6721751412). Historical requirements for blind OOS, forward studies, N_eff/N_REQUIRED, predictive edge, executable PnL, fees/slippage economics, full historical publisher PIT, prospective capture, D1–D5 predictive calibration, and full 00–04 E2E **MUST NOT block C1–C4**. Retain their original scientific limitations for future separately authorized work; never interpret them as waived scientific evidence or as production approval. Tests/evidence already accepted are REUSE, not mandatory RETEST. All new acceptance runs are local Windows only; GitHub Actions checks are not Stage03 acceptance evidence. Stage05, market access, trading and Telegram remain unauthorized.


**Fixed source:** MASTER v1.37 / Issue25#6652586815. **Owner/PM review**
required for any tradeoff that changes validity, production safety, or a frozen
historical result. Classification does **not** authorize merges.

| CURRENT_REQUIREMENT | PURPOSE | WHY_HARD | SIMPLER_EQUIVALENT | SAFETY/QUALITY_IMPACT | EVIDENCE_NEEDED | PM_DECISION |
|---|---|---|---|---|---|---|
| Prove historical publisher PIT from later REST kline archives | Exclude future-known inputs | Archive lacks original arrival receipt | DEV/OOS historical replay labeled HISTORICAL_PIT_UNVERIFIED; prospective receipt test later | KEEP no-lookahead, DEFER historical publisher proof; never claim certified PIT | Original source+receipt+decision timestamps for future observation | REPLACE_WITH_DISCLOSED_LIMIT; final science promotion PM |
| All 12 normalizers and multi-group numeric score | Filter bad observations | Several fields and calibrations absent | One frozen close/20-bar-high/20-bar-quote-volume rule, existing Spot & spread scanner gates | No reduction to input quality; performance superiority NOT asserted | Predicates, negative cases, sensitivity and labelled outcome study | SIMPLIFY; changes to actual rule require new contract/version |
| Heavy clock authority before any offline detector test | Arrival-before-decision correctness | Source-independent UTC calibration unavailable | Closed candle checks, available_at and decision monotonic ordering; CLOCK_UNCERTAIN when order cannot be certified | Synthetic wall times not a live UTC attestation | Real receipt+monotonic+clock uncertainty on bounded PM-approved field study | SIMPLIFY only offline; KEEP real time ordering |
| N_REQUIRED arbitrary before actual coverage | Avoid unsound confidence | No verified real sample inventory | Code-level correctness now, coverage first and predeclare N before real OOS | INSUFFICIENT_EVIDENCE until N/labels and independent OOS | Verified monthly coverage/label method and sample-power rationale | DEFER_WITH_DISCLOSED_LIMIT |
| Windows production storage immediately | Durable records in final hosting | Owner Windows not the development runner | SQLite temporary adapter and hosted CI with readback+backup; swap adapter at deployment | No claim of owner Windows durability | Native Windows restore, power-failure, backup/encryption acceptance | REPLACE for dev; KEEP production acceptance |
| GitHub all-time-runtime write dependence | Historical research custody | Contradicts final Windows host model | Research-only artifacts/GitHub evidence during development, local runtime later | Keep historical Stage04 records; no token required for future final runtime | E2E integration of swappable adapter | SIMPLIFY; leave legacy 020 inactive |
| Prior 020 field window at 2026-11-05T06:00Z | Bound market experiment | Date expired, Manifest not frozen | No live experiment in ORDER021; separate future approved one-event plan | Zero market requests; no implicit rollover | New frozen Manifest, PM 1.4 approval, native host readiness | KEEP gate; DEFER live |
| Stage05 before complete Stage03 acceptance | Prevent premature delivery | Scientific closure not attained | Test internal DETECTED_SIGNAL only, never destination routing | Stage05 FULL_HOLD unchanged | Independent Stage03 closure and owner decision | KEEP |

## Draft PR dependency classification — no silent rebasing

| PR | Current head | Classification today | Reason and needed gate |
|---|---|---|---|
| [#27](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/27) | e19531c50347ab29782c92113691ce34158c5769 | NEEDS_CHANGE | Independent historic DEV/OOS line; retain frozen science, assess differences vs v1.37 and re-test before merge |
| [#28](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/28) | 0f8f28dd77057681fd9776e3cc625201b1e2c7b0 | NEEDS_CHANGE | Clock/source evidence valuable, old main; do not promote absolute PIT; recheck workflow conflicts |
| [#29](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/29) | 18cc6238112a75321d2b194419cd1a38ec4eb5f0 | BLOCKED | Depends on prior #28 but behind #28 by one commit; GitHub custody historical only, final runtime must not require it |
| [#30](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/30) | 2f4c6266fb88893dbb1f2e1805f28afdacca1bbb | NEEDS_CHANGE | Stacked on #29, accepted 016–019 evidence retained; needs dependency+current main test, no rewriting frozen data |
| [#31](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/31) | fe556ae8dda01261b100d135f9ffc6053cf2e4de | BLOCKED FOR LIVE/MERGE | 020-A approved offline only, legacy native GitHub token + expired field plan; require new reviewed local field protocol, not bypass |

**ORDER021 branch:** intentionally based on **current main**, not on an outdated
stack. It imports existing \`core\`, \`binance_live\`, \`scanner\`, and uses
dedicated \`setup021*\` files without editing 010–020, previous evidence, or
PR heads. This avoids carrying 126+ unrelated stacked changes into a minimal
one-setup research PR. No PR is automatically merge-ready from old green CI.

## Engineering acceptance vs scientific qualification

| Component | ORDER021 expected acceptance | Current evidence limit |
|---|---|---|
| parser and source | Existing code handles synthetic public REST-formatted closed kline rows | No new live Binance request; no publisher PIT |
| candidate/scanner | Existing Spot/liquidity/quality contracts are called unchanged | No authenticated real market condition |
| deterministic setup | 20-bar-high/volume with prior-FALSE→TRUE and source identity | Not calibrated; only one UP/5m research setup |
| split | Frozen code/threshold used for earlier DEV and later OOS synthetics | No real OOS outcomes, no performance claims |
| persistence | Local WAL/FULL commit, readback, dedup, independent backup and hash restore | GitHub runner temp disk, not final Windows |
| CI | New 021 test and full legacy foundation Windows+Ubuntu | Synthetic execution only; production host UNKNOWN |
| prospective | Distinct, explicitly unavailable | No field rights/timing/manifest and no live approval |
| Stage03 closure (historical proposal superseded) | Current owner-approved C1–C4 calculation/source/functional closure only, independent PM and owner decision | Predictive scientific evidence remains separate and deferred |
