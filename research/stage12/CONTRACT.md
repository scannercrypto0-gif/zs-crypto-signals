# Stage12 predictive research contract

`zs.stage12.predictive-research.v1` is a synthetic-only evaluator with no market, storage, trading or notification integration. Real or missing data returns `BLOCKED_REAL_DATA_NOT_VERIFIED` and scientific metrics remain `NOT_EVALUATED`. Declaring a dataset real or verified does not bypass the gate. A self-asserted synthetic coverage declaration is suitable for deterministic fixtures only.

| Requirement | Contract and evidence |
|---|---|
| Research cohorts | Partition, V1/V2, horizon, frame, duration, continuation/reversal and UP/DOWN form independent metric groups. Intraday is 1–24 hours (15m/30m); Swing is 1–30 days (1h/4h/8h). |
| Frozen provenance | Independent SHA-256 pins for registration and dataset. Registration precedes partitions. Enforce source identity, explicit UTC, feature receipt and availability, exact label maturity, finalization before the partition end, unique events per cohort and stable attribution across cohorts. |
| Outcome definitions and costs | Freeze success/failure/quiet and the baseline identity before evaluation. Quiet counts as negative under the fixture binary convention. Pin asset/year/regime scope and report counts per cohort. Fee and slippage fields are validated assumptions, not measured fills or simulated profit. |
| Metrics | Step-integrated PR area with grouped ties, Brier, fixture-threshold precision/recall, five equal-width calibration bins and descriptive lead/persistence/MAE/MFE. Wilson 95% intervals are illustrative IID fixture intervals; they do not estimate real uncertainty. Fixture probabilities are declared inputs and are distinct from a score. |
| Plan | Hypothetical entry zone, stop and three targets require ordered side-specific levels and PIT-valid synthetic references for structure, volatility, execution risk and costs. Missing evidence yields UNVERIFIED_PLAN while retaining the candidate ID. No route qualifies a plan or signal. |

## Pre-registration protocol for a later authorized study

1. Freeze hypotheses, cohorts, label definitions (including quiet and censoring), horizons, primary metric, multiplicity family, fees/slippage, source and coverage rules, and baseline before inspecting holdouts. Use a price/volume baseline as the initial comparator and freeze its exact implementation and parameters. The module accepts paired fixture predictions; it does not train this baseline or a model.
2. Plan contiguous chronological DEV, OOS and FORWARD windows with an embargo based on the longest label horizon. Set the actual embargo and fold schedule in the registration before data access. The engineering gate rejects overlapping windows and labels maturing or finalizing beyond their own partition. Tune only inside DEV via walk-forward folds, purge overlapping label windows, and freeze the selected specification before OOS. Keep forward truly prospective.
3. Report cohort and asset/year/regime coverage, excluded/censored rows, uncertainty with dependency-aware blocks, and sensitivity to realistic costs. Predefine the comparison family and use Holm correction for confirmatory multiplicity. The synthetic module does not run significance tests, fit probabilities or establish baseline superiority.
4. Authorize real evaluation only after independent historical and prospective provenance, scope, completeness and label adjudication pass. Real evidence, fold execution and predictive calibration are outside this delivery.

Run on Windows with PYTHONPATH=src and `py -3.12 -m unittest discover -s tests -p test_stage12_predictive_research.py -v`.
