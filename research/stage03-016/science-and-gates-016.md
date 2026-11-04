# 016 scientific instrument and acceptance boundaries

Protocol freeze77ea1940765d2f6874330f075b3f34dcb1d74caf precedes all new calibration
results; initial executable calibration/formulas froze at
be884b093cbef17387127ecba9c3c2182e084a37. Subsequent engineering completion adds
proof-content binding, future chain admission, explicit context reasons and
implements the already specified loss/partition/DEV-CDF functions. It changes
no primary family, alpha, calibration seed/grid, costs, threshold or outcome
after observing results. Final head and CI must be read from the execution packet.

The24 primary comparisons are12 groups times2 directions; Intraday uses30m
parent/30m outcome and Swing4h/4h. Baseline prediction=.5; R features are bounded
descriptive proxies, never approved V2 score contributions. Q is exploratory
DEV-only ECDF, cannot refit on OOS or select an uncorrected winner. Squared-loss
paired gain is implemented on a bounded directional future-return target.

| Group | Experimental R primitive | Data eligibility |
|---|---|---|
|I1|Directional30m close location|Closed parent|
|I2|Direction-favorable child quote-volume share|Six continuous5m children|
|I3|(signed child net/path+1)/2|Nonzero body path and ratio in[-1,1]; otherwise missing, no clipping|
|I4|Second-half quote-volume share|Positive parent quote volume; not old RVOL alias|
|I5|Completed daily+ISO-week directional context agreement|Both contexts required|
|I6|clip(1-spread_bps/20,0,1)|Decision-time bid/ask,24h quote volume, no gap/staleness|
|S1|Daily/week context proxy, not approved BOS/structure|Both completed contexts|
|S2|Directional4h close location|Closed4h parent|
|S3|Favorable child quote-volume share|Four reconciled1h children|
|S4|Daily/week directional agreement|Both completed contexts|
|S5|Second-half quote-volume share proxy|Positive quote volume|
|S6|Same explicit spread transform as I6|Same contemporaneous liquidity constraints|

All are hypotheses/proxies, not complete SMART GATE indicators or approved
weights. Historical I6/S6 remain missing; two Tardis samples cannot cover the
full past. Contemporary compatibility book/ticker values are observed only at
their receipts, cannot be inserted into2025. Bid/ask/spread normalization rejects
missing, crossed, stale, future or gapped inputs; it does not invent depth/fills.
Full RSI/MACD/EMA/50week MA/VolumeProfile qualification is not asserted by this
limited source/basic-metric integration. Score remains null and unpublished.

Known010–015 DEV/OOS and the016 compatibility batch are not new eligible OOS.
The partition interface rejects old/viewed/unadmitted hashes, requires post-
freeze receipts and independently admitted causality, then separates DEV/OOS
with4h purge+7day embargo. Real DEV/OOS are unavailable now. Outcome observations
must occur after their declared horizon; no future outcome was fabricated.

Calibration:200 replications per cell;16/64/256 market blocks; rho0/.4/.8;
effects0/.3;24 correlated arm means;16 synthetic events/asset/block with both
assets sharing the market block. Event replication never increases blockN.
Conditional simultaneous Hoeffding intervals require independent block means;
rho>0 intentionally violates that assumption and cannot be certified by its
sample rejection rate. Descriptive lag1/effectiveN estimates are labeled
nonqualified. Actual N_events_market=0, N_effective_qualified=null,
N_required_qualified=null. No theoretical planning count is an empirical gate.

The frozen simulation yielded conditional independent-cell typeI0/200; power
for effect.3 at256 blocks189/200 (.945). At rho.8, null rejection was.04 at64
and.025 at256, while the independence theorem is inapplicable. These are DGP-
conditional instrument diagnostics, not market power, stationarity or profits.
Wilson intervals are retained in the actual output, not replaced by certainty.

An actual engineering defect was found during replay: the body-only child path
omits inter-candle gaps, so the old ETH archive I3 values1.0006016847 and
-.0006016847 were outside the prefrozen unit domain. They are invalidated in a
separate Stage04 erratum; raw inputs/old outputs remain untouched. Version2
returns missing/UNKNOWN for such ratios and includes the decision implementation
version in event identity. It does not expand the domain, clip toward a favorable
value or change any hypothesis/alpha/seed/calibration. Corrected four decisions
and their superseded payload hashes are independently replayed. The synthetic
inference calibration never used these old market feature values.

Costs2/10/25/50bps are assumed sensitivity scenarios, not account fees or fills.
At+20bps gross and additional2bps spread, modeled UP net outcomes are16/8/-7/
-32bps for those assumptions. Costs and prediction loss are separate gates.
An instrument can be valid with NO_WINNER_WITH_VALID_EVIDENCE; an actual winner
requires positive simultaneous lower bound, independent OOS, clock/liquidity
and cost review. No such winner is claimed now.

Current gates: engineering PASS_CANDIDATE only after GitHub replay; prospective
UTC HOLD; historical publisher PIT HOLD; historical full-period liquidity
BLOCKED; inference conditional/HOLD for actual data; OOS_WAITING_FOR_FUTURE_
ELIGIBLE_DATA; FORWARD_NOT_ARMED.04 stays APPLICATION_ONLY. Product stages05–13
are not accepted by016; this is not completion of the14-stage project.
