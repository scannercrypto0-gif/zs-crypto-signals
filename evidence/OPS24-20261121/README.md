# OPS24 acceptance evidence — scope and exclusions

Implementation PR: #76; governance PR: #75 (untouched).
Code HEAD 8c52be6f9c5d7a49af19bf68b1d8d50bd63a5b72; TREE dcf6a9b1abc2a62c9b91891e605dfcbdccf2bd98.
Windows11 normal token, Python3.12.10, native PowerShell5.1.26100.9818. Installed runtime remains 25210a1e152a92e0562e108f3d1fc16e4e1b61ab, disabled. Main remains7b7bb0e.

## Original tests and reconstruction

- windows-tests/OPS24-20261121-keepalive-fixed-evidence/acceptance.json: final41 tests, zero failures/errors/skips/Python network attempts, clean exact release. Includes single historical CLOCK74 regression only.
- windows-tests/OPS24-20261121-github-final-reproduction/acceptance.json: same41 cases reproduced in a fresh private GitHub clone, same HEAD/TREE. No local source worktree dependency.
- Other windows-tests directories and historical-iterations hold original earlier test outputs, each retaining their actual head and counts (30,34,35,37,38,39). They are not extra independent evidence for scientific performance. The initial keepalive transport test exposed an origin-pin mismatch (1 failure/1 error); the fixed final41 result is authoritative. Failures encountered during normal-clock investigation remain in clock-provenance rather than being erased.
- Controller tests actually ran PowerShell disabled install/status/XML/restore/reinstall/rollback in isolated temporary D roots. No task was registered/enabled. Supervisor network/restart/breaker cases are fixtures, not a real reboot or 24h service trial.
- CI: no checks/workflow configured for this branch. Windows receipts are the acceptance evidence; no CI PASS claim.

## Clock

WINDOWS_STATUS_PROTECTED_REGISTRY_V1 uses native OS configuration/status, protected64-bit registry ACLs, service SID/image/DLL provenance, Microsoft binary signatures/ACLs, original query exit codes and the unchanged operational numerical policy. The normal-user /source and /configuration access denials remain recorded. Only their redundant checks are substituted after verified equivalent inputs. Independent PM review of this new profile remains required; independent cryptographic/scientific UTC remains NOT_PROVEN.

## Actual source and scientific meaning

source-discovery/ records an earlier3-GET observation:3751 discovered,55 provisionally eligible,9,442,584 bytes,104 estimated weight, observed header peak604, advertised minute6000, effective cap5500. It evaluated zero candle packets and is NOT full-market proof.

The separately labelled bounded-full-market folder is the actual fresh same-boundary preflight on the final pinned release, if it ran. Its exact result, clock witnesses, per-request receipts, inclusion/exclusion metadata and hashes govern the outcome. Do not infer N/N from the earlier discovery or from synthetic tests.

Legacy-source replay is a NEW OFFLINE calculation at the maximum recorded response receipt of CLOCK73 original AAVE/ADA data, not rewriting the historical live1/45 result. Both UP/DOWN yielded NO_TRIGGER for both assets. OOS/forward/precision/recall/calibration/after-cost returns remain unproven. Original raw source data on D is hash-indexed; full market body redistribution is not part of this packet. Research intake can reproduce from those originals locally; GitHub-only checks reproduce engineering tests and exact receipt bytes, not unavailable historical raw bodies.

## Remaining acceptance gates

No autonomous24h start: first bounded N/N (G1), independent exact-code/clock-profile/evidence PM review and least-privilege logoff/reboot/STOP deployment proof (G2), separate owner exact-head merge/deployment approval; only then finite24h48 boundaries/288 health slots (G3). No Telegram test/send, SQL, Stage06 or trading in this package. The package does not grant scientific approval.

No local original was deleted. SHA256SUMS.json covers every allowed artifact byte-for-byte; verification from a second GitHub clone is separately reported.

## Final bounded live result (2026-11-21 13:00 Riyadh / 10:00 UTC)

HEAD 8c52be6f9c5d7a49af19bf68b1d8d50bd63a5b72; TREE dcf6a9b1abc2a62c9b91891e605dfcbdccf2bd98. Clean GitHub-only checkout. Discovered 3751; eligible 56; validated 56; missing 0 at common D 10:01:01.771674Z. MARKET_COVERAGE_VERIFIED for ONE snapshot. Actual 227 GET, estimated weight 552, observed minute header peak 2036 versus effective ceiling 5500, 9,666,506 body bytes. Two workers; 59.485s capture; 0.270291s mean request; 0.281s p95. No retries/unknown requests/halt; 90/110/120 timing limits unchanged.

Three actual normal-token clock witnesses passed the operational numerical policy. Maximum conditional proxy 0.1110934s; maximum recorded sync age 139.0043s. Original RPC denials retained. Independent UTC NOT_PROVEN; new equivalent-profile PM review pending.

Hash-verified source intake replayed all 56 final-D inputs: UP 55 NO_TRIGGER/1 CANDIDATE_SHADOW_ONLY; DOWN 56 NO_TRIGGER. Zero qualified/publishable signals or future-outcome claims. Two-second external process-tree samples are observations, not continuous resource guarantees.

G1 bounded operational source coverage PASSED for this snapshot. G2 independent review/deployment/logoff/reboot and G3 actual 24h remain OPEN. No task enabled, runtime changed, Telegram, SQL or trading. Original source bodies retained privately with hashes; only permitted receipt metadata/clock originals are published.
