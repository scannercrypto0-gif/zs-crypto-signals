# OPS24 acceptance evidence — scope and exclusions

Implementation PR: #76; governance PR: #75 (untouched).
Code HEAD fda01bb5317ef2ed12697d3e6993796b2ae52d42; TREE 2594b47632100b561dff0a0f4309e1779d91dde7.
Windows11 normal token, Python3.12.10, native PowerShell5.1.26100.9818. Installed runtime remains 25210a1e152a92e0562e108f3d1fc16e4e1b61ab, disabled. Main remains7b7bb0e.

## Original tests and reconstruction

- windows-tests/OPS24-20261121-pinned-evidence/acceptance.json: final39 tests, zero failures/errors/skips/Python network attempts, clean exact release. Includes single historical CLOCK74 regression only.
- windows-tests/OPS24-20261121-github-reproduction/acceptance.json: same39 cases reproduced in a fresh private GitHub clone, same HEAD/TREE. No local source worktree dependency.
- Other windows-tests directories and historical-iterations hold original earlier test outputs, each retaining their actual head and counts (30,34,35,37,38). They are not extra independent evidence for scientific performance. Failures encountered during normal-clock investigation remain in clock-provenance rather than being erased.
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
