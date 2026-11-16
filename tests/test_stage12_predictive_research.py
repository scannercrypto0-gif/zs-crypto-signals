from copy import deepcopy
from unittest import TestCase

from zs_smart_gate.stage05_contracts import ContractError, canonical, digest
from zs_smart_gate.stage12_predictive_research import evaluate_research, research_plan

SOURCE = "SYNTHETIC:S12"
REG = dict(registered_at="2026-01-01T00:00:00Z", hypothesis_id="H1", baseline_id="B1",
           quiet_definition="eligible without a trigger", success_definition="target reached",
           failure_definition="target not reached by maturity", multiplicity_policy="fixture only",
           costs=dict(fee_bps_per_side="5", slippage_bps_per_side="3"), fixture_threshold="0.5",
           partitions={name: dict(start=f"2026-0{i}-01T00:00:00Z", end=f"2026-0{i+1}-01T00:00:00Z")
                       for i,name in enumerate(("DEV","OOS","FORWARD"), 2)})


def row(event="A", label="SUCCESS", p="0.8", **overrides):
    decision = "2026-02-02T00:00:00Z"
    return dict(dict(event_id=event, label=label, source_id=SOURCE, horizon="Intraday", frame="30m",
                     horizon_length=1, version="V1", setup="CONTINUATION", direction="UP",
                     feature_at=decision, received_at=decision, available_at=decision, decision_at=decision,
                     label_end_at="2026-02-02T01:00:00Z", label_final_at="2026-02-02T01:01:00Z",
                     partition="DEV", asset="BTCUSDT", year=2026, regime="fixture", mae="0.01", mfe="0.02",
                     lead_seconds="10", persistence_seconds="20",
                     baseline_probability_fixture="0.5", model_probability_fixture=p), **overrides)


def evaluate(rows, reg=REG, **overrides):
    pin = digest(canonical(reg))
    dataset = dict(dataset_id="fixture", source_scope="SYNTHETIC_TEST_ONLY", source_id=SOURCE,
                   registration_sha256=pin, frozen_at="2026-05-01T00:00:00Z",
                   coverage="COMPLETE_SYNTHETIC_FIXTURE", rows=rows, row_count=len(rows),
                   scope={field:sorted({r[field] for r in rows}) for field in ("asset","year","regime")})
    return evaluate_research(dataset, **(dict(registration=reg, registration_sha256=pin,
                                             dataset_sha256=digest(canonical(dataset))) | overrides))


