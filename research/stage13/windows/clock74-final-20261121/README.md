# CLOCK74 final Windows acceptance evidence

Status **READY_FOR_PM_REVIEW** for the bounded engineering correction. The actual tested source branch is fix/clock73-offline-11th-receipt, HEAD 3e360d7471fa6d7270ededd77660392e80c8b250, TREE ac9b9fd8b0c7801183589b027cba1082d616f32b. Main baseline is 25210a1e152a92e0562e108f3d1fc16e4e1b61ab. PR74 source is pushed independently of this evidence branch, so the PR's final source HEAD itself has been tested. This branch adds receipts only and is not proposed as a replacement runtime checkout.

## Executed acceptance

Owner Windows 11, Python 3.12.10, Windows PowerShell 5.1.26100.9818. Nine affected suites, **91 tests / 91 passed / 0 failures / 0 errors / 0 skips**, each child exit 0, overall driver exit 0. Source clean before/after with unchanged HEAD/TREE. Python socket/urllib network-attempt counter was zero. The existing eight suites contribute 86 tests; five additional tests cover final-response hard stops and compact output against actual production summary code.

The final raw acceptance.json SHA-256 is **d3a1317ea93b0ce1e0b901a40cfc52bd7a08e8e3e5820855d7695fc759923f02**. accepted/ contains exact original stdout/stderr bytes, structured per-suite counts, original hashes and inner manifest. Its paths refer to the owner-local original directory D:\ZS-SMART-GATE\validation\CLOCK74-ACCEPTED-20261121-evidence. No log line ending or encoding normalization was applied on publication.

| Requirement | Evidence |
| --- | --- |
| Valid response 11 accepted, request 12 prevented | test_exact_eleventh_http_receipt_accepted_twelfth_forbidden |
| Two complete pairs / eight candle-frame requests / 11 total GETs | test_two_pairs_exactly_eleven_http_second_pair_evaluated |
| Actual deadline / observed-weight stops on response 11 | test_eleventh_response_deadline_and_observed_weight_still_stop |
| Response and cumulative-byte boundaries retain original body/hash | test_eleventh_response_size_and_total_byte_guards_preserve_original |
| Estimated-weight boundary and next-request refusal | test_estimated_weight_exact_cap_accepts_response_then_stops |
| Cursor restart / no repeated claim / specific vs legacy stop reasons | Existing marketwide capture/research tests, including the formerly failing test_restart_quota_and_no_repeated_claim |
| Compact Python summary preserves large result file | test_python_compact_output_preserves_large_original_and_no_delivery |
| Actual PowerShell 5.1 summary block, result/journal hashes, fallback stop reason | test_powershell51_actual_summary_block_and_hash_pointers |

All HTTP/clock inputs in these acceptance cases were injected fixtures. No live SHADOW was started. The PowerShell integration test executes only the parsed hash function and summary-output block against synthetic files; the installed runtime manager is not invoked.

## Changes and corrected harness iterations

The inherited dd541853 fix retains the legacy QUOTA_CONNECTIVITY_OR_DEADLINE label only for an empty PauseScan, while explicit reasons remain precise. Runtime request/weight/body/time/clock limits are identical to that inherited repair.

New source files are scripts/clock74-windows-acceptance.ps1, scripts/clock74-offline-tests.py and tests/test_clock74_acceptance.py. Updated docs/CLOCK73_OFFLINE_CORRECTION_AND_COVERAGE.md supplies quantitative A/B design and acceptance semantics.

The new harness initially needed two Windows-specific corrections. PowerShell 5.1 required resolving PSScriptRoot after parameter binding. It also required caching the Process handle before waiting so actual child exit codes remained available. The intermediate 91-test pass had missing exit codes and was explicitly rejected by the harness; it is retained in harness-iteration-not-accepted/. Final accepted receipts have actual exit 0 for all children.

The original e41a25520eeba3bf5bca977b1c257d1d9de2dc17 run (85/86) is preserved in historical-85-of-86/. Its failed test is historical, not attributed to the final HEAD. Earlier failed setup/driver logs are retained in drivers/. No prior evidence was overwritten or erased.

No Windows service, registry, clock configuration, installed runtime or scheduled task was changed. The acceptance command uses an ExecutionPolicy bypass limited to its PowerShell process; no persistent execution-policy mutation occurs. The offline test process guard does not claim to be an operating-system firewall.

## Reproduction

From a clean isolated source checkout under D:\ZS-SMART-GATE, use Windows PowerShell 5.1:

    powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\clock74-windows-acceptance.ps1 -ExpectedHead 3e360d7471fa6d7270ededd77660392e80c8b250 -ExpectedTree ac9b9fd8b0c7801183589b027cba1082d616f32b

The script chooses a fresh D: evidence directory, runs only the affected suites, preserves original streams and exits nonzero on any missing/failed/dirty evidence. It does not install/restore the active runtime or open a live pilot.

## Coverage design decision

Current two-pair acquisition needs 3+2*4=11 GETs and estimated weight 120. Forty-five eligible pairs need 183 GETs and estimated weight 464, beyond current 11/140 limits. Existing 90-second timing, 110-second capture and 120-second watchdog remain effective. With four hypothetical workers and four seconds of clock cost, illustrative per-request latencies 0.25/0.75/1.5/2 seconds imply approximately 16/40/76/100 seconds before decode/flush/jitter. These are calculations, not new measurements or runtime authorization.

Recommend A for immediate bounded acceptance, with sample 2/2 distinct from overall 2/45. B requires a separately approved source/budget/concurrency design and a final common decision that revalidates all inputs' freshness. The updated source document specifies durable reservations, incomplete cutoff closure, recovery and the prohibition on joining different inventories/boundaries into one full-market claim.

The next step is independent PM inspection of the pinned source and these raw receipts, followed by the owner's architecture/merge decisions. Scientific qualification, full eligible-market coverage and operational readiness are outside this engineering acceptance. There were no market/bot calls, SQL writes, scheduling, production activation, trading or main merge in this task.

## Publication custody

GitHub is the primary repository and authoritative project record. Both source and evidence are published in the official private repository. The root SHA256SUMS covers every evidence file recursively. Scoped .gitattributes rules preserve original bytes on Windows. Publication is accepted only after independent remote source/tree and receipt hash verification; that result is recorded in the PR74 handoff.

