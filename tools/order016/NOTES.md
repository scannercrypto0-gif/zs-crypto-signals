# Execution-only archive helpers

These exact one-time builders/processors preserve how016 evidence was assembled.
Their scratch layout is `work/`, `fixtures/`, `research-results/` and the named
packet folders below an explicit temporary execution root. They are not services,
retrieval fallbacks or approved capture launchers. They contain no owner drive
path or credential. Old superseded outputs remain in their pinned evidence
commits, with an explicit Stage04 erratum instead of silent replacement.

For independent reproduction use `scripts/restore-016-e2e.py` with the two
pinned GitHub evidence checkouts. It verifies original015 source lineage and016
claims/receipts, replays version2 decisions and the unchanged frozen calibration
with sockets disabled. It does not require these builders or the owner's disk.