class Stage12Tests(TestCase):
    def test_real_and_missing_stay_blocked(self):
        for data in (None, {"source_scope":"VERIFIED_REAL","verified":True}):
            result = evaluate_research(data)
            self.assertEqual(result["status"], "BLOCKED_REAL_DATA_NOT_VERIFIED")
            self.assertEqual(result["scientific_metrics"], "NOT_EVALUATED")
            self.assertNotIn("fixture_metrics", result)

    def test_known_fixture_metrics_and_quiet_candidate(self):
        report = evaluate([row(), row("B","QUIET","0.2")])
        self.assertEqual(report["scientific_metrics"], "NOT_EVALUATED")
        group, = report["fixture_metrics"]
        self.assertEqual(group["count"], 2)
        self.assertEqual(group["model_fixture"]["brier"], "0.04")
        self.assertEqual(group["model_fixture"]["pr_auc_step"], "1")
        self.assertEqual(group["baseline"]["pr_auc_step"], "0.5")
        self.assertEqual(group["model_fixture"]["precision"], "1")
        self.assertEqual(group["model_fixture"]["recall"], "1")
        self.assertEqual(group["outcomes"]["lead_seconds"]["mean"], "10")
        self.assertEqual(len(group["model_fixture"]["precision_wilson_95_iid_fixture"]), 2)
        self.assertEqual(sum(x["count"] for x in group["model_fixture"]["calibration"]), 2)

    def test_all_negative_fixture_is_explicit(self):
        scores = evaluate([row(label="FAILURE", p="0.2")])["fixture_metrics"][0]["model_fixture"]
        for field in ("precision","recall","pr_auc_step"):
            self.assertIsNone(scores[field])

    def test_pins_and_duplicate_events(self):
        for key in ("registration_sha256","dataset_sha256"):
            with self.assertRaisesRegex(ContractError, "PIN_MISMATCH"):
                evaluate([row()], **{key:"0"*64})
        with self.assertRaisesRegex(ContractError, "DUPLICATE_EVENT"):
            evaluate([row(),row()])

    def test_paired_versions_and_event_origin_conflicts(self):
        report = evaluate([row(), row(version="V2")])
        self.assertEqual(len(report["fixture_metrics"]), 2)
        self.assertEqual(report["fixture_metrics"][0]["scope_counts"]["asset"],
                         [{"value":"BTCUSDT","count":1}])
        with self.assertRaisesRegex(ContractError, "EVENT_ORIGIN_CONFLICT"):
            evaluate([row(), row(version="V2", asset="ETHUSDT")])

    def test_pit_and_label_maturity(self):
        for fields in (dict(available_at="2026-02-03T00:00:00Z"),
                       dict(label_final_at="2026-02-02T00:59:59Z"),
                       dict(label_final_at="2026-03-01T00:00:00Z"),
                       dict(source_id="FOREIGN"), dict(partition="OOS")):
            with self.subTest(fields=fields), self.assertRaises(ContractError):
                evaluate([row(**fields)])

    def test_partition_overlap_and_invalid_cost(self):
        reg = deepcopy(REG)
        reg["partitions"]["OOS"]["start"] = "2026-02-28T23:59:59Z"
        with self.assertRaisesRegex(ContractError, "PARTITION_OVERLAP"):
            evaluate([row()], reg)
        for cost in ("NaN","Infinity","-0.01"):
            reg = deepcopy(REG)
            reg["costs"]["fee_bps_per_side"] = cost
            with self.assertRaisesRegex(ContractError, "DECIMAL_OUT_OF_RANGE"):
                evaluate([row()],reg)

    def test_swing_and_intraday_cohorts_never_pool(self):
        swing = row("B", horizon="Swing", frame="8h", version="V2", setup="REVERSAL", direction="DOWN",
                    label_end_at="2026-02-03T00:00:00Z", label_final_at="2026-02-03T00:01:00Z")
        self.assertEqual(len(evaluate([row(),swing])["fixture_metrics"]),2)
        with self.assertRaisesRegex(ContractError,"COHORT_INVALID"):
            evaluate([dict(swing, frame="15m")])

    def test_plan_is_hypothetical_and_preserves_candidate(self):
        at = "2026-02-02T00:00:00Z"
        evidence = dict(evidence_id="E1", source_id=SOURCE,event_at=at,available_at=at)
        proposal = dict(source_scope="SYNTHETIC_TEST_ONLY", structure=evidence, volatility=evidence,
                        execution_risk=evidence, costs=dict(evidence, fee_bps_per_side="5",
                                                            slippage_bps_per_side="3"),
                        entry_zone=["100","101"], stop="95", targets=["105","110","115"])
        for direction, levels in (("UP",proposal),("DOWN",dict(proposal,stop="105",targets=["95","90","85"]))):
            plan = research_plan("C1", direction, levels, source=SOURCE, decision_at=at)
            self.assertEqual(plan["status"],"SYNTHETIC_HYPOTHESIS_ONLY")
            self.assertIsNone(plan["signal_id"])
            self.assertFalse(plan["trading_authorized"])
        for change in (dict(volatility=None),dict(targets=["99","100","101"]),
                       dict(costs=dict(evidence, available_at="2026-02-02T00:00:01Z"))):
            result = research_plan("C1","UP",dict(proposal,**change),source=SOURCE,decision_at=at)
            self.assertEqual(result["candidate_id"],"C1")
            self.assertEqual(result["status"],"UNVERIFIED_PLAN")
            self.assertIsNone(result["levels"])
