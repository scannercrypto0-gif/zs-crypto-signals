# P0-OPS-FULL-MARKET-24H-001 — B1 engineering package

Authority: Issue51 comments 7059836760/7059859495; PM governance Draft PR75. Base main: 7b7bb0ebdf0bb601cf1f468c0146c784cb8e0a5f, TREE ac9b9fd8b0c7801183589b027cba1082d616f32b. Isolated D: worktree; installed runtime and root MASTER/README/CLOCK74 preserved. This package does not start a service.

## Architecture and risk decisions

| Decision | Implementation | Limitation |
| --- | --- | --- |
| B1 first | ZS_OPS24_B1_REST_V1; dynamic 3+4N GET / 104+8N estimated weight; two workers | N/N requires actual same-boundary proof. No popularity whitelist. |
| Quota | Atomic durable request/weight/body/in-flight reservations; advertised minute quota minus 500 reserve, capped at 5500 | Shared-IP headers cannot guarantee future headroom; 429/418 stop without retry. |
| Time | Frozen inventory/boundary, four frames, 22 closed 5m bars, parent reconciliation, common final D | Preserve 90s freshness, 110s capture, 120s process-tree watchdog. No stitched boundaries. |
| Resources | Two concurrent workers (policy supports at most four), 8s timeout, discovery body 16MiB, candle body 256KiB, cycle 32MiB | Observed discovery N=55 implies 223 GET/544 estimated weight. Two workers need roughly 113L plus clock/decode/storage overhead; L=1s already exceeds freshness. This is a feasibility calculation, not a benchmark. |
| Recovery | Reserved/committed/failed ledger, SHA-256, fsynced original bytes and metadata, explicit complete-receive reconciliation | Unknown/incomplete requests are never automatically reissued. |
| Clock | Normal-token live Windows status + protected OS configuration provenance, versioned equivalent profile | Original RPC denials retained; operational time only. Independent cryptographic UTC is not proven; PM review pending. |
| Worker | Normal token, singleton, finite reviewed activation, DISABLED default, durable slots, breaker/backoff | Task/network after logoff and real Windows reboot are not proven. No task registered/enabled. |
| Resource caps | 512MiB working set, 1GiB spool, 512MiB minimum free, 60 CPU-seconds/capture | Caps HOLD and retain originals; no deleting evidence to manufacture uptime. |
| Effects | SHADOW/RESEARCH_ONLY, null signal IDs | No Telegram sender, operational archive, SQL or trading path. |
| B2 fallback | Separately reviewed streaming/cache contract if B1 cannot meet timing | Not implemented/activated; no covert freshness increase. |

HTTPS uses a verified TLS connection per worker (REST_HTTPS_KEEPALIVE_THREAD_LOCAL_V1), reused across its requests, without proxies, redirect following or application retries. Unknown acknowledgements stop rather than triggering a transparent resend. Live latency must still be measured.

## Source and causal contract

Dynamic discovery covers every supported eligible Spot USDT pair and records exclusions. Each cycle binds release HEAD/TREE and boundary. Complete four-frame receipts are reconstructed and re-evaluated at one final decision D after the final clock check. Oldest ticker/book/context freshness and closed-candle alignment remain mandatory. N/N means every eligible pair is valid under the same inventory and decision window; missing, late and unknown inputs remain explicit.

The SQLite WAL/FULL ledger reserves request, weight, maximum response bytes and in-flight capacity before HTTP. A second clock/STOP check precedes physical transport. Raw body and metadata are fsynced before commit. Hash-verified committed responses replay without HTTP. Complete original bytes plus matching receipt metadata may explicitly reconcile a crash before commit. Unknown receives cannot be resent. Stored results have immutable hash readback, not new sample identity.

The first exchangeInfo must advertise one minute REQUEST_WEIGHT. A stricter server ceiling is adopted. Response weights, bans, body limits, clock failure and wall/monotonic step stop the capture. There are zero automatic retries. The historical CLOCK74 11th-request rule is unchanged; this new policy is separately versioned.

## Normal-token operational clock equivalent

WINDOWS_STATUS_PROTECTED_REGISTRY_V1 calls fixed native System32 Windows commands, reads 64-bit HKLM W32Time/NtpClient and autotimesvc configuration, checks optional GPO overrides, protected registry ownership/DACLs, OS service SIDs, native image/DLL paths, Microsoft Authenticode signatures and binary ownership/DACLs. No caller-provided JSON accepted flag supplies time authority. No key provisioning or digital signature of operator approval is required.

