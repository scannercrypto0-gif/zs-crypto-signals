# Order020-A: bounded pilot implementation, NOT field approval

Authority: Issue25#6629342692 and MASTERv1.33 on main
f30f3146d253834235fea48ec00cdea9cda135c8. Parent PR30 is019 final
2f4c6266fb88893dbb1f2e1805f28afdacca1bbb. Previous019 engineering acceptance
and016–018 frozen contracts/results are retained, not requalified.

## Exact proposed event and limits

Target:5November2026 06:00:00UTC (09:00 Riyadh). Start window05:56UTC,
hard end06:02UTC (08:56–09:02 Riyadh). This is ONE future5m close for each of
BTCUSDT/ETHUSDT, not two windows. Native Manifest will pin final code, plan,
owner-host+boot hash, freeze time and expiry24h after freeze on GitHub BEFORE
the event. Target must be>=10min after freeze. No automatic rollover or new
target after expiry. A missed event remains missed and requires a new decision.

One fixed public combined websocket URL, no redirects/reconnect/accounts. Max
12min,1200 data messages and2MiB. Native implementation is stricter: declared
message/frame assembly<=8KiB,1200 data frames also, four pongs/second maximum,
raw byte guard counts decrypted wire framing/control too. Exact ping payload
is echoed. Partial/truncated data is never presented as a complete source
message. The library is hash-pinned websocket-client1.9.0; real parser tests use
only byte buffers, with all sockets disabled. TLS cert/hostname checks required.

Six GETs maximum, NO retries: time×2, explicit per-symbol bookTicker×2 and
ticker/24hr×2. Official current weights1+1+2+2+2+2=10 (owner cap24). NO klines,
universe scan or historical archive. REST requests start concurrently AFTER
both target final markers and a preclaimed batch, keeping the current books
within a realistic10s freshness window. Every attempt is counted before child
dispatch; canceled/unknown replies stay explicit, not called successful GETs.
DNS/TLS/body work is killed at5s per child by the native supervisor. No redirects.

For six concurrent replies, the native per-response guard is a stricter32KiB
(owner cap64KiB): even all six hostile replies sum to192KiB below256KiB total.
At the exact native guard it conservatively stops and preserves the received
prefix. This avoids cap+1 reads and shared-budget races. Any error status,
timeout, scope, size or partial reply stops the batch; already-dispatched
attempts remain counted, never silently retried or replaced.

## Prerequisites and independent gate

Native entry requires owner Windows, NOT GitHub Actions, D-only workspace,
venv/Manifest/TEMP/TMP, clean Git checkout at the reviewed SHA, unchanged
host+boot fingerprint, the frozen Manifest read back from private GitHub,
native push permission, capacity, no conflicting project Python collector or
running ZS/SuperKumo task, a new local exclusive lock and remote one-use session
claim. Existing03B3/legacy tasks are never stopped, edited or started.

PM review must be a NEW GitHub Issue25 comment, authored by the governance
account, containing020_FIELD_PREFLIGHT_PASS and a JSON block with exact
code_sha,manifest_sha256,plan_sha256,study_id,host_fingerprint_sha256,
review_role="PM 1.3",independence_statement="PM_REVIEW_NOT_EXECUTOR",
native_github_storage_pass=true,source_rights_and_quota_pass=true and
single_event_scope_pass=true. Comment creation must follow freeze. The runner
fetches it itself, not a local assertion. Shared governance account/persona
separation is an organizational review control, NOT a cryptographic proof of
different humans; executor does not issue that decision. A code/plan/boot
change needs matching new review. Missing/invalid review stops before market.

Current native GitHub credentials are UNAVAILABLE; noninteractive Git clone and
GCM lookup failed safely without displaying tokens or prompting. Connected
GitHub tool can store/read StageA evidence, but that is NOT proof the autonomous
native process has credentials. A separate native-storage probe command is
implemented (GitHub only, zero market), to be run after authentication exists.
No token is copied from the app/browser, persisted, requested in chat or put in
arguments/logs. No login/security setting or budget was changed.

The local D source snapshot was restored from GitHub-pinned blob identities;
89 matching D cache files were read only and96 missing/current files fetched
from GitHub. All185 parent files matched before edits. Native Git checkout is
still pending because authentication is absent; CI uses clean actual GitHub
checkouts, never pretends to be the owner's host. Independent PM preflight and
native write/readback evidence are ACTUAL remaining gates, not presumed pass.

## Source/rights review

