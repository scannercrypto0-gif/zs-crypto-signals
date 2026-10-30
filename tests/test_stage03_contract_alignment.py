"""Postmerge 03A/03C semantic compatibility and fail-closed score boundary."""
from __future__ import annotations

import unittest
from datetime import timedelta, timezone
from unittest.mock import patch
from decimal import Decimal

from test_stage03_qualification_readiness import setup
from zs_smart_gate.stage03_contract_alignment import (
    group_alignment, unavailable_contract_packet,
)
from zs_smart_gate.stage03_qualification_readiness import assess_readiness
from zs_smart_gate.stage03a_contracts import (
    Direction, Horizon, V2_GROUPS, unavailable_score,
)
from zs_smart_gate.stage03c_score_contracts import (
    VERSION as VERSION_03C, WEIGHTS, score_v2, detection_event_key,
)


class ContractAlignmentTests(unittest.TestCase):
    def test_twelve_concepts_have_weight_parity_and_no_silent_ambiguity(self):
        unresolved = {
            "INTRADAY": {"SIX_5M_INTERNAL_QUALITY", "VOLUME_CONTINUITY"},
            "SWING": {"FOUR_1H_INTERNAL_QUALITY", "DAILY_WEEKLY_CONTEXT"},
        }
        for horizon in Horizon:
            rows = group_alignment(horizon)
            self.assertEqual(len(rows), 6)
            self.assertEqual(sum(x["weight"] for x in rows), 100)
            self.assertEqual({x["stage03a_group"] for x in rows},
                             {name for name, _ in V2_GROUPS[horizon]})
            self.assertEqual({x["stage03c_concept"] for x in rows},
                             set(WEIGHTS[horizon.value]))
            self.assertEqual(
                {x["stage03a_group"] for x in rows
                 if x["status"] == "UNMAPPED_OWNER_DECISION_REQUIRED"},
                unresolved[horizon.value],
            )
            for row in rows:
                with self.subTest(horizon=horizon, group=row["stage03a_group"]):
                    self.assertEqual(row["weight"],
                                     WEIGHTS[horizon.value][row["stage03c_concept"]])
                    if row["status"] == "UNMAPPED_OWNER_DECISION_REQUIRED":
                        self.assertIsNone(row["mapped_03c_group"])
                    else:
                        self.assertEqual(row["mapped_03c_group"], row["stage03c_concept"])
                    self.assertEqual(row["normalization_status"], "NOT_APPROVED")

    def test_fail_closed_if_weight_or_name_drifted(self):
        # We do not modify either accepted contract: a test-only stand-in.
        fake = {k: dict(v) for k,v in WEIGHTS.items()}
        fake["INTRADAY"]["volume"] = 21
        with patch("zs_smart_gate.stage03_contract_alignment.WEIGHTS", fake):
            with self.assertRaisesRegex(ValueError, "WEIGHT_CONTRACT_DRIFT"):
                group_alignment(Horizon.INTRADAY)
        fake = {k: dict(v) for k,v in WEIGHTS.items()}
        fake["INTRADAY"]["unexpected"] = fake["INTRADAY"].pop("volume")
        with patch("zs_smart_gate.stage03_contract_alignment.WEIGHTS", fake):
            with self.assertRaisesRegex(ValueError, "03C_GROUP_CONTRACT_DRIFT"):
                group_alignment(Horizon.INTRADAY)

    def test_both_existing_unavailable_contracts_share_status_not_version(self):
        for horizon in Horizon:
            for direction in Direction:
                with self.subTest(horizon=horizon.value,direction=direction.value):
                    packet = unavailable_contract_packet(horizon, direction)
                    prior = unavailable_score(horizon, direction)
                    self.assertEqual(packet["status"], prior.status)
                    self.assertEqual(packet["stage03a_version"], prior.score_version)
                    self.assertEqual(packet["stage03c_version"], VERSION_03C)
                    self.assertNotEqual(packet["stage03a_version"], packet["stage03c_version"])
                    self.assertEqual(packet["score"], None)
                    self.assertEqual(packet["qualification_status"], "NOT_EVALUATED")
                    self.assertTrue(packet["missing_reasons"])
                    self.assertTrue(all(x["normalization_status"] == "NOT_APPROVED"
                                        for x in packet["alignment"]))
                    self.assertFalse(packet["publishable"])

    def test_03c_called_with_empty_mapping_not_descriptive_or_supplied_groups(self):
        for horizon in Horizon:
            for direction in Direction:
                kw=setup(horizon,direction)
                complete={key:Decimal("0.8") for key in WEIGHTS[horizon.value]}
                # Complete 03C numbers are not licensed for this raw path.
                for offered in (None, {}, complete):
                    with self.subTest(horizon=horizon,direction=direction,
                                      has_groups=offered is not None):
                        with patch("zs_smart_gate.stage03_contract_alignment.score_v2",
                                   wraps=score_v2) as scorer:
                            row=assess_readiness(**{**kw,"normalized_groups":offered})
                        scorer.assert_called_once_with(horizon.value, {})
                        self.assertIsNone(row["score"])
                        self.assertEqual(row["score_status"],"SCORE_UNAVAILABLE")
                        self.assertEqual(row["stage03c_dependency"],"MERGED_BUT_NOT_QUALIFIED")
                        self.assertFalse(row["publishable"])
                        self.assertIsNone(row["signal_id"])
                        self.assertFalse(row["delivery_authorized"])
                        if offered is not None:
                            self.assertEqual(row["status"],"INVALID")
                            self.assertIn("NORMALIZATION_INPUT_NOT_APPROVED", row["reason_codes"])

    def test_03c_numeric_reference_still_not_authorized_for_raw_path(self):
        # 03C independently supports a research number for pre-normalized values;
        # that is not a license to pass Stage03B1's raw measured features.
        for horizon in Horizon:
            standalone=score_v2(horizon.value,{key:Decimal("0.5")
                                            for key in WEIGHTS[horizon.value]})
            self.assertEqual(standalone.status,"SCORED_RESEARCH_ONLY")
            for direction in Direction:
                row=assess_readiness(**setup(horizon,direction))
                self.assertEqual(row["status"],"RESEARCH_CANDIDATE")
                self.assertEqual(row["score_status"],"SCORE_UNAVAILABLE")
                self.assertIsNone(row["score"])
                self.assertTrue(row["research_metrics"][direction.value])
                self.assertFalse(row["publishable"])

    def test_03a_and_03c_identity_serializations_are_not_interchangeable(self):
        for horizon in Horizon:
            for direction in Direction:
                kw=setup(horizon,direction)
                row=assess_readiness(**kw)
                close=row["identity"]["decision_candle_close_at"]
                # The distinct 03C research key must NOT replace the 03A key.
                other=detection_event_key(
                    rule_version=row["identity"]["rule_version"],
                    market="BINANCE:SPOT", symbol=kw["symbol"],
                    direction=direction.value, horizon=horizon.value,
                    setup_type=row["identity"]["setup_type"],
                    decision_close_utc=close,
                    discriminator=kw["event_discriminator"],
                )
                self.assertNotEqual(other,row["identity"]["detection_event_key"])
                self.assertTrue(row["identity"]["detection_event_key"].startswith("RESEARCH-KEY-"))
                self.assertIsNone(row["identity"]["signal_id"])

    def test_utc_and_no_http_in_postmerge_integration(self):
        for horizon in Horizon:
            for direction in Direction:
                kw=setup(horizon,direction)
                shift=timezone(timedelta(hours=3))
                changed={**kw,"decision_at":kw["decision_at"].astimezone(shift)}
                with patch("urllib.request.urlopen",
                           side_effect=AssertionError("OUTBOUND_FORBIDDEN")), \
                     patch("socket.create_connection",
                           side_effect=AssertionError("OUTBOUND_FORBIDDEN")):
                    left=assess_readiness(**kw)
                    right=assess_readiness(**changed)
                self.assertEqual(left["identity"],right["identity"])
                self.assertEqual(left["score_contracts"],right["score_contracts"])
                self.assertEqual(left["score_status"],"SCORE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
