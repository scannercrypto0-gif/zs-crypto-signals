# Actual scheduler launch; clock provenance collection HOLD

Original 8c8c84b administrator-run task registered, started at 2026-11-21T14:00:26Z and exited 2. Stdout: NORMAL_CLOCK_OS_PROVENANCE_UNAVAILABLE. Original stdout/stderr/task report/exit retained unchanged; manifest hashes match native report. This establishes process launch, not clock acceptance or full probe success.

Source fix head 8acea8a86f6d9d86f664af7f488fd7f7b7e404a5 / tree 7ac2612914c7b7bda97b09296d905dad751dfb77 preserves native provenance child stdout/stderr/exit/hash, and writes actual probe identity/resources before propagating clock HOLD. No permission/signature/time guard is bypassed. Exact underlying native failure is still UNKNOWN until next actual run captures it.

Previous account has a Windows profile, so it is not reset/deleted. Subsequent setup uses a new fixed reusable ZS_SG_Worker role, with owner-DPAPI credential CLIXML on D protected owner/System/Admin only. No ciphertext or plaintext may be published. Existing account imports its credential without password reset; missing/orphan credentials HOLD. This supersedes earlier diagnostic-only no-file credential approach and is explicitly documented. No actual new account/credential created by the normal agent; administrator setup PENDING.

Windows targeted suites: controller 7/7, clock 8/8; fresh GitHub clone reproduces both (15/15). No failures/errors/skips/Python network attempts. These tests do not prove actual new role provisioning, clock acceptance, reboot/logoff, 24-hour or live acceptance. Market/Telegram/SQL calls=0 in this repair. PR76 remains Draft; no merge.
