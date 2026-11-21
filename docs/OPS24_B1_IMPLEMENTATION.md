# P0-OPS-FULL-MARKET-24H-001 — B1 engineering package

Authority: Issue51 comment 7059836760 and PM governance Draft PR75. Base main: 7b7bb0ebdf0bb601cf1f468c0146c784cb8e0a5f, TREE ac9b9fd8b0c7801183589b027cba1082d616f32b. Development uses an isolated D: worktree. Root MASTER/README and CLOCK74 are preserved.

## Architecture selection and risk sheet

| Decision | Implementation | Acceptance limitation |
| --- | --- | --- |
| B1 first | New ZS_OPS24_B1_REST_V1; dynamic 3+4N requests / 104+8N estimated weight; two workers | Actual full-market latency and N/N need trusted operational time and measured evidence. |
| Quota | Atomic durable request/weight/body/in-flight reservations; advertised one-minute quota minus 500 reserve, capped at 5500 | Shared-IP headers cannot guarantee future headroom. 429/418 latch a stop. |
| Time | One frozen inventory/boundary, four frames, 22 closed 5m bars, exact parent reconciliation, common final D | Existing 90s freshness, 110s capture and 120s watchdog remain. No cross-boundary aggregation. |
| Bounds | Two workers by default, at most four by config; 8s request timeout; 16MiB discovery body / 256KiB candle body / 32MiB cycle | 45 pairs require 183 GET / 464 estimated weight. At two workers, approximately 93L plus clock/processing is needed; L=1s already exceeds 90s. This is a calculation, not a live benchmark. |
| Recovery | Reserved/committed/failed ledger, original SHA, atomic fsync metadata, explicit complete-receive reconciliation | Unknown/incomplete requests are never resent; stale/stepped snapshots remain incomplete. |
| Clock | RSA-signed short-lived operational witness, bound to code/policy and reassessed raw observations | Protected publisher/key/ACL deployment and renewal are NOT installed or proven. Normal-worker live evaluation stays blocked. |
| Worker | Normal token, singleton, signed finite 24h activation, default DISABLED, durable slots/breaker | No task/service enabled; S4U/logoff network and actual Windows reboot remain NOT PROVEN. |
| Resources | 512MiB working set, 1GiB spool, 512MiB minimum free, 60 CPU-seconds/capture | Caps produce HOLD; evidence is not deleted to manufacture uptime. |
| Effects | Research and null signal IDs | No sender, operational archive, SQL provisioning or trading path. |
| B2 fallback | Separate stream/cache source design if B1 measurements cannot meet timing | Not implemented or activated here. |

## Source and causal contract

Every supported eligible pair is queued from dynamic discovery, without a popularity whitelist. Non-USDT/missing-policy exclusions remain explicit. Cycle identity binds release and boundary. All packets are re-evaluated at one final decision D, including oldest book/ticker/context freshness. N/N requires every pair's valid four-frame evidence under that same inventory and boundary. Unknown/late/missing pairs are not counted.

The ledger reserves request/weight and maximum response bytes before HTTP, with bounded in-flight work. Bodies are fsynced before metadata and SQLite commit. A known committed body can be read without another HTTP request. Complete original bytes plus metadata may explicitly reconcile a crash before commit; missing/unknown responses stay HOLD. A complete capture's stored receipt is hash-checked on replay and is not a new sample.

Estimated quota is not proof of current IP headroom. The first exchangeInfo must advertise a valid minute weight limit. The client adopts a stricter server limit when necessary. There are no automatic retries through 429/418 or unknown receives.

## Normal worker and protected clock

ops24_clock verifies RSA3072+ signatures against a pinned public key, binds HEAD/TREE and the owner-approved operational clock policy, re-assesses signed Windows Time observations, and limits witness age to 30s. Invalid signatures, future/stale data, wrong code/key/source/policy and wall/monotonic/boot changes cause HOLD. This does not prove independent cryptographic UTC for signal science.

