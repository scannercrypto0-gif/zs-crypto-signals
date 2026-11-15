# MAT002 closure matrix and QV1-B decision sheet

| Link | Status / evidence |
| --- | --- |
| 00, 01, 02 | PASS bounded accepted source, scanner and Setup; PR54 historical evidence retained. |
| 03 C1–C4 | CLOSED bounded by owner #6726131155; no retrospective new gates. |
| 03 qualification | PARTIAL: provenance and identity intake, policy decision pending. |
| 04 | PASS application-only: pinned exact replay, reopened SQLite, and durable per-reply source/payload binding; production retention unapproved. |
| 05A | PASS accepted standalone / integrated synthetic routing; genuine qualified route BLOCKED on policy. |
| 05B | PASS prior API-accepted market rejection summary and JSON; no replayed sends. |
| 05C | PASS standalone prior evidence and new offline connected replay; fresh market integrated live proof pending. |
| E2E | PARTIAL: same archived source and decision through two fixture replies, not an all-live session. |
| Merge | HOLD for independent PM review and owner exact-head approval. |

## QV1-B-PROPOSAL-1 — one decision

| Horizon / direction | Required closed source | Components |
| --- | --- | --- |
| Intraday UP | 5m children + 30m parent; causal prior 1h/4h context; shared scanner inputs | N01–N06 explicit status/reason |
| Intraday DOWN | Same frames, direction-specific approved setup required | N01–N06 explicit status/reason |
| Swing UP | 1h children + 4h parent; prior structure and 1d/1w context; shared scanner inputs | N07–N12 explicit status/reason |
| Swing DOWN | Same frames, direction-specific approved setup required | N07–N12 explicit status/reason |

Proposed gates: approved source identity and digest, complete causally available and reconciled windows, UTC and approved independent clock/liquidity witness, versioned setup for the path, approved evaluator evidence and reproducible decision readback. Identity binds scope, venue, symbol, horizon, direction, setup version and close. A future signal identity also binds approved qualification policy version to that event. This packet supplies the evidence intake, not an approved numerical evaluator or certified history.

Accept vector: all explicitly approved gates pass on the same pinned evidence. Reject vector: approved setup/gate explicitly fails with valid inputs. Unknown vector: missing frame, unsupported path or witness, or missing approval; future/relabelled inputs are contract errors. Internal DETECTED_SIGNAL stays internal. Recommend allowing SCORE_UNAVAILABLE only after independent qualification; Score V2 and trade plan remain absent until their own rules are approved. Alternative: require Score V2 for all admission, which blocks qualification pending a separate scoring policy. N03 V0.2 remains diagnostic, numeric N03 unavailable, four SEM mappings unchanged. No signal, score, or plan is emitted by this proposal.

## One future integration session — NO-GO pending review

Only after exact-SHA independent PM review and specific owner authorization: use one public BTCUSDT capture, <=12 REST GET, zero WS, exact source/decision/readback binding; two genuine A/B private queries after READY and <=12 Telegram calls / <=2 05C replies. No 05A/B sends, retries, forced offset, old-session reset or artificial qualifying signal. Existing archived source explicitly historical, not a fresh result. Fresh acquisition/runner admission require independent review; this implementation only authorizes offline replay.

## Merge sequence

Review #54 cumulative implementation first (includes #53, do not merge it again), then #55. #57 modifies bounded interactive/forensics; #58 modifies the Round2 launcher and remains paused on top of #57. No overlap with the #55 delta paths in the reviewed file sets; refresh dependent base SHAs and compare again before any merge. #52 remains PM-owned docs and #49 separate historical cleanup. No MASTER/README changes. #58 PowerShell 5.1 ACL run was not attempted or reused.
