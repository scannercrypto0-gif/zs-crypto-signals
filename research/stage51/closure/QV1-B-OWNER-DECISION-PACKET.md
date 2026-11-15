# QV1-B-OWNER-DECISION-PACKET — version 2

## Implemented and verified engineering scope

- QV1-B-BOUNDARY-1 verifies decision/close/scope/path identity bound to source hash, per-frame closed and UTC/as-of ordering, symbol/feed consistency, witness-to-feed binding and component availability. Presence of a witness is not an independent clock attestation. Stable event/candidate identity is separate from immutable evidence SHA.
- Real promotion remains disabled. Historical approved rejection is independently replayed from Stage04 for archive C and never sent to 05A. The synthetic branch tests explicit PASS/FAIL/UNKNOWN, deterministic fixture signal identity after durable readback, A/B/C routing with the same fixture identity and no Score, rejection to C, audit-only UNKNOWN, and rejection of synthetic live dispatch. 05C remains read-only. No new traffic.
- C1–C4 acceptance preserved. Setup v1.1 UP breakout is an internal detection predicate on closed 5m bars, not an approved production qualification policy. R2 provides scoped component calculations, not overall qualification.

| Path | Source dependencies | Executable / owner-policy pending |
| --- | --- | --- |
| INTRADAY UP | 5m children and 30m parent, causal 1h/4h context; N01–N06 | Evidence checks and existing UP detection; qualification aggregation pending |
| INTRADAY DOWN | same | Evidence checks; direction-specific setup and aggregation pending |
| SWING UP | 1h children and 4h parent, prior structure and causal 1d/1w; N07–N12 | Evidence checks; approved Swing UP trigger and aggregation pending |
| SWING DOWN | same | Evidence checks; approved Swing DOWN trigger and aggregation pending |

## One policy decision

**Recommended:** phase qualification by approving a versioned Intraday UP evaluator first once the owner supplies the exact signed-off predicate set below. Leave unavailable paths fail-closed. **Alternative:** require all four paths and a common qualification specification before enabling any. The alternative delays UP qualification but avoids a directionally incomplete release. This is a single choice about scope plus the predicate values to make that choice executable. Until the selected version is specified, status is POLICY_OWNER_APPROVAL_PENDING.

| Rule pending | Definition and units for approval | Dependency and effect |
| --- | --- | --- |
| Directional trigger | Exact closed-bar predicate, lookback count (bars), direction and breakout comparator. Reuse approved UP internal detection where valid; specify DOWN and both Swing predicates or disable those paths. | Stage02/03 closed windows; determines event admission, never a score. |
| Required component acceptance | For each enabled path, list mandatory components, normalized units and comparators, or identify each as diagnostic-only. Decide required conjunction and behavior for unavailable inputs. | N01–N06 / N07–N12 from R2. Missing required component stays UNKNOWN. No threshold proposed as approved. |
| Numeric N03 and SEM | Keep N03 V0.2 diagnostic and numeric R2 N03 UNAVAILABLE; keep SEM-I-01/02 and SEM-S-01/02 unmapped. Alternative requires separate versioned formulas and independent reference evidence. | No substitution into gate values or score. |
| Liquidity and timing | Specify authorized book/24h volume evidence, limits in basis points/quote currency and seconds, and independent clock uncertainty/availability under the active context. | Source/event timing and market quality. A mere valid timestamp cannot certify a witness. |
| Score and trade plan | Existing owner decision permits SCORE_UNAVAILABLE after independent qualification. Score V2 and Entry/SL/TP each require their own approved formula and units. | Neither missing score nor plan changes a gate result; no numeric fallback. |

Decision vectors: all approved required gates pass on independently verified same-source evidence → eligible for approved-policy qualification; explicit approved gate failure on valid evidence → reject; missing policy or mandatory data → UNKNOWN; future, mixed or tampered evidence → fail closed. Live qualification remains NOT_TESTED and unavailable. No historical PIT/OOS or profitability claims.
