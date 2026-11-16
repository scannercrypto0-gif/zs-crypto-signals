from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from zs_smart_gate.mtf_contracts import CandleWindow, DURATIONS
from zs_smart_gate.stage05_contracts import ContractError, canonical, digest
from zs_smart_gate.stage11_market_context import evaluate_context, synthetic_ablation

SOURCE = "SYNTHETIC:S11"
CLOSE = datetime(2026, 11, 16, tzinfo=timezone.utc)
DECISION = CLOSE + timedelta(seconds=5)
AT = "2026-11-16T00:00:00Z"
INVENTORY = dict(source_id=SOURCE, symbols=["ETHUSDT", "SOLUSDT"],
                 observed_at=AT, received_at=AT, available_at=AT)


def bars(prices, frame="1h"):
    step = DURATIONS[frame]
    result = []
    for index, price in enumerate(prices):
        end = CLOSE - (len(prices)-1-index)*step
        result.append(CandleWindow(frame, end-step, end, end, end, SOURCE,
                                   price, price, price, price, "1", price))
    return tuple(result)


def evaluate(data=None, inventory=None, **extra):
    inventory = INVENTORY if inventory is None else inventory
    if data is None:
        data = {
            "BTCUSDT": {"1h": bars(("100","110","99","120"))},
            "ETHUSDT": {"1h": bars(("100","110","99","120"))},
            "SOLUSDT": {"1h": bars(("100","90","95","80"))},
        }
    args = dict(inventory=inventory, inventory_sha256=digest(canonical(inventory)),
                datasets=data, subject="ETHUSDT", direction="UP", horizon="Intraday",
                decision_at=DECISION, source_id=SOURCE)
    return evaluate_context(**(args | extra))


