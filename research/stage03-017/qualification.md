# Order017 clock qualification — HOLD, no Forward activation

Authority: owner execution instruction in chat 4 November 2026 (Asia/Riyadh),
MASTER v1.31 and PM review Issue25#6607149613. Preflight Issue25#6623205730.
No published order017 URL was supplied; do not invent one.

## Actual experiment

Two public Roughtime UDP requests, 1024 bytes each, 30 seconds apart, no retries,
port2003; two 352-byte replies. No market calls, NTS repeat, Windows mutation,
service, schedule, trading or continuous Forward. Host DNS outside RTT bracket.
Original samples preserve the first parser's missing-NONC error. No new network
attempt followed that error. The corrected offline verifier confirms signatures
and nonce membership on the same exact raw replies. Cloudflare's deployed
draft11 omits an echoed NONC; signed Merkle inclusion still binds the fresh nonce.
This explicit deployment profile is not RFC10049 conformance.

Signed radius: 1 second on BOTH replies. RTT 0.0177287 / 0.0175022 seconds.
Conditional conservative local error bounds: 1.1648551088989259 /
1.216447938092041 seconds. Strict <1 second fails even before drift qualification.
Neither best RTT nor two-sample averaging can remove the authority radius.
Wall-vs-monotonic observed slope ~1.5928ppm is descriptive, NOT a guaranteed
oscillator drift or independence from the Windows hardware clock. Signed source
time at generation is bracketed by request/response; no symmetric path assumed.
RTT arithmetic assumes the monotonic timer's rate; no traceable timer calibration
was available. Therefore these bounds are conditional, never admitted UTC pins.
Windows diagnostic was read only; synchronization status and precision fields
are not UTC attestation. Initial root dispersion was4.1334482s and last good sync
age27782s; a later status snapshot is retained separately with its own values.

## Source review and alternatives

- Cloudflare published key/endpoint (beta; check pinned key on each future
  review): https://developers.cloudflare.com/time-services/roughtime/usage/
  Code-wire reference: https://github.com/cloudflare/roughtime/blob/main/protocol/protocol.go
  Wire version constants: https://github.com/cloudflare/roughtime/blob/main/protocol/version.go
  Protocol design informed this independent Python implementation. Referenced
  upstream source is Apache-2.0; no new runtime package or downloaded client.
  Observed integer-second signed radius is unsuitable for this gate. No repeated
  probes intended to cherry-pick a smaller radius.
- Netnod free NTP/NTS is traceable to UTC(SP):
  https://www.netnod.se/free-time-services
  Internet service has no accuracy SLA:
  https://www.netnod.se/netnod-time-direct
  TLS/AEAD + root dispersion remain conditional metadata, not an independently
  guaranteed local UTC error/drift bound. No new NTS exchange was performed.
- Netnod guaranteed services are managed/direct products, not free public
  endpoints. No purchase or paid trial is authorized or started.
- A locally available UTC-traceable GNSS/PPS or calibrated oscillator plus
  timestamping path could resolve this, but none was provided/verified here.
  Merely shortening Windows polling cannot manufacture traceability or a
  maximum hardware drift guarantee. No security downgrade or UAC was needed.

## Prepared external evidence request (NOT SENT)

Recipient candidates: Netnod/RISE time metrology authority, or an existing
owner-provided UTC-traceable clock supplier. Request a free/public document or
signed proof identifying the actual reference and validity interval, calibration
chain to UTC, maximum absolute error at generation, leap/smear semantics,
uncertainty units and confidence/coverage, nonce-bound independently verifiable
transcript, and any drift/rate bound for the local timestamping path. For an
existing GNSS/PPS installation, also supply calibration and PPS-to-Windows/QPC
latency/jitter bounds, restart/suspend behavior and device identity. State all
terms/costs before use; no account, payment, support contact or purchase has
been made. A source claim without a local transfer/error budget is insufficient.

## Forward readiness and exact next gate

NOT_ARMED. No new admitted UTC proof hash, observed market event, or automatic
pin insertion. Historical publisher PIT remains HOLD. Need a <1s total budget
at each receipt AND decision, measured/tied to the same epoch, including source,
network/timestamping, wall/QPC residual, calibration age and admitted drift.
Faults/reboot/suspend/reconnect require recalibration and a new anchored epoch.
Existing016 plan's5–6November dates confer no authorization. Re-date a small
BTCUSDT/ETHUSDT proposal only after independent clock acceptance and re-review
of source rights, private GitHub custody, free quota, exact request/byte limits,
and stop conditions. PM review then a separate explicit owner start/end scope.
No timer, task or automatic start was installed.

## Merge review snapshot, no merge

28 head0f8f28dd77057681fd9776e3cc625201b1e2c7b0 → main;
29 head18cc6238112a75321d2b194419cd1a38ec4eb5f0 →28;
30 original016 head9ae9ac0ce23449b38b2da4592015935b45094774 →29.
main6b42e2193bcd5ad6feea075ee91f54fb775baf2f. All open Draft/unmerged.
Reviews returned COMMENTED, not APPROVED. PM accepts016 engineering only.
28 advances not included in frozen29 head: inspect duplicate crypto/probe
backports and merged-tree diff, do not infer new-base CI from old green checks.
Decision order28, retarget/revalidate29, then retarget/revalidate30, independent
owner decisions each. 27 separate; no scientific/OOS transplant. This017
increment stays on30, preserving previous016 code/evidence SHAs. Original
merge review remains research/stage03-016/merge-review-016.md. No speculative
retarget, merge or old research/market rerun was performed.

## Offline review

PYTHONPATH=src; run tests/test_clock017.py with existing pinned crypto lock;
python scripts/verify-017-clock.py research/stage03-017/samples.json
Verify manifest hashes before interpreting the results. Samples contain no keys,
cookies or account tokens: root public key, random public nonce, signed replies.
Hashes/CI are application custody evidence, not scientific independent approval.
Review verdict: CLOCK_SOURCE_AUTHENTICATED_BUT_RADIUS_FAIL / DRIFT_UNPROVED /
PROSPECTIVE_UTC_HOLD / FORWARD_NOT_ARMED. Actual receipt/decision scientific
qualification remains unavailable; no synthetic event can close it.
