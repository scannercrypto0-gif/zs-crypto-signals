# 05C_FORENSIC_ROOT_CAUSE_MATRIX — 2026-11-10

**Authority:** Issue #56, SD Coding takeover; forensic repair **offline only**. Current 05C one-shot authorization is **CONSUMED**. No new Telegram/Binance traffic, no live retry, no merge, no full-qualification claim.

## Immutable observations (do not overwrite)

- Draft PR #55 failed live code commit: `52d43136b3bfe21fd5ad217777ebecee09d0ce97`; exact prior live receipt committed at evidence HEAD `c3946cdb5905ca617bdd5a00952be70f552e87ab`, file `research/stage51/closure/05c-human-assisted-receipt.json`, SHA256 `62183328956051cd56b53024a4fa461dca54481695d9bd8ec3aeeaef6d27ab0d`.
- Receipt 2026-11-10 09:09:57Z–09:11:45Z: 1 `getMe`, 1 `getWebhookInfo`, **8** `getUpdates` (including baseline), zero `sendMessage`, zero Binance, status `TWO_HUMAN_REQUESTS_NOT_OBSERVED`, exit 2; `READY` reported, owner reported A/B human sends.
- The original receipt contains **no update counts, no filter rejection categories, no verified Telegram incoming payloads/timestamps**. Hence the real root cause **cannot be determined from this record**. Sending by human and successful bot ingestion are different facts. Never infer which account missed or whether Telegram delivered updates.
- Previously accepted Windows focused 16/16 and Stage03 C1–C4, prior Stage04/05A/05B evidence remain intact and are not rerun.

## Cause tree: discriminator and safe action

| Hypothesis | New offline-safe distinguishing evidence in a future, separately authorized test | Classification |
|---|---|---|
| Telegram supplied zero updates during all polls | `EMPTY_BATCH` in each of seven post-READY poll histograms; baseline count shown separately | Not decidable from failed receipt; external delivery, bot activation/privacy/block or concurrent poller remain possibilities |
| Older queued updates repeated by `offset=0` | `BELOW_BASELINE` across polls; each batch count, total, baseline count | Non-acknowledging by design; do **not** force cursor forward or delete pending updates |
| 20 oldest unconfirmed updates obstruct newer ones | `INTERACTIVE_BACKLOG_FULL_NO_CURSOR_ADVANCE` and `batch_count=20`; no replies | Potential real liveness problem; **fail closed**, seek separately approved cursor ownership design, no skip/drop |
| Wrong A/B user/chat, not authorized by exact allowlist | `UNAUTHORIZED_ACCOUNT`, `CHAT_USER_MISMATCH`, `INVALID_IDS` | Reject by design. Never guess IDs, weaken allowlists or export IDs to GitHub |
| Not human/private | `BOT_SENDER`, `NON_PRIVATE_CHAT`, `MALFORMED_SENDER_CHAT`, `NO_MESSAGE` | Reject by design; do not treat bots/groups as owner |
| Text letter case / outer whitespace | `TEXT_MISMATCH` in old code even if text is `btcusdt` or ` BTCUSDT `; now normalized in `classify_inbound` | **Confirmed source-level defect** relative to existing `InteractiveService.parse_symbol` normalization; actual real-message text unknown |
| Telegram second timestamp before READY or future by host clock | `DATE_OUTSIDE_WINDOW` | Keep inclusive exact `started_at <= date <= observed_at`; clock boundary fixture and stale/future tests; no blanket tolerance |
| Invalid/missing Telegram message ID | `MISSING_MESSAGE_ID` | Reject by design; never fabricate reply-to ID |
| Same unacknowledged update repeated | `DUPLICATE_AUTHORIZED` plus A/B booleans; no second reply | Deduplicate in memory per role; do not ack and do not send twice |
| Another consumer owns updates, webhook, 429, timeout, Bot API issue | `getWebhookInfo` preflight and sanitized `INTERACTIVE_POLL_FAILED_OR_UNKNOWN` status; no way to prove absent competing consumers via one bot | Owner/PM operational dependency; no extra calls without authorization |

## Code change boundary

- Added *pure*, deterministic `stage05c_inbound_forensics.py`. One reason code per update, per-poll batch count and aggregated histogram; `seen={A: bool, B: bool}`. **No raw Telegram update contents, tokens, A/B chat/user IDs, unrelated text, private message IDs, URLs or PII in diagnostics**. Matched reply-to IDs remain only in the pre-existing owner-local `pending` and are not returned in diagnostic output.
- Narrow existing `bounded_interactive.py` integration: records reason counts for each **existing** post-READY poll, baseline batch count; no additional Bot API calls, no retries or new `getUpdates` endpoints, same `offset=0`, same <=12 total API attempts/<=2 replies, same ready and durable claim. Full 20-update pages stop fail-closed with `INTERACTIVE_BACKLOG_FULL_NO_CURSOR_ADVANCE`; no API acknowledgements, cursor advancement or update deletion.
- Plain-symbol `BTCUSDT` acceptance now uses `.strip().upper()` (also accepts `btcusdt`), **does not expand to `/analyze` commands**, still requires exact A/B private human user/chat identity, fresh inclusive Telegram integer date, positive message ID, valid update ID for live. Legacy `simulation=True` fixtures lacking `update_id` remain accepted **only in simulation**, preserving pre-approved fixture contract.
- No changes to Python runner, Windows launcher, telegram HTTP adapter, DPAPI handling, accepted closure evidence, production/scanner/market/SQL, MASTER or README. No claim that instrumentation cures external non-delivery.

## New focused offline test matrix

- Unit: distinct authorized A/B across polls, duplicate non-acknowledging read, correct reply binding only in memory; case/whitespace normalization, `/analyze` still rejected; same-second inclusive date, stale/future rejection; old/update ID baseline, malformed update; exact allowlist and cross-account mismatch, bot/group rejection; nontext and missing message ID; empty and full batch histograms; raw private payload excluded; simulation-only missing update ID.
- Integration: fake Bot API baseline + two later polls with A then B (two reply-to IDs, offsets `[0,0,0]`); 20 non-authorized updates triggers fail-closed without reply/offset advancement; separate empty and unauthorized batches generate distinct reasons with no sends. **No live API, no market or trading.**
- Accepted earlier 16/16 tests **not rerun**. Local non-Windows targeted test execution does not constitute a Windows acceptance receipt. PM may request one exact narrow Windows command later, without re-running 16/16 or consuming live authorization.

## Governance

`05C_FORENSIC_CODE_READY_FOR_PM_REVIEW` means only that targeted offline instrumentation and identified text normalization source defect were addressed, **not that the historical failed live case has an established exclusive root cause**. Real `05C_LIVE_NOT_VERIFIED`; one-shot permit consumed. **New separate owner authorization required** before any future human-assisted Telegram run (A then B, genuine `BTCUSDT`), and PM must review diagnostics and Windows receipts first.
