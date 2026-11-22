# Explicit Microsoft catalog member proof — implementation and evidence

Original daa6222 actual Password-logon scheduled Health still failed SYSTEM_BINARY_SIGNATURE_UNVERIFIED, normal_token=true, probe_observed=true, cleanup=true. Changing logon alone did not fix it. Original probe hash verified against task report; raw results retained. Four NotSigned/None binary results and one embedded Valid are preserved. No claim of exact internal Windows catalog-discovery cause.

New source head 28b5b2ad6d9c03adb1795b313fa11db9dc252ee7, tree 671d1a033c9c864dc5640e67253e2f5824f945f8:
- Explicit native WinVerifyTrust WTD_CHOICE_CATALOG verifies actual SHA256 SIP member digest, catalog membership and Windows chain. Signed-catalog embedded Authenticode, Microsoft signer, catalog/binary SHA256 and protected Windows store/ACLs must independently match. Original NotSigned is not rewritten.
- Protected read-only catalog-location map is DISCOVERY_ONLY_NOT_ACCEPTANCE. Actual worker recalculates/cryptographically verifies; no cached success accepted. Only NotSigned auto-discovery gets separate evidence; HashMismatch/unknown errors remain rejected. No trust roots or Windows ACLs modified to force trust.
- Native DLL loaded from absolute Windows system directory, handles closed, file/catalog byte limits, bounded discovery process/signature subprocess/task watchdogs, partial diagnostics retained. Revocation freshness and independent scientific UTC are not newly proved.
- Health diagnostic only currently uses this catalog-bound path; existing production Serve/default observer is not silently migrated or enabled. Independent PM review explicitly pending for the signature method.

Validation: Windows controller 8/8, clock 10/10, native catalog 3/3 = 21/21 PASS; independent fresh GitHub source clone reproduces all 21. Zero failures/errors/skips/Python network attempts. OS-native trust functions may use Windows trust facilities; Python socket counters do not attest that native networking is impossible. No Binance/Telegram/SQL calls.

Native positive test verifies real Windows sc.exe and its Microsoft-signed catalog. Modified .text byte is rejected by native WinVerifyTrust despite the original real signed catalog. Negative metadata tests reject bad binding, signer, changed hashes, writable/missing catalog ACLs, original HashMismatch and boolean native result.

Additional credential-authenticated standard-account diagnostic (admin=false) binds four original NotSigned rows to fresh native code=0 member proofs and Valid Microsoft catalog signatures, retaining NotSigned. This is NOT a scheduled clock acceptance: source registry/signature-state input is historical, not a fresh time witness. Direct Python profile/loaded-profile/correct-profile-environment comparisons remain separately labelled diagnostics. Local account SIDs and private user environment are redacted, original hashes retained. Parent process exit unavailable is not invented. Derived module caches excluded. No secret/ciphertext or Windows catalog/binary bytes uploaded.

Actual corrected scheduled catalog-bound Health remains PENDING administrator execution. No full clock/24h/logoff/reboot/scientific/production GO, no merge. PR76 Draft. Standing owner permissions cover this finite Windows diagnostic; no new owner approval requested.

References:
https://learn.microsoft.com/en-us/windows/win32/api/wintrust/ns-wintrust-wintrust_catalog_info
https://learn.microsoft.com/en-us/windows/win32/api/mscat/nf-mscat-cryptcatadmincalchashfromfilehandle2
https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-winverifytrust