Only the exact redundant SOURCE_COMMAND_FAILED and CONFIGURATION_COMMAND_FAILED RPC blockers can be substituted after these provenance checks and valid active status source. Raw exit codes and original blockers are retained. Every other existing check stays mandatory: allowlisted time.cloudflare.com, NTP enabled, running service, sync age <=600s, four distinct samples, offset and conditional proxy <=0.5s, discontinuity/step <=0.05s. Refresh every <=20s with intervening age/step checks; step during observation also stops. Raw witnesses are hashed and referenced at HTTP start/receipt and final decision. This is the already approved operational numerical policy under a NEW observation profile, pending independent PM review, not proof of independent scientific UTC.

## Disabled-first worker and recovery

InstallDisabled creates a pinned release pointer and SHA-checked Git bundle. BuildTask emits disabled S4U/LeastPrivilege/IgnoreNew boot XML uniquely named per owned root. Register/Enable require authenticated owner SID, exact release pin, PM review reference and hash-linked engineering/full-market/normal-worker/stop-rollback/owner-merge proofs; no bare enable flag starts it. A full-market proof requires actual eligible=validated>0, missing=0. Reviewed deployment must supply these records; none is fabricated here.

Status/Stop/Disable are independent commands/markers. Upgrade requires disabled state and exclusive lock. Restore verifies a bundle into a fresh checkout. Rollback verifies a previous disabled pointer. The installed order007 runtime is untouched. Disabled XML and simulated restarts do not prove real logoff networking, reboot recovery or a 24h run.

## Stability and science

The finite 24h journal enumerates 288 five-minute health slots and 48 half-hour opportunities, each PLANNED/CLAIMED/PASS/PARTIAL/HOLD/MISSED with immutable payload hash. Unknown claims survive restarts; three failures latch breaker/backoff. A completed wall-clock window and fixture PASS slots cannot replace actual monotonic session heartbeats and 24h observed uptime. Per-boundary N/validated/missing and request/capture mean/p95 remain separate from process availability.

ops24_science hash-verifies original bodies and reconstructs common-D research inputs. Legacy CLOCK73 replay verifies the original manifest/result SHA, preserves the historical live 1/45 result and labels any later calculation OFFLINE. Neither replay is new prospective or OOS data. Independent PIT, DEV/OOS, forward, costs, sample size and UP/DOWN scientific acceptance remain open. Precision, recall, calibration and after-cost returns remain unavailable without qualified outcomes.

## Reproducible Windows commands

Windows11, Python3.12.10, PowerShell5.1, D:\ZS-SMART-GATE. New implementation uses Python standard library only; no venv changes.

    powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\ops24-windows-acceptance.ps1 -ExpectedHead <HEAD> -ExpectedTree <TREE> -Output D:\ZS-SMART-GATE\validation\fresh-ops24-evidence

The wrapper invokes only affected suites plus one CLOCK74 final-response regression behind a Python network deny guard. It records original stdout/stderr, checksums and clean HEAD/TREE. It does not rerun the unchanged91-test suite.

A source-only observation makes at most three sequential public discovery GETs and cannot claim full-market evaluation. One separately explicit bounded preflight starts on the current declared UTC30m boundary (epoch seconds), in a fresh directory and clean checkout:

    python -B scripts/ops24-bounded.py --full-market-preflight --boundary <UTC-epoch-seconds> --output D:\ZS-SMART-GATE\validation\fresh-full-market

No Telegram, SQL, trading or recurring collection. Operational/scientific clock statuses and actual N/N/partial counts must be read from its receipts. Source raw bodies are retained privately on D: with hash/byte manifests; only rights- and privacy-screened evidence is published to the private GitHub repository, then restored and hash-verified in a clean checkout.

## Remaining gates

G1: measured bounded full-market N/N, not source discovery alone. G2: independent PM exact-code/clock-equivalence review, actual least-privilege deployment/logoff and STOP/recovery/reboot proof, separate exact-head owner merge/deploy approval. G3: only then start the finite24h read-only soak and account for every slot. No merge or unattended enablement here. Scientific signal quality and production delivery remain separately gated.
