> **OWNER SUPERSEDING DECISION — 2026-10-30:** This file is a historical, unactivated GitHub App permissions proposal, not a current setup instruction. The owner has deferred all Windows runner deployment and the on-device synthetic GitHub App canary until after GitHub-only project development is complete. Do not create/install an App, key, token, or Windows worktree under the previous authorization. GitHub Actions may be used for development CI/tests subject to their own authorization boundaries; it is not the intended production scanner runtime. See [MASTER v1.16](../ZS_SMART_GATE_MASTER.md) and [Issue #11](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/11). Existing code and design details below remain for historical reference only.\n\n# GitHub evidence backend — permission proposal (not activated)

Status: proposal only. No GitHub App, installation, token, secret, repository setting, or storage activation is created by this change.

## Proposed installation scope

- Install a future GitHub App on the single repository scannercrypto0-gif/zs-crypto-signals.
- Proposed permissions: Metadata read-only and Contents read/write. Contents write is required to create claim/receipt files and update the capacity index on a dedicated evidence branch. No Issues, Pull requests, Actions, Administration, Workflows, Secrets, or account-wide permissions are needed by the backend implementation.
- The backend is disabled by default. Activation requires an explicitly constructed transport with a token and enabled=True; no environment or file-based credential discovery is implemented.

## Guarantees and limitations

- Unique paths, create-if-absent, a compare-and-swap capacity index, canonical JSON, SHA-256, and exact readback provide application-level duplicate/corruption detection.
- The private repository currently lacks verified server-enforced branch protection/rulesets under its current plan. A writer with sufficient Contents/ref permissions may alter records or Git history. This is not WORM, tamper-proof, or server-enforced append-only storage.
- The capacity index is a single compare-and-swap point. A stale SHA or HTTP conflict fails closed; no market work is retried. Capacity reservations are conservative and may remain allocated after a failed record write.
- The live GitHub credential path has not been exercised by this PR. All tests use an in-memory mock transport.

## Bounds and approval gates

- Maximum logical journal payload budget: 10 MiB per study.
- Existing outage spool reference: maximum 10 MiB, TTL at most 24 hours. It remains in-memory and is not durable storage.
- The 30-day point is an operational review, not automatic deletion from Git history.
- Before activation, PM/owner must review permissions, retention, branch/trust model, outage policy, and a separate canary plan. No Binance/NTP, Windows runner, Telegram, or study calls are performed here.
