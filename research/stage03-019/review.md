# Order019 temporal-integrity engineering and sensitivity review

Authority: Issue25#6625572882. Read main/MASTERv1.32/README at
a0f8493aee1228bc625360fd55a553cc5c69954f, Issue11/25, PM016–018 reviews,
PR28/29/30 and reviews. Parent30=f8f9507ff45a914edabfdea19c90155d2c7f01d5.
No edits to governance, previous contracts, models, datasets, raw or outcomes.

## 019-A: rule inventory and impact, before changing a previous gate

No previous gate is changed. A new, explicitly weaker protocol is implemented.

| Existing rule/location | Purpose | New manual protocol disposition |
|---|---|---|
|5m closes on300000ms; inclusive source close becomes exclusive +1ms|Avoid forming/future bars|Exact boundary/identity validation plus source x=true; never infer from Windows wall|
|30m↔6×5m and4h↔8×30m; mtf_contracts/integrated016/018|Availability and coherent indicator inputs|All selected parents/children already received; exact continuous spans, OHLC/base+quote-volume sums; no partial parent|
|1d/1w closed context; UTC Monday week offset345600s|No future day/week context|Explicit source-final UTC bars, already received, required; no UTC+8 substitution|
|Source receipt/available <= decision; input digest/epoch/seq|Causal leakage prevention|Zero monotonic slack, identity/hash/claim/revision/epoch checks; after-decision inputs blocked even1ns|
|Latest5m ≤600s / current liquidity age≤10s|Data quality, not UTC certificate|Retained as distinct freshness gates; source delivery uncertainty unknown→UNKNOWN/HOLD|
|018 snapshot-to-decision≤10s|Separate old research freshness policy|Frozen018 unchanged; new manual gate uses input-specific age budgets, not a universal speed deadline; fresh quote still≤10s|
|30m/4h/daily/weekly most recent closed contexts|Context quality|Latest context age≤one own frame duration; incomplete/missing context HOLD, not a full score|
|Historical5m children needed for4h indicator|Closed historical input, not new current bar|Preserve all causal/finality checks; do not require a4h-old child to be a fresh current5m bar|
|Core/scanner eligibility and partial metrics|Original research eligibility, not all V2 scientific features|Frozen.019 only exposes descriptive close/return/confirmed-local-pivot/spread diagnostics, never an approved score|
|V1 UTC<1s; V2 UTC<1.5s; independent calibration/drift|Absolute UTC proof only|Frozen; not a compulsory prerequisite for weaker relative claim. Absolute field stays HOLD|
|Monotonic+epoch and wall/QPC residual discontinuity|Ordering and lifecycle safety|Same-epoch strict monotonic order; >=1s wall/mono discontinuity blocks; fixed wall offset not an absolute-time claim|
|Windows restart/sleep/disconnect/watchdog|Continuity safety|Restored ACTIVE lifecycle coverage and terminal decision fence; heartbeat gaps>60s, explicit lifecycle event or epoch change→HOLD/reanchor|
|Binance endpoint host, UTC/offset stream, raw/schema|Source authority/semantics|Reviewed profile pins empty by default; source marker/stream/schema must match; UTC+8 unsupported; no HTTP/WS client activated|
|Telegram sending/latency|Notification delivery|No sender. Speed not used as an uncertainty ceiling; publishable=false always|

The watchdog60s is a declared application monitoring policy, not a clock drift
specification or delivery SLA.019 validates supplied lifecycle records; it does
not start an OS watcher. A future authorized recorder must actually capture
system/connection lifecycle notifications and watchdog coverage; missing or
unrestored coverage blocks. Hashes/claims/readbacks are application integrity,
not privileged-proof WORM or independent publisher timestamps.

## 019-B: new claim and source finality

MANUAL_RESEARCH_ALERT_CAUSALITY_V1 is separate from frozen prospective V1/V2.
Its only positive state is RESEARCH_CAUSAL_ORDER_PASS_CANDIDATE. Neither
SCIENTIFIC_PIT_PASS nor OOS_QUALIFIED nor PRODUCTION_SIGNAL is emitted.

Every candidate input binds study/source/symbol/frame/event identity, raw hash
and byte count, claim ID/time, receipt monotonic stamp, epoch, hash-chain seq,
diagnostic wall stamp/source/trust, revision and linked supersedes. Decision
cutoff is separate. Raw source close/end and finality marker remain in raw
payload; extracted close/marker result is also exposed per input. Only restored
digest pins are usable. Earlier raw remains preserved on correction; selecting
the superseded value blocks. Default source/epoch/readback registries are empty.

Supported finality route: reviewed Binance UTC websocket kline profile,
raw k.x=true, event E>=T+1, interval/open/close/symbol identity and valid OHLCV.
The source explicitly asserts finality; receipt of that assertion precedes
decision inside the same local epoch. This does NOT establish independent UTC
or original publication history. REST klines have no such flag: old016 REST
samples do not get requalified. No authenticated live websocket capture exists
in019; all newly stored source profiles/inputs are labeled synthetic doubles.

Source references:
- https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md
- https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md

An implemented alternative avoids requiring an unprovided websocket transit
SLA: TWO same-source current-time REST references, both inside the candidate
ledger/claims/readbacks and received before decision. Each has an observed
monotonic send/receive bracket after its claim. Both must be<=10s old, coherent
with each other and noncontradictory with later source-finality events. With
source time T, request send s and decision D, the conservative source-age upper
estimate is (T-close)/1000 + (D-s)/1e9 +0.002 seconds. It uses the FULL request
bracket; two milliseconds cover two integer-millisecond quantizations. Pair
coherence checks the difference of source times against the request brackets.
Inconsistent/stale/incomplete/postdecision references block, not silently fall
back. Nominal local monotonic seconds and short-horizon source consistency are
explicit application assumptions, not independent rate calibration or UTC.
This path is tested with new SYNTHETIC reference replies only, zero actual GETs.
It is a practical future finite capture design subject to its own reviewed
Manifest/request budget/approval, never permission to issue these requests now.

