# QV1-B-FINAL-DECISION-PACKET — version 1

Owner decision #6767851362 allows SCORE_UNAVAILABLE after independent qualification under an approved contract. Missing numerical predicates remain POLICY_OWNER_APPROVAL_PENDING. Preserve owner-closed C1–C4. Existing source/clock guards and Setup/R2 component contracts remain authoritative within their existing scope.

| Path | Required windows | Setup / ledger |
| --- | --- | --- |
| Intraday UP | closed 5m children, 30m parent, causal 1h/4h context | Setup v1.1 UP where defined; N01–N06 |
| Intraday DOWN | same windows | approved DOWN predicate required; N01–N06 |
| Swing UP | closed 1h children, 4h parent, causal prior 4h and 1d/1w context | approved Swing UP predicate required; N07–N12 |
| Swing DOWN | same windows | approved Swing DOWN predicate required; N07–N12 |

Require named approved predicates, source and liquidity evidence, ordered UTC receipt/availability before decision, reconciled windows, policy-bound deterministic event identity and verified journal readback. Pass vector requires each approved gate to pass. Fail vector requires valid evidence and explicit gate rejection. Unknown includes unsupported setup or missing mandatory context, witness, evaluator or approval. Unapproved quantitative rules remain unavailable. A qualified signal identity would bind the stable event to the approved policy version; internal DETECTED_SIGNAL does not authorize it. N03 V0.2 remains diagnostic and four SEM links remain unmapped.

Recommendation: once independently qualified, allow SCORE_UNAVAILABLE if the approved qualification contract explicitly permits it, with a reason and no invented number. Alternative: require Score V2, which keeps the route closed until an independent scoring decision. Trade plan is separately approved; no fabricated levels. This packet asks for one versioned policy decision. Absent approved missing predicates, keep qualified dispatch closed even if the evidence-intake contract is accepted.
