# Scheduled standard-token clock provenance correction — 2026-11-22

Original administrator-run 8acea8a probe is preserved unchanged: registered=true, probe_observed=true, normal_token=true, session=0, clock=BLOCKED, cleanup=true. Its raw probe SHA matches task report. This establishes actual scheduled normal-token execution, not clock/full operational acceptance. Native retained stderr establishes SERVICE_SID_QUERY_FAILED at sc.exe showsid.

Fix head 4b173811970c65f6b1a79f6b569963ff9d8f016b, tree 158ad8a038cbc8647fd9642c5d951732ff800dda replaces this identity lookup with Windows NT SERVICE name-to-SID translation. Same exact service identity shape/distinctness checks, signed-binary set, registry ownership/ACL, active source, sync age, quorum, offset/step and scientific-time limitations retained. No worker elevation, SCM permission grant, ignored failed command or synthetic witness. Old clock evidence not reinterpreted.

Affected Windows clock tests 9/9 PASS; fresh GitHub source clone independently reproduces 9/9, zero failures/errors/skips/Python network attempts. Actual native test compares translated service SIDs to original sc.exe showsid under the normal operator; this does not claim scheduled-worker equivalence is physically proved yet. Corrected S4U Health pending administrator execution on fresh root, reusing existing DPAPI-protected standard worker credential with no password reset. No secret/ciphertext uploaded. No Binance/Telegram/SQL calls or merges. PR76 Draft. Reboot/logoff/24h and independent scientific time remain unproved.

Microsoft service SID mapping reference: https://learn.microsoft.com/en-us/windows/win32/api/winsvc/ns-winsvc-service_sid_info
