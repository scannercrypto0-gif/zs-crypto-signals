# SCIENTIFIC_007_UP_DOWN_REPORT — original source intake, not signal approval

Authority: owner amendment Order007-A/007-B in PR #71.
Period: 18 November 2026. Status: **SCIENCE_NOT_APPROVED**.

## Current original market evidence (historical, not newly replayed)

- Order006 exchangeInfo observed 3,743 instruments, of which 1,373
  active Spot and 518 active USDT. This is **listing discovery**, not
  a proven eligible/liquid denominator or full-market candle evaluation.
- Historical four-asset source snapshot captured only **six** 5m bars
  for each of two captured assets (BNBUSDT/BTCUSDT); the other two
  assets had only instrument identities. They cannot support the 22
  consecutive 5m candidate requirement.
- A separately captured BTCUSDT 22-bar original source replay produced
  true `NO_TRIGGER` for both UP and DOWN, not verified real positives.
- Before new owner Windows execution, **new original cross-asset
  dataset ID: NOT_YET_CAPTURED**, **actual accepted new evaluated
  5m windows: 0**, **qualified genuine UP: 0**, **qualified genuine
  DOWN: 0**. Do not attribute synthetic directional positives to real
  markets.

## Implemented source and admission code

`scripts/order007-original-capture.py` and
`src/zs_smart_gate/order007_original_source.py` run only as
**manual, bounded, public-read-only Windows foreground operations**.
They retrieve original Spot listing, 24h ticker/book and up to two
requested eligible symbols' exact 22×closed 5m + 30m/1h/4h endpoint
rows, binding symbol, UTC event boundary, measured receive-at,
source response SHA256, selected bin/request parameters and source
identity. Responses are stored on **D:** with per-response source-body
hashes, a private combined packet and a sanitized manifest.
The collector checks exchangeInfo runtime one-minute REQUEST_WEIGHT
policy and the shared-IP `X-MBX-USED-WEIGHT-1M` header via bounded
capture; the local conservative ceiling is 5,500 with 500 reserved
against the observed runtime limit, and own 11-GET/140-weight and
120-second watchdog limits remain separate.

The source-capture module may produce
`SOURCE_VALIDATED_CLOCK_BLOCKED`, `SOURCE_INVALID_OR_INCOMPLETE`,
or `UNSCANNED_INELIGIBLE_OR_UNAVAILABLE`. Such dispositions do
not establish a contemporaneous scientifically valid event.
Unreviewed operational Windows Time policy, historical capture age,
source/market missingness and invalid contexts remain explicit blockers.
No trading/Telegram/production signal ID is created.

`scripts/order007-science-intake.py` and
`src/zs_smart_gate/order007_science.py` read owner-private D:
source records, independently hash-check original response bytes
against the sanitized manifest and each per-symbol packet, deduplicate
symbol/boundary, and reproduce descriptive source admissibility and
candidate status counts for BOTH directions. The resulting
`dataset_id_sha256`, `manifest_chain_sha256`, and
`development_hypotheses_sha256` are reproducible from owner-local
bytes. Different packet data for the same symbol/boundary or a
tampered source response is rejected; a blank result is NOT a pass.
These records are still **self-attested public HTTP observations**,
not independent exchange or absolute time-source attestation.

## Development hypotheses: versioned but not scientifically accepted

The new file `ORDER007_UP_DOWN_DEV_HYPOTHESES.json` records
the existing deterministic **development** assumptions:

- UP: newest closed 5m close above prior 20 highs and above its open;
  quote volume at least 1.20× previous-20 mean; false-to-true
  transition.
- DOWN: newest closed 5m close below prior 20 lows and below its open;
  quote volume at least 1.20× previous-20 mean; false-to-true
  transition.

These are **not** frozen adopted scientific thresholds or an
authorization to open OOS. Candidate event IDs are source/version/
direction-bound, but there is **no approved QV1 production policy**
for either direction.

## Scientific gate matrix before new actual Windows samples

| Requirement | UP | DOWN |
|---|---|---|
| Genuine representative source dataset ID | PENDING | PENDING |
| Multi-symbol 22 closed 5m + aligned 30m/1h/4h | NOT_PROVEN | NOT_PROVEN |
| 24h quote volume, spread/fees quote normalization | NOT_APPROVED | NOT_APPROVED |
| Windows Time/independent observed uncertainty | BLOCKED | BLOCKED |
| PIT D1–D5 + 12 normalizer decisions | UNREVIEWED | UNREVIEWED |
| N_REQUIRED, minimum signal-quality and cost thresholds | UNREGISTERED | UNREGISTERED |
| Chronological DEV, untouched OOS, embargo/purging | NOT_RUN | NOT_RUN |
| True prospective forward/shadow outcomes | NOT_COLLECTED | NOT_COLLECTED |
| Precision/recall/calibration/false positives | NOT_EVALUATED | NOT_EVALUATED |
| Overlapping-opportunity uncertainty, asset/regime/year splits | NOT_EVALUATED | NOT_EVALUATED |
| Independent PM scientific acceptance | NOT_APPROVED | NOT_APPROVED |
| Production signal qualification | FORBIDDEN | FORBIDDEN |

The present source intake intentionally **does not open OOS**,
calculate fabricated precision/recall/profit, or fill approved
scientific registries. Original data collection requires actually
running the Windows source collector; this session has no physical
owner-PC access. After sufficient original data, PM must independently
adopt the eligibility universe, clock policy, D1–D5, normalizers,
pre-registered DEV/OOS/forward split/embargo, `N_REQUIRED`, horizons,
costs and quantifiable accept/reject rules **before OOS is opened**.
Otherwise the scientifically correct decision stays
`UP_NOT_QUALIFIED / DOWN_NOT_QUALIFIED`.

## Custody, deployment and authority

Raw original HTTP bodies, original combined packets, private config
and Windows logs stay on `D:\ZS-SMART-GATE\`. Only sanitized
hash-bound manifest and reason codes may be submitted for PM review.
Installing a disabled Windows package and engineering-merging a
properly tested branch are separately allowed actions; neither
licenses public or commercial market signals, 24-hour unattended
operation, external message delivery, GitHub operational archives,
SQL, or trades.

Verdict: `SCIENCE_EXECUTION_CODE_DELIVERED / NEW_ORIGINAL_CAPTURE_PENDING_OWNER_WINDOWS / SCIENCE_NOT_APPROVED / UP_DOWN_NOT_QUALIFIED`.