Only semantic facts were used: explicit kline closed flag, interval/timezone
and source timestamps/current-book snapshot semantics. The docs do not prove
a maximum websocket delivery delay. The synthetic50ms transport bound is
explicitly NOT a measurement, SLA or real admitted profile. Field transit
uncertainty is currently UNKNOWN; no field reference pair exists either. A caller cannot obtain field acceptance
merely by using the bundled synthetic profile; real profile admission and
evidence are separate PM/owner gates. No raw provider signing or UTC guarantee
is inferred from TLS/source identity.

Margin choice: wait for an explicit source-final marker, not an arbitrary
close+5s delay. In that route no extra wall-based waiting interval is claimed
to prove closure. If finality must instead be inferred from a time reference,
the worst known source/reference/transfer uncertainty B would require a margin
strictly larger than B. No finite B is established for the current REST data;
therefore that fallback is NOT implemented and returns FINALITY_UNKNOWN.
This is an explicit conservative hold, not an inferred zero-error clock.

## Independent result fields

source_closed_confirmed: source assertion/schema established for consumed bars;
per-input UNKNOWN remains visible when evidence is absent. received_before_decision:
receipt monotonic fence, independent of absolute wall correctness. data_fresh:
latest decision context age tests only; unknown when a required context or
transport-age bound is unavailable. Historical children are labeled separately.
clock_quality: relative same-epoch only, unattested UTC. ABSOLUTE_UTC_PIT:HOLD.
publishable:false / score:null / OOS_QUALIFIED:false / Forward:NOT_ARMED always.

Freshness uses source-local publication lag E-(T+1), an independently reviewed
transport bound when one exists, and observed local receipt age. No packet delay
bound is guessed from a local UTC offset. Book snapshot freshness uses its own
request/response monotonic bracket; worst age starts at request send, after the
claim and before receipt. It is current-snapshot evidence only, not historical
I6/S6 coverage, traded liquidity, fills or complete scientific score.

## 019-C: controlled experiment and what changes the decision

All source data are newly generated, deterministic synthetic data, not market
OOS. Original010–018 samples/thresholds did not select a margin or model. Design
iterations and initial local test/debug runs occurred; this is not claimed as a
blinded preregistered discovery trial or statistical strategy-quality result.
Protocol and generator/results are pinned for exact engineering replay.

Study includes ideal wall, ±1.5/±3/±5s constant offsets, source assertion before
close, open/missing-finality/REST inputs, late30m/4h/day/week and1ns late quote,
stale5m/30m/4h/day/week/liquidity, missing context, unknown transport delay,
jump/restart/sleep/disconnect, duplicate/raw tamper, linked/unlinked correction,
missing child/readback/profile, and an unconfirmed latest pivot. sensitivity.json
states separately whether eligibility, decision state, indicator availability
or actual defined indicator values changed, and why. A blocked calculation is
UNKNOWN, not a fabricated changed numeric indicator.

Constant wall offsets leave relative eligibility/indicators unchanged; they do
NOT prove the offset is acceptable for absolute UTC. Open/future/stale/unknown
cases block indicators. A linked correction can remain eligible while the old
raw persists; superseded input selection fails. The unconfirmed newest bar is
never used as a confirmed pivot. Changing its high can still change the ordinary
closed-bar close-location diagnostic; these are distinct effects.

## 019-D/E: tests, replay, custody and merge disposition

Unit/integration tests cover negative cases, epoch/lifecycle coverage and gaps,
source identity/timezone, exact MTF sums, pivot causality, storage offline,
claim-before-receipt failure/no-retry, durable source+decision restoration and
recalculation. Same field states survive storage. No network or timer tests.
Clean Windows/Ubuntu GitHub-only replay pins018 parent checkout, verifies all
previous172 blobs (excluding the additive .gitattributes line), raw fixture
manifest and exact baseline/sensitivity reproduction with sockets disabled.
Original016/017/018 replay and full foundation CI remain mandatory/unchanged.

PR28=0f8f28dd77057681fd9776e3cc625201b1e2c7b0 (base main),
29=18cc6238112a75321d2b194419cd1a38ec4eb5f0 (base28),
30 starts at f8f9507ff45a914edabfdea19c90155d2c7f01d5 (base29).
They are open Draft/unmerged; reviews are COMMENTED, not merge approvals.
28 then revalidate/retarget29 then30 only after separate owner decisions;
no speculative rebase or retarget. PR27 stays separate. Issue11's older009
recovery evidence is scoped, not a new machine reboot or complete field test.
No rerun of03B3, Stage04 canary, source/time probe or operating-system changes.

Actual remaining gate: field source-finality/transport-profile and lifecycle/
durability evidence are not present for this new protocol. The relative path
has engineering proof with synthetic doubles only; it is not authorized field
capture. Before any future run: frozen NEW study Manifest, source/UTC-stream
semantics/rights, actual transport/freshness/lifecycle evidence or explicit HOLD,
private GitHub quota/cap/storage/recovery review, PM independent approval, then
owner-specific source/start/end/request/byte scope. No sender or service is
enabled here. Historical publisher PIT, scientific score, historical I6/S6,
new OOS/qualified winner and full-project closure all remain unavailable/HOLD.
