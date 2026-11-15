# Intraday UP clock calibration follow-up

The policy supports event-local authenticated UTC intervals. The acquisition recorder must bind both event brackets to one monotonic session and to the exact source/decision digest. The trusted witness pin covers the complete artifact. Each bracket encloses its marker between authenticated receipts, and the availability upper bound must be at or before the decision lower bound. A bound wider than the configured maximum or overlapping intervals gives UNKNOWN. This path uses fresh event-local evidence and does not extrapolate clock rate or reuse an old witness.

The Windows probe brackets a local test marker, not a Binance event. Provider identity and NTS authenticity were checked, and the marker interval remains conditional on the provider error metadata. The real trust registries remain empty. A real production-shaped evidence record needs paired calibrated timestamps captured with the actual source, a verified independent witness artifact, and an accepted exact qualification policy.

The alternate extrapolation path still requires a separately justified bound on oscillator drift and witness age. Comparing sampled offsets with a monotonic timer is diagnostic and cannot certify the maximum rate between or after samples. No clock settings change is warranted by successful sync and the measured conditional error.

Historical continuation results support keeping N01 diagnostic in the next policy. An explicit null cutoff removes N01 from the mandatory gate set, with a distinct policy fingerprint. Missing clock evidence remains UNKNOWN. The positive branch is tested only with synthetic policy and witnesses.