Official docs confirm unauthenticated public market-only endpoints and the
combined envelope/UTC kline closed flag. They are technical source semantics,
not a scientific guarantee of absolute UTC or network latency. Private bounded
research storage only; no public redistribution or paid service. PM must review
source/rights/quota as part of preflight; no account keys or support contact.
References:
- https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
- https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md
- https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md

## Receipts, recovery and evidence capacity

Hierarchical claim-before-attempt: a remote one-use session reservation and
remote chunk reservation precede source I/O. Every read/input also receives a
D-local fsynced claim before I/O, and each raw payload/receipt gets a hash-chain
record before conversion/analysis. Raw after a clock fault is still retained.
The entire chunk (individual claims/raws/health/status) is committed and byte-
read back from GitHub at checkpoints<=15s, before the next source-read block.
No new source reads during unknown GitHub durability. This batching avoids
thousands of per-message API writes; it is explicit, not claimed as instant
GitHub persistence of every byte or WORM. A storage error consumes the attempt,
retains the D spool, stops, and never repeats the capture/failed PUT.

Study<=3MiB including frozen files/chunk claims/receipts/terminal reports;
combined020 preparation+reserved field capacity<=10MiB. Record sizes are counted
at serialized bytes;64KiB terminal reserve and512KiB REST/terminal reserve before
new WS reads. GitHub journal API budget<=300. Terminal restore re-reads every
chunk and checks seq/hash/raw chain. Raw streams, forming/non-target updates,
unknown replies and missing evidence stay distinguished. No local deletion.

Native loop samples monotonic/wall and Windows unbiased interrupt time versus
tick count for sleep, detects wall jumps, checks a CANCEL sentinel and source
disconnect, and stops on deadline or gap. OS watchdog/thread and hidden launch
wrapper bound the one process; no service/recurring task is installed. On a hard
exit, D terminal marker plus consumed remote claim indicate incomplete capture;
they do not manufacture a final receipt. Future recovery can upload preserved
evidence for review, never restart collection under the old claim.

## Decision scope and tests

Combined envelope is saved raw before unwrapping. Only the pinned target time,
symbol and5m interval with x=true and source E>=T+1 are candidates; x=false and
non-target messages are not decision inputs. Both source time replies carry
monotonic request/response brackets. Same-source reference coherence/freshness
uses019's limited relative model, NOT independent UTC. Book freshness<=10s and
symbol/raw/claim/epoch/ordering/schema checked; observed spread/volume stay
descriptive. The short sample lacks30m/4h/day/week: overall status ALWAYS HOLD
CONTEXT_INSUFFICIENT, score=null,publishable=false,OOS_QUALIFIED=false and
ABSOLUTE_UTC_PIT=HOLD even if limited field-relative observation is a candidate.

Tests cover bad/missing PM pins, changed scope/code/host, CI/non-Windows veto,
expiry/early window, one-use caps, wrong/truncated/open frames, late data,
inconsistent refs, stale books, HTTP errors, partial batches, cancellation,
source disconnect, storage/readback failure, preserved arrived raw after sleep,
hash-chain corruption and hard end. Simulation outputs explicitly say
SYNTHETIC_CAPTURE_SIMULATION_ONLY, never owner-field execution. Pinned real
websocket parser checks cover ping/pong, fragmentation, truncation, oversized
declared length, server masking, binary and redirect rejection without sockets.

Clean Windows/Ubuntu020-A CI verifies184 original blobs unchanged, pinned019
checkout and parser/test outputs. Full regression CI remains mandatory; these
are not new016–019 research experiments or market calls. StageA source calls0.

## Run instructions after independent approval ONLY

1. Establish native repo-scoped GitHub access without exporting credentials;
   clone/check out the final approved SHA in a CLEAN D folder. All project
   files/dependencies/cache/temp stay D. Do not change deployed tasks/03B3.
2. Read the immutable GitHub Manifest/plan, check native storage with
   scripts/check-020-native-storage.py and let PM review that real receipt.
3. Only if PM registers the exact preflight pass, use the hidden one-shot
   scripts/launch-020-approved.ps1 with the pinned Manifest/comment ID inside
  05:56–06:00UTC on the chosen date. No Codex/model needs to remain open.
4. Missing/late approval, auth, boot/host change or expired target means
  020_FIELD_PREFLIGHT_BLOCKED; do not reschedule/rollover automatically.

No PhaseB command, task or socket has been started by StageA. Owner decision
already covers exactly the one scoped event AFTER PM acceptance; do not ask
again for those same six requests, and do not self-certify PM acceptance.