class Stage11Tests(unittest.TestCase):
    def test_btc_trend_volatility_and_breadth_denominator(self):
        frame = evaluate()["frames"]["1h"]
        self.assertEqual(frame["btc_regime"]["value"]["trend"], "UP")
        self.assertGreater(float(frame["btc_regime"]["value"]["mean_absolute_bar_return"]), 0)
        self.assertEqual(frame["breadth"]["counts"], {"UP":1,"DOWN":1,"NEUTRAL":0})
        self.assertEqual(frame["breadth"]["eligible_count"], 2)
        self.assertEqual(frame["breadth"]["value"], "0")
        self.assertEqual(frame["relative_strength"]["value"]["direction"], "NEUTRAL")
        self.assertEqual(float(frame["correlations"]["BTCUSDT"]["value"]), 1)

    def test_missing_asset_not_removed_from_denominator(self):
        frame = evaluate({"BTCUSDT":{"1h":bars(("1","2"))},
                          "ETHUSDT":{"1h":bars(("1","3"))}})["frames"]["1h"]
        self.assertEqual(frame["breadth"]["status"], "INSUFFICIENT_COVERAGE")
        self.assertEqual(frame["breadth"]["eligible_count"], 2)
        self.assertIsNone(frame["breadth"]["value"])
        self.assertEqual(frame["relative_strength"]["value"]["excess_return"], "1")
        self.assertEqual(frame["correlations"]["BTCUSDT"]["status"], "INSUFFICIENT_SAMPLE")

    def test_constant_sample_and_misalignment(self):
        frame = evaluate({"BTCUSDT":{"1h":bars(("1","1","1","1"))},
                          "ETHUSDT":{"1h":bars(("1","2","1","2"))},
                          "SOLUSDT":{"1h":bars(("1","2","1"))}})["frames"]["1h"]
        self.assertEqual(frame["btc_regime"]["value"]["trend"], "NEUTRAL")
        self.assertEqual(frame["correlations"]["BTCUSDT"]["status"], "CONSTANT_SAMPLE")
        self.assertEqual(frame["correlations"]["SOLUSDT"]["status"], "MISALIGNED")

    def test_gap_duplicate_future_and_foreign_source(self):
        values = bars(("1","2","3"))
        for changed, status in (
            ((values[0],values[2]), "INVALID_DATA"),
            ((values[0],values[0]), "INVALID_DATA"),
            ((*values[:2],replace(values[2], available_at=DECISION+timedelta(seconds=1))), "INVALID_DATA"),
            ((replace(values[0],source_id="FOREIGN"),), "UNVERIFIED_SOURCE"),
            (values[:-1], "STALE"),
        ):
            with self.subTest(status=status):
                frame = evaluate({"ETHUSDT":{"1h":changed}})["frames"]["1h"]
                self.assertEqual(frame["series_status"]["ETHUSDT"], status)

    def test_inventory_pin_and_pit(self):
        with self.assertRaises(ContractError):
            evaluate(inventory_sha256="0"*64)
        with self.assertRaises(ContractError):
            evaluate(inventory=dict(INVENTORY, available_at="2026-11-16T00:00:06Z"))

    def test_news_late_publication_unverified_and_missing(self):
        event = dict(event_id="news1", source_id=SOURCE, event_at=AT, published_at=AT,
                     received_at=AT, available_at=AT)
        self.assertEqual(evaluate(news=event)["news"]["status"], "PRESENT")
        self.assertEqual(evaluate(news=dict(event, published_at="2026-11-16T00:01:00Z"))["news"]["status"],
                         "INVALID_DATA")
        self.assertEqual(evaluate(news=dict(event, source_id="FOREIGN"))["news"]["status"], "UNVERIFIED_SOURCE")
        self.assertEqual(evaluate()["news"]["status"], "MISSING")

    def test_horizons_and_directions_preserve_baseline_and_no_trading(self):
        for direction in ("UP","DOWN"):
            for horizon, frames in (("Intraday", {"1h","4h"}),("Swing", {"4h","1d"})):
                context = evaluate(direction=direction,horizon=horizon)
                self.assertEqual(set(context["frames"]), frames)
                self.assertIsNone(context["spot_eligibility_effect"])
                self.assertIsNone(context["signal_id"])
                self.assertFalse(context["trading_authorized"])
                report = synthetic_ablation(context)
                self.assertEqual(report["spot_only"], direction)
                self.assertIsNone(report["predictive_accuracy"])
        with self.assertRaises(ContractError):
            synthetic_ablation(dict(evaluate(), direction="DOWN"))

    def test_missing_stale_or_foreign_btc_preserves_asset_and_ablation(self):
        values = bars(("1", "2", "1", "3"))
        for btc, status in ((None, "MISSING"), (values[:-1], "STALE"),
                            ((replace(values[0], source_id="FOREIGN"),), "UNVERIFIED_SOURCE")):
            with self.subTest(status=status):
                data = {"BTCUSDT": {"1h": btc}, "ETHUSDT": {"1h": values}}
                context = evaluate(data)
                frame = context["frames"]["1h"]
                self.assertEqual(frame["series_status"]["ETHUSDT"], "PRESENT")
                self.assertEqual(frame["btc_regime"]["status"], status)
                self.assertEqual(frame["relative_strength"]["status"], "INSUFFICIENT_COVERAGE")
                self.assertEqual(frame["breadth"]["status"], "INSUFFICIENT_COVERAGE")
                self.assertIsNone(synthetic_ablation(context)["spot_plus_context"]["btc_trend_agreement"]["1h"])
                self.assertEqual(context["frames"]["4h"]["btc_regime"]["status"], "MISSING")
                self.assertEqual(evaluate(data, horizon="Swing")["frames"]["1d"]["btc_regime"]["status"],
                                 "MISSING")

    def test_inventory_age_uses_observation_not_recent_availability(self):
        for horizon, duration in (("Intraday", timedelta(hours=1)),
                                  ("Swing", timedelta(hours=4))):
            for extra in (-1, 0, 1):
                with self.subTest(horizon=horizon, extra=extra):
                    observed = DECISION - duration - timedelta(microseconds=extra)
                    inventory = dict(INVENTORY, observed_at=observed.isoformat().replace("+00:00", "Z"))
                    if extra < 0:
                        self.assertEqual(evaluate(inventory=inventory, horizon=horizon)["horizon"], horizon)
                    else:
                        with self.assertRaisesRegex(ContractError, "STAGE11_INVENTORY_STALE"):
                            evaluate(inventory=inventory, horizon=horizon)
        with self.assertRaisesRegex(ContractError, "STAGE11_INVENTORY_INVALID"):
            evaluate(inventory=dict(INVENTORY, available_at="2026-11-16T00:00:05.000001Z"))

    def test_equal_length_shifted_series_are_not_aligned(self):
        btc = bars(("100", "110", "100", "115"))
        asset = bars(("100", "110", "100", "115"))
        shift = timedelta(hours=1)
        shifted = tuple(replace(b, **{key: getattr(b, key)-shift for key in
                        ("open_at", "close_at", "received_at", "available_at")}) for b in asset)
        # A shifted contiguous hourly series is stale when both have closed.
        frame = evaluate({"BTCUSDT": {"1h": btc}, "ETHUSDT": {"1h": shifted}},
)["frames"]["1h"]
        self.assertEqual(len(btc), len(shifted))
        self.assertEqual(frame["series_status"]["ETHUSDT"], "STALE")
        self.assertEqual(frame["relative_strength"]["status"], "INSUFFICIENT_COVERAGE")
        self.assertEqual(frame["breadth"]["status"], "INSUFFICIENT_COVERAGE")

    def test_btc_in_eligible_universe_and_malformed_member(self):
        inventory = dict(INVENTORY, symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        frame = evaluate(inventory=inventory)["frames"]["1h"]
        self.assertEqual(frame["breadth"]["eligible_count"], 3)
        self.assertEqual(frame["breadth"]["counts"]["UP"], 2)
        prices = bars(("1", "2", "1", "3"))
        frame = evaluate({"BTCUSDT": {"1h": prices}, "ETHUSDT": {"1h": prices},
                          "SOLUSDT": {"1h": ("not-a-candle",)}}, inventory=inventory)["frames"]["1h"]
        self.assertEqual(frame["series_status"]["SOLUSDT"], "INVALID_DATA")
        self.assertEqual(frame["breadth"]["eligible_count"], 3)
        self.assertEqual(frame["breadth"]["aligned_count"], 2)
        self.assertIsNone(frame["breadth"]["value"])
        self.assertEqual(frame["correlations"]["BTCUSDT"]["status"], "PRESENT")
        for symbols in (None, ["ETHUSDT", "ETHUSDT"], ["ETHUSDT", []]):
            with self.assertRaisesRegex(ContractError, "STAGE11_INVENTORY_INVALID"):
                evaluate(inventory=dict(INVENTORY, symbols=symbols))
