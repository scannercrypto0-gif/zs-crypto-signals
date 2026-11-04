# Order018 — independent prospective protocol V2

Owner decision: Issue25#6623892290; MASTER v1.32, read from current main
`a0f8493aee1228bc625360fd55a553cc5c69954f`. PM reviewed017 at #6623633666
and016 at #6607149613. Parent PR30 SHA445d7b04fd834c2dc84ad3d296e406ea357c055e.
No governance edits, merge, hardware purchase, Windows change or live requests.

## Policy and historical preservation

| Concern | Frozen V1 /010–017 | New V2 /018 |
|---|---|---|
| Clock total uncertainty | strictly <1s | strictly <1.5s |
| Exact upper boundary |1s fails|1.5s fails;1.499s can pass only complete proof|
| Source/counter/drift | Historical decisions unchanged | independently admitted proof AND explicit source/transfer/local budget, calibrated counter and future drift bound |
| Raw receipt / input IDs / mono / sequence / gaps | preserved | retained, no extra late-input allowance |
| Candle close | historical margins preserved | closed_at + uncertainty <= received_wall |
| Publication PIT | HOLD | HOLD; receipt never proves original publication |
| Forward activation | not authorized | not authorized; new owner scope/version required |

All139 pre018 research/source/test/script Git blobs are pinned in
preserved-git-blobs.json. The new GitHub-only reproduction checks exact Git
object IDs at HEAD and original017 checkout SHA, preventing silent historical
edits. V1 code/contracts,016 model/calibration/DEV data,017 raw replies and
original results remain byte-identical. Old acceptance/failure labels are never
renamed. No local drive locator is an authoritative restore input.

## Timing-gate audit and explicit routes

| Location | Disposition |
|---|---|
|prospective_causality.py|Frozen V1, retains1s; no global search/replace|
|clock017.py / verify-017-clock.py|Frozen original conditional1s calculation and HOLD|
|stage03_nts_authority.py|Frozen historical conditional1s gate; retired probes not re-enabled|
|integrated_research016.py / forward_slot016.py|Frozen016 API; old protocols/scopes are not routed through V2|
|prospective_causality_v2.py|New strict1.5s total-error gate; decimal accumulation; default reviewed pins empty|
|integrated_research018.py|Explicit new-study-only entry, rejects historical/compat replay reinterpretation; imports V2 assess|
|forward_slot018.py|Dormant V2-scoped injected-I/O entry; old scope cannot activate V2; same source/weight/size/claim/no-retry protections|
|protocol-016.json / old forward proposals|Frozen historical/unapproved plans; never alter or auto-start them|
|protocol-v2.json|New versioned clock contract, no source/trading activation|
|restore-018-time-bound.py|Offline derived view of017 only; never issues provider request|

Separate1s wall/monotonic discontinuity guards remain conservative anomaly
detectors, NOT the UTC uncertainty ceiling. Existing5m freshness10minutes,
decision freshness10seconds and liquidity age10seconds are independent source
quality policies; they are not changed to1.5s. For example a2second
receipt-to-decision interval with a valid clock and closed inputs is supported.
No lateness is added to received<=decision comparisons. Alert latency is only
a separate optional diagnostic; no Telegram sender or speed target is added.
Original source-to-receipt transport delay stays unknown when original
publication time is unproved, rather than inferred from clock error.

The new modules are explicit versioned forks to preserve frozen implementations
and output identity. Structural receipt/digest functions are shared from frozen
V1; no monkey patch or implicit fallback. Scientific scoring/eligibility remains
blocked regardless of a synthetic causal candidate. Synthetic trust doubles
exercise branch acceptance; they are not admitted real-world attestations.

## Re-evaluation of017

New file reevaluation-017.json is derived from original017 signed samples and
reproduces the old verifier output exactly first. Conditional bounds remain
1.1648551088989259 /1.216447938092041s. Both satisfy the new NUMERIC ceiling;
neither receives scientific clock admission. Local counter calibration,
maximum future drift proof and independent total-budget admission are missing.
Original below_one_second=false and original HOLD remain unchanged. No
new attestation or registry pin is constructed from the threshold change.

## Verification and remaining evidence gate

New tests exercise1.499/1.500/1.501, exact accumulated drift1.500, missing or
tampered witnesses, calibration expiry/reboot, total-budget understatement,
forming/near-boundary candles, future receipts/contexts, latency separation and
V2 dormant capture claim/recovery. Full foundation CI remains mandatory on
Windows+Ubuntu; original016 replay and017 signature checks remain separate.
The new018 clean-runner workflow fetches only GitHub-pinned017, verifies frozen
blobs and SHA256, disables sockets during computation, and reproduces the new
view byte-for-byte. Nothing depends on D or a local owner's disk.

Remaining external input: independently reviewable calibrated counter and
maximum drift valid for a specified same-epoch time interval, with a complete
source+network/timestamping+local uncertainty budget below1.5s at EACH receipt
and decision. Existing017 signatures alone still do not provide it. PM must
independently review the new contract/code/evidence. Real Forward requires its
own later source/rights/quota/storage/clock acceptance and owner time/bounds
scope; no date or automatic start is adopted here. No scientific closure,
new OOS, winning formula or production signal is claimed.
