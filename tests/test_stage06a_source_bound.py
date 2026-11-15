"""Stage06A *new adapter* tests only. Offline fixtures; no 00–05 test suites run."""
from copy import deepcopy
from datetime import timedelta
from unittest import TestCase
from decimal import Decimal as D

from test_stage03_research_handoff import synthetic_handoff
from test_stage03_r1_closed_parent import CLOSE, DECISION
from zs_smart_gate.stage05_contracts import ContractError, canonical, digest
from zs_smart_gate.stage06a_source_bound import (
    BAR_SCHEMA, RESEARCH_RECEIPT, evaluate_source_bound,
)


def signed(row):
    row["payload_sha256"] = digest(canonical(row))
    return row


def bars(symbol="BTCUSDT", sha="a"*64, *, gap=False, target=False):
    start = DECISION + timedelta(minutes=5)
    def stamp(t):
        return t.isoformat(timespec="seconds").replace("+00:00", "Z")
    items = []
    for i in range(2):
        a = start + timedelta(minutes=5*(i + (1 if gap and i else 0)))
        b = a + timedelta(minutes=5)
        items.append({"open_at": stamp(a), "close_at": stamp(b),
                      "available_at": stamp(b+timedelta(seconds=1)),
                      "open": "100", "high": "111" if target and i else "102",
                      "low": "99", "close": "101", "closed": True})
    raw = canonical({"schema": BAR_SCHEMA, "venue": "BINANCE_SPOT",
                    "symbol": symbol, "source_manifest_sha256": sha,
                    "timeframe": "5m", "candles": items})
    return raw, digest(raw)


def receipt(handoff):
    at = DECISION.isoformat(timespec="seconds").replace("+00:00", "Z")
    return signed({"schema": RESEARCH_RECEIPT,
                   "candidate_id": handoff["candidate_id"],
                   "event_id": handoff["event_id"],
                   "source_manifest_sha256": handoff["source_manifest_sha256"],
                   "available_at": at})


class Stage06ABoundTests(TestCase):
    def setUp(self):
        self.handoff = synthetic_handoff()
        self.raw, self.hash = bars(sha=self.handoff["source_manifest_sha256"], target=True)
        self.now = (DECISION+timedelta(hours=1)).isoformat(timespec="seconds").replace("+00:00", "Z")
        self.kw = dict(record=self.handoff, record_kind="R0_RESEARCH_HANDOFF",
                       research_identity={"symbol": "BTCUSDT", "discriminator": "GENERAL_30M"},
                       receipt=receipt(self.handoff), bars_raw=self.raw,
                       bars_sha256=self.hash, as_of=self.now)

    def test_research_scenario_target_is_touch_not_fill(self):
        scenario = dict(direction="LONG", entry="100", stop="95",
                        target="110", scenario_only=True)
        x = evaluate_source_bound(**self.kw, research_plan=scenario)
        self.assertEqual(x["status"], "TARGET_TOUCHED")
        self.assertIsNone(x["signal_id"])
        self.assertFalse(x["is_executed_trade"])
        self.assertFalse(x["is_production_signal"])
        self.assertEqual(x["result_sha256"], digest(canonical({k:v for k,v in x.items() if k!="result_sha256"})))
        self.assertEqual(x, evaluate_source_bound(**self.kw, research_plan=scenario))

    def test_policy_hold_without_explicit_scenario_does_not_invent_levels(self):
        r = evaluate_source_bound(**self.kw)
        self.assertEqual(r["status"], "NO_APPROVED_OR_EXPLICIT_PLAN")
        self.assertIsNone(r["signal_id"])

    def test_wrong_symbol_foreign_candles_rejected(self):
        raw, sha = bars("ETHUSDT", self.handoff["source_manifest_sha256"])
        with self.assertRaises(ContractError):
            evaluate_source_bound(**dict(self.kw, bars_raw=raw, bars_sha256=sha))

    def test_wrong_source_manifest_rejected(self):
        raw, sha = bars("BTCUSDT", "b"*64)
        with self.assertRaises(ContractError):
            evaluate_source_bound(**dict(self.kw, bars_raw=raw, bars_sha256=sha))

    def test_capture_tamper_sha_mismatch(self):
        with self.assertRaises(ContractError):
            evaluate_source_bound(**dict(self.kw, bars_raw=self.raw+b" ", bars_sha256=self.hash))

    def test_handoff_identity_pinned_to_r0(self):
        with self.assertRaises(ContractError):
            evaluate_source_bound(**dict(self.kw, research_identity={"symbol":"ETHUSDT","discriminator":"GENERAL_30M"}))

    def test_corrupted_handoff_fails_original_sha(self):
        h = deepcopy(self.handoff)
        h["raw_features"]["body_to_range"]["raw_value"]="9999"
        with self.assertRaises(ContractError):
            evaluate_source_bound(**dict(self.kw, record=h))

    def test_research_availability_receipt_tamper(self):
        receipt_row = receipt(self.handoff)
        receipt_row["available_at"] = "2026-11-10T00:00:00Z"
        with self.assertRaises(ContractError):
            evaluate_source_bound(**dict(self.kw, receipt=receipt_row))

    def test_gap_closed_bar_rejected(self):
        raw, sha = bars(sha=self.handoff["source_manifest_sha256"], gap=True)
        with self.assertRaises(ContractError):
            evaluate_source_bound(**dict(self.kw, bars_raw=raw, bars_sha256=sha))

    def test_future_bar_fails_closed(self):
        with self.assertRaises(ContractError):
            evaluate_source_bound(**dict(self.kw, as_of=DECISION.isoformat(timespec="seconds").replace("+00:00","Z")))

    def test_non_scenario_authority_forbidden(self):
        with self.assertRaises(ContractError):
            evaluate_source_bound(**self.kw, research_plan={"direction":"LONG","entry":"100","stop":"95","target":"110","scenario_only":False})

    def test_unverified_qualified_event_never_inferred(self):
        with self.assertRaises(ContractError):
            evaluate_source_bound(**dict(self.kw, record_kind="STAGE05_EVENT"))
