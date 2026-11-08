"""Only new C1-C4 accounting/rejection behavior; no old suite is re-run."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from test_stage03_r2_offline import intraday, swing
from test_stage03_r2_functional import stage03_inputs
from test_stage03_r2_closed_bundle import sample
from test_stage03_r2_source_contract import swing_readiness
from test_stage03_r2_receipt_bundle import _record
from zs_smart_gate.stage03_r2_closure import (
    stage03_c1c4_research_from_closed_receipts as close,
)


class C1C4ClosureAccountingOnly(TestCase):
    def test_intraday_single_e2e_research_not_qualification_and_pending_semantics(self):
        kw = intraday()
        record = _record(sample(kw, stage03_inputs(kw)))
        with patch("socket.create_connection", side_effect=AssertionError("NO_NETWORK")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("NO_NETWORK")):
            row = close(record)
            replay = close(deepcopy(record))
        self.assertEqual(row, replay)
        self.assertEqual(row["status"], "RESEARCH_CANDIDATE")
        self.assertEqual([x["indicator"] for x in row["component_rows"]],
                         ["N01", "N02", "N03", "N04", "N05", "N06"])
        self.assertEqual(row["component_rows"][2]["status"], "UNAVAILABLE")
        self.assertIn("N03", row["unavailable_component_ids"])
        self.assertTrue(row["component_rows"][2]["reason_codes"])
        self.assertEqual(row["component_rows"][1]["status"],
                         "SEMANTIC_DECISION_REQUIRED")
        self.assertEqual(row["component_rows"][3]["status"],
                         "SEMANTIC_DECISION_REQUIRED")
        self.assertEqual([x["decision_id"] for x in row["semantic_decisions"]],
                         ["SEM-I-01", "SEM-I-02", "SEM-S-01", "SEM-S-02"])
        self.assertEqual(row["qualification_status"], "NOT_EVALUATED")
        self.assertIsNone(row["score"])
        self.assertIsNone(row["signal_id"])
        self.assertFalse(row["publishable"])
        self.assertEqual(row["market_requests"], 0)
        self.assertEqual(len(row["packet_sha256"]), 64)

    def test_swing_components_and_unavailable_reason_are_not_silently_zero(self):
        kw = swing()
        row = close(_record(sample(kw, swing_readiness(kw))))
        self.assertEqual(row["status"], "RESEARCH_CANDIDATE")
        by_id = {x["indicator"]: x for x in row["component_rows"]}
        self.assertEqual(set(by_id), {"N07", "N08", "N09", "N10", "N11", "N12"})
        self.assertEqual(by_id["N09"]["status"], "SEMANTIC_DECISION_REQUIRED")
        self.assertEqual(by_id["N10"]["status"], "UNAVAILABLE")
        self.assertIsNone(by_id["N10"]["value"])
        self.assertTrue(by_id["N10"]["reason_codes"])
        self.assertIn("N10", row["unavailable_component_ids"])
        self.assertIsNone(by_id["N10"]["production_contribution"])
        self.assertEqual(row["full_impulse_definition_status"], "UNAPPROVED")

    def test_missing_volume_future_receipt_and_crossfeed_return_explicit_rejection(self):
        kw = intraday()
        record = _record(sample(kw, stage03_inputs(kw)))
        edits = (
            (lambda x: x["ticker24"]["payload"].pop("quoteVolume"),
             "RECEIPT_TICKER24_EXPLICIT_VOLUME_STRINGS_REQUIRED"),
            (lambda x: x["parent"].__setitem__("available_at", "2099-01-01T00:00:00+00:00"),
             "BUNDLE_CANDLE_INVALID"),
            (lambda x: x["children"][0].__setitem__("source_id", "SYNTHETIC:FOREIGN"),
             "BUNDLE_CANDLE_SOURCE_MISMATCH"),
        )
        for change, expected in edits:
            damaged = deepcopy(record)
            change(damaged)
            row = close(damaged)
            with self.subTest(expected=expected):
                self.assertEqual(row["status"], "REJECTED")
                self.assertTrue(row["rejected_input"])
                self.assertIsNone(row["research"])
                self.assertIn(expected, row["rejection_reasons"][0])
                self.assertEqual(row["component_rows"], [])
                self.assertEqual(row["qualification_status"], "NOT_EVALUATED")
                self.assertIsNone(row["signal_id"])
                self.assertFalse(row["delivery_authorized"])
