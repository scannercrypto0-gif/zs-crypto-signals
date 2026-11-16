import copy
import subprocess
import sys
import unittest

from zs_smart_gate.stage05_contracts import ContractError
from zs_smart_gate.stage10_futures_context import evaluate_context, synthetic_ablation

SOURCE = "SYNTHETIC:STAGE10"
SYMBOL = "BTCUSDT"
START = "2026-11-16T09:00:00Z"
MID = "2026-11-16T09:00:20Z"
LATE = "2026-11-16T09:00:50Z"
END = "2026-11-16T09:01:00Z"


def row(identity, at=MID, **fields):
    return dict(id=identity, source_id=SOURCE, symbol=SYMBOL, event_at=at,
                received_at=at, available_at=at, **fields)


def feed(*rows):
    return dict(source_id=SOURCE, symbol=SYMBOL,
                coverage=dict(start=START, end=END, available_at=END, complete=True, row_count=len(rows)),
                pages=[dict(cursor=0, next_cursor=None, rows=list(rows))])


def trade(identity, maker=False, qty="2"):
    return row(identity, buyer_is_maker=maker, base_qty=qty, price="100")


def evaluate(**feeds):
    return evaluate_context(feeds, source_id=SOURCE, symbol=SYMBOL,
                            window_start=START, decision_at=END, max_age_seconds=45)


