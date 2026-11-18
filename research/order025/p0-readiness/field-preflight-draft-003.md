# ZS03 single future field feasibility — preflight DRAFT 003 / NOT ARMED

Authority: https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/25#issuecomment-6704626219
Owner provisionally accepted Option A for custody ONLY. This is NOT a live schedule, command, field acceptance, PIT proof, or changed MASTER. Stage03 OPEN / Stage05 FULL HOLD.

## Gate matrix — ALL required before market connection

| Gate | Required independently reviewed evidence | Current verdict |
| --- | --- | --- |
| Event identity | Freeze one study/event ID, code SHA, manifest digest, UTC future window, responsible operators and cancel logic | BLOCKED / DRAFT |
| Host | GitHub Actions Ubuntu temporary DEVELOPMENT host or evidenced equivalent; ONE manual bounded event after new authority; no cron/live CI and no Windows production inference | DRAFT |
| Owner custody | Receipt really downloaded, stored outside writer permissions, locally hashed and owner-acknowledged; fresh read-only raw restore and failure plan | OWNER_CUSTODY_ACK_PENDING |
| Clock | For EVERY event receive AND decision, independent authenticated NTS witness with exact same selected peer across chronyc sources/authdata/ntpdata/tracking; interval uncertainty strictly <1.5s, no stale/source switch/sync fail | BLOCKED / NO EVENT WITNESS |
| Stamp margin | Existing +0.100-second local stamp overhead is UNMEASURED; calibrate and justify upper bound on real approved host; prior single real 0.115796-second NTS sample cannot be reused as future event proof | BLOCKED |
| PIT causal logic | Source candle close/availability, local receive time and decision time with signed uncertainty bounds; latest possible input availability <= earliest possible decision; otherwise reject | BLOCKED |
| Legal source rights | Verify actual Binance Spot public API terms and versions, permitted local/private retention, redistribution/use/country restrictions, lawful raw custody and duration; record reviewer/links/date | BLOCKED / UNVERIFIED |
| Exact endpoint quota | Freeze official REST paths and physical weights plus exchange/IP rate limits, websocket streams/message/subscription limits, 429/418/backoff behavior, retries/timeouts; cite current primary docs and calculated worst case | BLOCKED / UNVERIFIED |
| Physical request caps | Up to 12 REST GET attempts TOTAL (all retries included) and up to 12 physical WS subscriptions TOTAL including retries/resubscribe; hard counters committed before each attempt, fail closed if missing | DRAFT / NO CALLS |
| Event/time limits | BTCUSDT, ETHUSDT, Binance Spot PUBLIC ONLY, duration <=60 minutes; new spending USD 0; stop on any fee/over-budget/unverified rights | PROPOSED ONLY |
| Recoverability | Source raw original bytes, digest, byte count, code SHA, manifest SHA, clock evidence, exact request counters, read-only fresh restore, owner-external receipt, independent checksum confirmation | SYNTHETIC ONLY |
| Science | D1/D2/D3/D5 and required sample sizes and DEV/OOS/Forward need independent freezing; one feasibility event cannot validate profitability/probabilities | BLOCKED |
| Explicit owner GO | Real PM FIELD_PREFLIGHT_PASS plus new owner FIELD_CAPTURE_GO for exact event, permissions, window, retention and quota; not implied by Option A | BLOCKED |

## Frozen proposal limits (not an executable configuration)

- Proposed event ID: ZS03-FIELD-FEASIBILITY-ONE-EVENT-UNSCHEDULED. Actual ID/window/manifest NOT FROZEN.
- Data universe: public Binance Spot BTCUSDT and ETHUSDT only; closed-candle evidence plus any approved bid/ask and liquidity references; no private endpoints/accounts/trading.
- Environment: development GitHub Actions Ubuntu; run manually only under later authorization; final Windows production runtime remains a separate delivery acceptance.
- Maximum: duration 60 minutes; 12 physical REST GET attempts including failed/retried; 12 physical WS subscription requests including reconnect; hard stop on exhaustion, API warning/ban, rights ambiguity or unexpected fees.
- Time evidence: independently authenticated NTS selected identity and <1.5s uncertainty for each receive/decision; stamp margin needs real calibration; exchange-provided timestamp alone insufficient.
- Source records: primary documentation URLs, ToS/reuse/retention permission, named selected REST endpoints and weight, official WS quotas/counters, region restrictions, real logs only after new approval.
- Custody: one separately controlled owner acknowledgment and raw restore plan; event-specific original receipt after actual capture not superseded by synthetic demo.
- Retention and volume: propose one event only; PM+owner must set explicit files/bytes ceiling and legal retention and restore location before capturing ANY real market raw. 1 MiB cap in the synthetic tool does NOT authorize 1 MiB real capture.
- Stop logic: missing source/UTC, failed receipt, lost raw, quota counter unavailable, stale clock, unapproved extension or elevated cost means NO CONNECT / STOP.
- Scientific criteria: one short event is a feasibility exercise, not Stage03 closure, forward OOS, accuracy, or confidence calibration.

## Current conclusion and next authority

No new NTS query, Binance GET/WS, recurring task, scheduling, secret, execution token, merge, public repo, paid plan, Telegram, trading, Stage05. PM reviews synthetic handoff and source/rights/clock plan, owner separately receives and ACKs the external receipt; PM subsequently examines actual event-specific source/clock/legal/cost readiness; only then can owner consider explicit FIELD_CAPTURE_GO. **MARKET_NO_GO**.