The administrator-only collect function executes only the fixed Windows Time command list. No signing key, privileged recurring publisher, certificate or trust directory is provisioned in this package. The publisher's code/import chain, admin-only private key, parent directory ACLs and unmodifiable worker public-key pin need security review. The worker checks admin/SYSTEM ownership and denies nonprivileged mutation rights along that trust chain; a writable pin is refused. These checks and owner-Windows deployment proof. A JSON accepted flag alone is insufficient. G2 remains OPEN.

InstallDisabled creates a disabled release pointer and SHA-checked Git bundle. BuildTask emits disabled S4U/LeastPrivilege/IgnoreNew XML, uniquely named per owned root. Register/Enable refuse a missing protected authority and require signed proof hashes for engineering, full-market, normal-worker, stop/rollback and owner merge gates. No bare enable flag starts a worker.

Stop/Disable have independent markers. Upgrade requires disabled state and an exclusive lock. Restore checks a local bundle into a fresh directory and verifies HEAD/TREE. Rollback restores a verified previous disabled pointer. The active order007 installation is untouched. A least-privilege XML alone does not prove network access after logoff or reboot recovery.

## Stability and science

The frozen 24h journal enumerates 288 health slots and 48 half-hour opportunities with PLANNED/CLAIMED/PASS/PARTIAL/HOLD/MISSED states and payload hashes. Unknown reservations survive restart. Three failures latch a breaker; bans and unknown requests require explicit recovery. Monotonic session heartbeats supply an observed uptime lower bound and an unobserved-time upper bound. A complete wall-clock window and fixture PASS slots without observed sessions cannot pass 24h stability. CPU/memory/disk, queue completion, clock, quota, missed slots and corruption affect status. No 24h completion follows from simulating slots or merely running a process.

ops24_science verifies original bodies, reconstructs common-decision inputs and replays directional outputs. It does not mutate real qualification registries or invent outcomes. Existing hypotheses remain development-only. Independent PIT, preregistered DEV/OOS/forward, costs, sample size and directional scientific acceptance remain open; precision/recall/calibration/after-cost returns stay unavailable without eligible outcomes.

Telegram, 05C human interaction, actual archive and SQL require their separate scopes. No accepted Telegram test is repeated here.

## Operator commands

Windows 11, Python 3.12.10, PowerShell 5.1, D:\ZS-SMART-GATE. Optional operational witness dependencies are pinned in requirements/ops24-clock.txt. An audited existing D: dependency directory can be supplied to tests without modifying the installed venv.

    powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\ops24-windows-acceptance.ps1 -ExpectedHead <HEAD> -ExpectedTree <TREE> -Output D:\ZS-SMART-GATE\validation\fresh-ops24-evidence -Dependencies <audited-D-dependencies>
    python -B scripts/ops24-bounded.py --observe-source --output D:\ZS-SMART-GATE\validation\fresh-observation

Observation makes at most three sequential public discovery GETs and holds full candle evaluation while protected clock deployment is absent. It records actual response bytes/hashes, current advertised quota, real headers and provisional inventory counts. Host-time conditional eligibility is not a trusted N/N decision.

After PM and owner exact-head merge/deployment review, controller operations are InstallDisabled, BuildTask, Status, Stop, Disable, Restore and Rollback. Actual Register/Enable require the protected authority and signed gate evidence. Until then G1/G2 are blocked and G3 is NOT_STARTED.

One Draft implementation PR and original Windows receipts are synchronized to the private official GitHub repository and independently restored. Only new/affected tests plus the single CLOCK74 final-response compatibility regression run; the unchanged 91-test baseline is not repeated.

Offline legacy research intake can additionally verify the pinned original CLOCK73 response bytes and calculate a new common-decision research replay. It preserves the original live 1/45 result and labels its later offline calculation separately. It does not rewrite the original runtime outcome or create prospective/OOS evidence.
