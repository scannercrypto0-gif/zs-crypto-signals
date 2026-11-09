# Order 51 — bounded 00–05 integration evidence

Authority: [Owner and PM order](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6742052408).
Windows execution pin `c3f6b8faacab6703435f703e6e597b55932cd928`, tree `faff5ab4ef00fe81aa40414fc7ccd3fa2a82d8db`.

| Boundary | Implementation and checked contract | Result |
| --- | --- | --- |
| 00 → 01 | `e2e51.capture/analyze → scanner.build_universe/inspect_candles`. Exact public endpoint and symbol, source candle timestamps, duplicate/gap/partial/future rejection, rolling quote volume, separate book receipt. | Real BTCUSDT, six REST GET attempts, zero WS, no retry. |
| 01 → 02 | Same closed raw 5m sequence to the scanner and frozen `setup021.evaluate`. | Scanner PASS. Setup research candidate, NO_BREAKOUT. |
| 02 → 03 | `e2e51.analyze` reuses R2 `close_parts/path_parts/volume_continuity` for N01/N02/N04. Latest completed 30m aggregate from six contiguous 5m bars, with preceding 20-bar baseline. Setup decision candle and component parent have separately recorded timestamps. | N01/N02/N04 research values. N03/N05/N06 and N07–N12 unavailable with reasons. Full typed R2 live admission, independent UTC PIT, scores, and qualified signals remain HOLD. |
| 03 → 04 | `e2e51.persist → LocalChainJournal`. Canonical source receipts, rejected candidate, SQL projection, archive hash and journal readback. | Actual SQLite commit/readback. Offline backup/restore and duplicate replay passed. This is application custody. |
| 04 → 05A | `e2e51-windows.deliver` deliberately uses a labeled synthetic route test A+B. | Offline test verified. No genuine signal existed in captured sample. |
| 04 → 05B | Verified Stage04 event to `make_document` for rejected candidate summary and SHA-bound JSON to C=A. | Actual JSON built from market decision. Offline route and Desktop wrapper extraction verified. |
| 04 → 05C | Fresh case-bound private symbol queries from A/B to independent 05C. `InteractiveService` reads the same decision snapshot with source time and unavailable values. | Offline two-account routing verified. |
| 05 SQL | Accepted SQL Server DDL with a rollback-only fixture in tempdb. Candidate and attempt FK, duplicate route constraint, unknown delivery, microsecond readback. | SQL Server Express 16.0.1210.3 probe passed. Full live SQL import and Stage06B remain outside the verified result. |

## Windows evidence

Windows owner host, Python 3.12.10 standard library, PowerShell 7.6.9. Offline exact-SHA preflight started 2026-11-09 14:24:09.470986 UTC and ended 14:24:11.240967 UTC. Five tests, zero failures, errors or skips, exit 0. `py -3.12 -B scripts/e2e51-windows.py preflight --head <execution-pin>`. The runner performs the focused unittest suite. `git diff --cached --check` passed. No accepted smoke or unrelated suite was rerun. No CI was triggered manually.

Market entry used `py -3.12 -B scripts/e2e51-windows.py market --head <execution-pin>` once, exit 0. Decision 2026-11-09 14:25:16.879 UTC, newest closed 5m at 14:25:00 UTC. The 505 ms half-width is a same-provider comparison, with no independent timing claim or historical publication claim. The source adapter used the [official public market-only host and endpoints](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md).

Offline replay of the captured market JSON regenerated the identical decision SHA256 `db48497c3fd4cb98bd379e42f2964466fffcf57583ad2f016ff3fc0b7d94e857`. Stage04 serialized readback SHA256 `bdc49250bb305ae0131b6c768ae43a8f11818bdcebbaa038dc6be6fcfd731311`. Analytics attachment SHA256 `0bda1f242636f043917f8ce68bde4cfbb4b93e5a010775781e4c2d8eb3c945e4`.

On the execution pin, `status` is read-only. `stop` sets a persistent local stop marker checked before every new request, and one-shot claim files prevent any repeat after interrupted or ambiguous requests. The launcher never schedules itself. Keep the owner console and all credentials private. The separate `telegram` command requires exact SHA, clean checkout, a still-current matched market readback, an interactive Windows terminal and a typed owner confirmation. It allows 11 Bot API calls and six outputs in one execution. It records each intent before the send. Telegram acceptance and owner visual verification are separate. The market probe is already consumed. Never clear a claim to retry it.

## Baseline and governance

- Main `f064493e77bd4f70029fb8af1837ac9685d07c41`. [PR #50](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/50) merged, head `0be30e119ff4ac8dc88d287895cb242f7fa97ed0`, base `3d210cf9aac8a789b3a3208a6b37a2d0ffad810b`.
- [PR #53](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/53) draft and unmerged at `4c421204db345d47dc75c8fd25c2fbf512a5531d`, base main above. Order branch descends directly from that pinned head. Original files retained.
- [PR #52](https://github.com/scannercrypto0-gif/zs-crypto-signals/pull/52) draft and unmerged at `df8a2bc25f15bd54b91c15558788a026a20b2119`, base main above. PM documentation review stays separate. Proposed docs correction: replace stale two-bot / group-archive language with three independent identities and two private accounts, C=A, and preserve production HOLD. MASTER and README were left untouched.
- [Prior owner-accepted smoke](https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-6741868646) is separate. Its 12 calls and seven outputs are not evidence of this execution.
