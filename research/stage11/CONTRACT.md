# Stage11 market context

Synthetic-only context contract `zs.stage11.market-context.v1`. This module has no transport and is not called by the Spot Scanner. It accepts an explicitly SHA-256-pinned, caller-supplied eligible inventory with observed, received and available UTC timestamps, per-symbol CandleWindow tuples, a source ID and a decision time. BTC may be supplied as a benchmark outside the eligible universe.

| Requirement | Definition and verification |
|---|---|
| BTC trend and volatility | Intraday uses 1h/4h and Swing uses 4h/1d. Each trend is the sign of first-to-last close return; zero is neutral. Volatility is the mean absolute close-to-close return, with at least two returns. |
| Breadth | Net advancing minus declining as a fraction of all pinned eligible symbols, with unchanged symbols in the denominator. Report observed counts but no net value if any eligible member lacks data aligned to BTC. |
| Relative strength and correlation | Relative strength is the asset return minus BTC return over identical close timestamps. Pearson uses at least three synchronized single-bar returns; constant samples and misalignment have explicit states. |
| PIT and coverage | Reuse CandleWindow source, closure and availability checks. Reject duplicates, gaps and future inputs. Latest closed bar and inventory must be younger than their applicable frame. Coverage refers to the contiguous supplied series; no claim of complete exchange acquisition. |
| Optional context | An injected synthetic news fixture must match the pinned synthetic source and satisfy event ≤ publication ≤ receipt ≤ availability ≤ decision. ETH/BTC and dominance are NOT_IMPLEMENTED. No event discovery. |
| Ablation | Report directional agreement for the same UP/DOWN baseline with BTC context; neutral or missing context has null agreement. No predictive accuracy, thresholds, veto or order authority. |

Hypothetical workload only: for three series and two frames at one request per series/frame, six GET-equivalents at an assumed two weight units and 150 ms each amount to 12 hypothetical weight units and 0.9 seconds serially. These are sizing assumptions, not current exchange weights or measured latency.

Windows test command: set PYTHONPATH=src and run `py -3.12 -m unittest discover -s tests -p test_stage11_market_context.py -v`.

## Inventory freshness boundary

Age is measured from observed_at, the snapshot time. received_at and available_at establish when the snapshot was known and must satisfy observed_at <= received_at <= available_at <= decision. Recent availability never refreshes an old snapshot. A snapshot is stale at or beyond the shortest selected frame. Two contiguous equal-length series shifted by a whole frame cannot both be fresh at the same decision. The earlier series is stale, so it cannot supply breadth, relative strength or correlation.