class FuturesContextTests(unittest.TestCase):
    def check(self, kind, payload, status):
        metric = evaluate(**{kind: payload})["metrics"][kind]
        self.assertEqual(metric["status"], status, metric)
        return metric["value"]

    def test_missing_unverified_and_stale_are_distinct(self):
        self.assertIsNone(self.check("oi", None, "MISSING"))
        self.check("oi", dict(feed(), source_id="OTHER"), "UNVERIFIED_SOURCE")
        self.check("oi", feed(row(1, START, contracts="10")), "STALE")
        self.assertIsNone(evaluate()["spot_eligibility_effect"])

    def test_oi_and_price_timestamp_join(self):
        oi = feed(row(1, contracts="12"), row(2, LATE, contracts="16"))
        price = feed(row(1, price="100"), row(2, LATE, price="99"))
        value = evaluate(oi=oi, price=price)
        self.assertEqual(value["metrics"]["oi"]["value"]["current"], "16")
        self.assertEqual(value["oi_price"]["value"],
                         dict(price_change="-1", oi_change="4", position_side_inference=None))
        price["pages"][0]["rows"][0]["event_at"] = START
        self.assertEqual(evaluate(oi=oi, price=price)["oi_price"]["status"], "INSUFFICIENT_COVERAGE")

    def test_funding_applied_time_and_signed_rate(self):
        valid = row(1, LATE, rate="-0.001", period_start=START, period_end=LATE)
        self.assertEqual(self.check("funding", feed(valid), "PRESENT")["latest"]["rate"], "-0.001")
        self.check("funding", feed(dict(valid, period_end=END)), "INVALID_DATA")

    def test_ratio_definition(self):
        self.check("ratio", feed(row(1, ratio="1.2", definition="TOP_ACCOUNT_RATIO")), "PRESENT")
        self.check("ratio", feed(row(1, ratio="1.2", definition="UNDECLARED")), "INVALID_DATA")

    def test_cvd_both_signs_and_empty_attested_interval(self):
        for maker, expected in ((False,"2"),(True,"-2")):
            self.assertEqual(self.check("aggtrades", feed(trade(10,maker)), "PRESENT")["base_cvd"], expected)
        self.assertEqual(self.check("aggtrades", feed(), "PRESENT")["base_cvd"], "0")
        self.check("aggtrades", feed(dict(trade(1), buyer_is_maker=1)), "INVALID_DATA")

    def test_pages_complete_duplicate_gap_and_interruption(self):
        payload = feed(trade(10), trade(11, True, "1"))
        payload["pages"] = [dict(cursor=0, next_cursor=1, rows=[trade(10)]),
                            dict(cursor=1, next_cursor=None, rows=[trade(11, True, "1")])]
        self.assertEqual(self.check("aggtrades", payload, "PRESENT")["base_cvd"], "1")
        self.check("aggtrades", feed(trade(10),trade(12)), "INSUFFICIENT_COVERAGE")
        self.check("aggtrades", feed(trade(10),trade(10)), "INVALID_DATA")
        interrupted = copy.deepcopy(payload)
        interrupted["pages"].pop()
        self.check("aggtrades", interrupted, "INSUFFICIENT_COVERAGE")
        payload["pages"][1]["cursor"] = 2
        self.check("aggtrades", payload, "INVALID_DATA")

    def test_pit_source_symbol_and_declared_count(self):
        for change in (dict(available_at="2026-11-16T09:01:01Z"),
                       dict(symbol="ETHUSDT"), dict(source_id="FOREIGN")):
            self.check("aggtrades", feed(dict(trade(10), **change)), "INVALID_DATA")
        payload = feed(trade(1))
        payload["coverage"]["row_count"] = 2
        self.check("aggtrades", payload, "INSUFFICIENT_COVERAGE")
        payload["coverage"].update(row_count=1, end=LATE)
        self.check("aggtrades", payload, "INSUFFICIENT_COVERAGE")

    def test_depth_zones_imbalance_and_crossing(self):
        snapshot = row(1, bids=[["99","3"],["98","6"]], asks=[["101","3"]])
        book = self.check("depth", feed(snapshot), "PRESENT")
        self.assertEqual(book["base_imbalance"], "0.5")
        self.assertEqual(book["bid_zones"][0]["price"], "98")
        self.check("depth", feed(dict(snapshot, asks=[["98","3"]])), "INVALID_DATA")

    def test_actual_liquidations_only(self):
        event = row("event-1", event_type="ACTUAL_LIQUIDATION", order_side="SELL", price="99", base_qty="2")
        self.assertEqual(self.check("liquidations", feed(event), "PRESENT")["count"], 1)
        self.check("liquidations", feed(dict(event, event_type="CANDLE_INFERENCE")), "INVALID_DATA")
        payload = feed()
        payload["coverage"]["complete"] = False
        self.check("liquidations", payload, "INSUFFICIENT_COVERAGE")

    def test_ablation_has_no_authority_and_is_hash_bound(self):
        context = evaluate(aggtrades=feed(trade(1, True)))
        self.assertEqual(context, evaluate(aggtrades=feed(trade(1, True))))
        self.assertFalse(context["trading_authorized"])
        self.assertIsNone(context["signal_id"])
        probe = synthetic_ablation("UP", context)
        self.assertFalse(probe["spot_plus_context"]["agreement"])
        self.assertIsNone(probe["predictive_accuracy"])
        context["symbol"] = "ETHUSDT"
        with self.assertRaisesRegex(ContractError, "ABLATION_CONTEXT_INVALID"):
            synthetic_ablation("UP", context)

    def test_price_and_cvd_comparison_requires_aligned_window(self):
        flow = feed(trade(1, True))
        price = feed(row(1, START, price="100"), row(2, END, price="101"))
        self.assertEqual(evaluate(aggtrades=flow, price=price)["price_cvd"]["value"]["relationship"],
                         "OPPOSITE_SIGNS")
        price["pages"][0]["rows"].pop(0)
        price["coverage"]["row_count"] = 1
        self.assertEqual(evaluate(aggtrades=flow, price=price)["price_cvd"]["status"],
                         "INSUFFICIENT_COVERAGE")

    def test_snapshot_coverage_and_exact_window(self):
        payload = feed(row(1, contracts="12"))
        payload["coverage"]["end"] = LATE
        metric = evaluate(oi=payload)["metrics"]["oi"]
        self.assertEqual(metric["status"], "PRESENT")
        self.assertEqual(metric["coverage"]["kind"], "AS_OF_SAMPLE")
        self.assertFalse(metric["coverage"]["coverage_to_decision"])
        for kind in ("aggtrades", "liquidations"):
            stream = feed()
            stream["coverage"]["end"] = LATE
            self.check(kind, stream, "INSUFFICIENT_COVERAGE")
            stream["coverage"]["end"] = END
            metric = evaluate(**{kind: stream})["metrics"][kind]
            self.assertEqual(metric["coverage"]["kind"], "COMPLETE_INTERVAL")
            self.assertTrue(metric["coverage"]["coverage_to_decision"])
            stream["coverage"]["start"] = "2026-11-16T08:59:59Z"
            self.check(kind, stream, "INSUFFICIENT_COVERAGE")
        payload["coverage"]["start"] = "2026-11-16T08:59:59Z"
        self.check("oi", payload, "INSUFFICIENT_COVERAGE")

    def test_malformed_shapes_and_timestamps_are_isolated(self):
        for payload in ([], dict(feed(), coverage=[]), dict(feed(), pages={}),
                        dict(feed(), pages=[None]), feed("row"),
                        feed(dict(trade(0), event_at="2026-11-31T09:00:20Z")),
                        feed(dict(trade(0), id=[]))):
            with self.subTest(payload=payload):
                context = evaluate(aggtrades=payload, oi=feed(row(1, contracts="12")))
                self.assertEqual(context["metrics"]["aggtrades"]["status"], "INVALID_DATA")
                self.assertEqual(context["metrics"]["oi"]["status"], "PRESENT")

    def test_invalid_decimals_and_zero_depth_fail_closed(self):
        for value in ("not-a-number", "Infinity", "NaN", "1E+9999999", float("inf")):
            with self.subTest(value=value):
                self.check("aggtrades", feed(trade(1, qty=value)), "INVALID_DATA")
        self.check("depth", feed(row(1, bids=[["99", "0"]], asks=[["101", "0"]])), "INVALID_DATA")

    def test_spot_import_does_not_initialize_futures_context(self):
        code = ("import sys; import zs_smart_gate.scanner;"
                "assert 'zs_smart_gate.stage10_futures_context' not in sys.modules")
        completed = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
