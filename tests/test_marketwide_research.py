"""ORDER006 deterministic fixtures are synthetic controls, never live signals."""
from contextlib import closing
import copy
from dataclasses import asdict
from datetime import timedelta
import json
from pathlib import Path
import runpy
import tempfile
import unittest

from zs_smart_gate.marketwide_cursor import PauseScan, ScanLedger
from zs_smart_gate.marketwide_research import (
    FRAMES, evaluate, inventory, packet_from_receipts, directional_return,
)
from zs_smart_gate.setup021_fixtures import scenario
from zs_smart_gate.stage05_contracts import canonical, digest


def packet(symbol="OTHERUSDT", direction="UP"):
    original = scenario("2026-09-01T00:10:00Z", symbol=symbol, breakout=direction != "FLAT")
    bars = original["klines"]
    if direction == "DOWN":
        for bar in bars:
            o, h, l, c = map(float, bar[1:5])
            bar[1:5] = [str(200-o), str(200-l), str(200-h), str(200-c)]
    boundary = bars[-1][6] + 1
    received = original["received_at"].isoformat().replace('+00:00', 'Z')
    rows = {}
    rows["5m"] = bars
    children = bars[-6:]
    rows["30m"] = [[boundary - 1800000, children[0][1], str(max(float(b[2]) for b in children)),
                   str(min(float(b[3]) for b in children)), children[-1][4],
                   "60", boundary-1, str(sum(float(b[7]) for b in children)), "0", "0", "0", "0"]]
    for frame in ("1h", "4h"):
        end = boundary // FRAMES[frame] * FRAMES[frame]
        rows[frame] = [[end-FRAMES[frame], "100", "120", "80", "100", "100",
                        end-1, "10000", "0", "0", "0", "0"]]
    market = asdict(original["market"])
    market["observed_at"] = market["observed_at"].isoformat().replace('+00:00', 'Z')
    for field in ("bid", "ask", "quote_volume_24h"):
        market[field] = str(market[field])
    return dict(symbol=symbol, boundary_ms=boundary, decision_at=original["decision_at"].isoformat().replace('+00:00', 'Z'),
                market=market, frames={k: dict(rows=v, received_at=received,
                payload_sha256=digest(canonical(v))) for k, v in rows.items()},
                source_scope="SYNTHETIC_TEST_ONLY", source_manifest_sha256="a"*64,
                clock_status="SYNTHETIC_TEST_CLOCK")


def snapshot(symbols):
    p = packet()
    at = p["decision_at"]
    ms = int(__import__("datetime").datetime.fromisoformat(at).timestamp()*1000)
    listing = [dict(symbol=s, baseAsset=s.removesuffix("USDT"), quoteAsset="USDT",
                    status="TRADING", isSpotTradingAllowed=True) for s in symbols]
    tickers = [dict(symbol=s, quoteVolume="50000000", closeTime=ms-1000) for s in symbols]
    books = [dict(symbol=s, bidPrice="100", askPrice="100.01") for s in symbols]
    receipts = [dict(path=k, params={}, payload=v, received_at=at)
                for k,v in zip(("exchangeInfo","ticker/24hr","ticker/bookTicker"),
                               (dict(symbols=listing), tickers, books))]
    return inventory(receipts, at, scope="SYNTHETIC"), receipts


def repin(p, frame):
    p["frames"][frame]["payload_sha256"] = digest(canonical(p["frames"][frame]["rows"]))


class MarketwideTests(unittest.TestCase):
    def test_symmetric_positives_and_directional_identity(self):
        for direction in ("UP", "DOWN"):
            with self.subTest(direction=direction):
                rows = evaluate(packet(direction=direction))
                matching = next(r for r in rows if r["direction"] == direction)
                self.assertEqual(matching["status"], "CANDIDATE_SHADOW_ONLY")
                self.assertTrue(matching["detector_trigger"])
                self.assertEqual({r["signal_id"] for r in rows}, {None})
                self.assertNotEqual(rows[0]["event_id"], rows[1]["event_id"])
                self.assertEqual(rows, evaluate(packet(direction=direction)))

    def test_mixed_bear_and_bull_other_symbols_are_not_btc_gated(self):
        for benchmark in ("UP", "DOWN"):
            specs = dict(BTCUSDT=benchmark, ETHUSDT=benchmark, OTHERUSDT="UP",
                         BEARUSDT="DOWN", FLATUSDT="FLAT")
            with tempfile.TemporaryDirectory() as root:
                ledger = ScanLedger(Path(root)/"scan.db")
                snap, _ = snapshot(specs)
                scan = ledger.register(snap, packet()["boundary_ms"])
                for _ in range(3):
                    report = ledger.chunk(scan, lambda item: packet(item["symbol"], specs[item["symbol"]]),
                                          max_pairs=2, healthy=lambda: True)
                self.assertEqual(report["coverage"], "MARKET_COVERAGE_VERIFIED")
                actual = {r["symbol"]: r["results"] for r in report["actual_evaluations"]}
                for symbol, direction in (("OTHERUSDT", "UP"), ("BEARUSDT", "DOWN")):
                    self.assertEqual(next(r for r in actual[symbol] if r["direction"] == direction)["status"],
                                     "CANDIDATE_SHADOW_ONLY")
                self.assertTrue(all(r["status"] == "NO_TRIGGER" for r in actual["FLATUSDT"]))
                self.assertEqual(report["production_signals"], 0)

    def test_all_quotes_explicit_and_no_silent_missing_drop(self):
        snap, receipts = snapshot(["GOODUSDT", "MISSINGUSDT", "ODDBTC"])
        receipts[0]["payload"]["symbols"][-1]["quoteAsset"] = "BTC"
        receipts[1]["payload"] = [r for r in receipts[1]["payload"] if r["symbol"] != "MISSINGUSDT"]
        snap = inventory(receipts, snap["decision_at"], scope="ALL_BINANCE_SPOT_INVENTORY")
        self.assertEqual(len(snap["rows"]), 3)
        by_symbol = {r["symbol"]: r for r in snap["rows"]}
        self.assertIn("UNSUPPORTED_QUOTE_POLICY", by_symbol["ODDBTC"]["reasons"])
        self.assertIn("MISSING_TICKER_OR_BOOK", by_symbol["MISSINGUSDT"]["reasons"])
        self.assertTrue(by_symbol["GOODUSDT"]["eligible"])

    def test_filtered_inventory_cannot_claim_complete_scope(self):
        snap, receipts = snapshot(["XUSDT"])
        receipts[0]["params"] = {"symbol": "XUSDT"}
        with self.assertRaises(ValueError):
            inventory(receipts, snap["decision_at"], scope="ALL_BINANCE_SPOT_INVENTORY")

    def test_duplicates_and_future_inventory_rejected(self):
        snap, receipts = snapshot(["XUSDT"])
        receipts[1]["payload"] *= 2
        with self.assertRaises(ValueError):
            inventory(receipts, snap["decision_at"], scope="SYNTHETIC")
        _, receipts = snapshot(["XUSDT"])
        receipts[-1]["received_at"] = "2030-01-01T00:00:00Z"
        with self.assertRaises(ValueError):
            inventory(receipts, snap["decision_at"], scope="SYNTHETIC")

    def test_invalid_join_and_timing_symmetric(self):
        for mutate in ("MISSING", "FUTURE", "GAP", "HASH", "PARENT", "SYMBOL", "STALE", "CONTEXT"):
            p = packet()
            if mutate == "MISSING":
                del p["frames"]["1h"]
            elif mutate == "FUTURE":
                p["frames"]["5m"]["received_at"] = "2030-01-01T00:00:00Z"
            elif mutate == "GAP":
                p["frames"]["5m"]["rows"][3][0] -= 300000
                repin(p, "5m")
            elif mutate == "HASH":
                p["frames"]["5m"]["rows"][3][4] = "99.1"
            elif mutate == "PARENT":
                p["frames"]["30m"]["rows"][0][7] = "123"
                repin(p, "30m")
            elif mutate == "SYMBOL":
                p["market"]["symbol"] = "WRONGUSDT"
            elif mutate == "STALE":
                p["decision_at"] = "2026-09-01T02:05:00Z"
            else:
                p["frames"]["4h"]["rows"][0][6] += 14400000
                repin(p, "4h")
            with self.subTest(mutate=mutate):
                self.assertTrue(all(r["status"] == "DATA_INVALID" for r in evaluate(p)))

    def test_equal_high_low_and_insufficient_volume_no_trigger(self):
        for direction in ("UP", "DOWN"):
            for mode in ("EQUAL", "VOLUME"):
                p = packet(direction=direction)
                last = p["frames"]["5m"]["rows"][-1]
                if mode == "EQUAL":
                    last[4] = "101" if direction == "UP" else "99"
                else:
                    last[7] = "100"
                children = p["frames"]["5m"]["rows"][-6:]
                parent = p["frames"]["30m"]["rows"][0]
                parent[4] = last[4]
                parent[7] = str(sum(float(b[7]) for b in children))
                repin(p, "5m")
                repin(p, "30m")
                self.assertTrue(all(r["status"] == "NO_TRIGGER" for r in evaluate(p)))

    def test_clock_unverified_prevents_candidate_admission(self):
        p = packet()
        p["clock_status"] = "TIME_STEP_OR_UNVERIFIED"
        self.assertTrue(all(r["status"] == "QUALIFICATION_BLOCKED" for r in evaluate(p)))

    def test_directional_outcome_sign_and_no_short_authority(self):
        self.assertGreater(directional_return(100, 90, "DOWN"), 0)
        self.assertLess(directional_return(100, 90, "UP"), 0)
        with self.assertRaises(ValueError):
            directional_return(100, 90, "SHORT_ORDER")

    def test_restart_quota_and_no_repeated_claim(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"scan.db"
            ledger = ScanLedger(path)
            snap, _ = snapshot(["AUSDT", "BUSDT", "CUSDT"])
            scan = ledger.register(snap, packet()["boundary_ms"])
            ledger.claim(scan)  # Simulated crash after durable reservation.
            report = ScanLedger(path).chunk(scan, lambda _: (_ for _ in ()).throw(PauseScan()),
                                           max_pairs=2, healthy=lambda: True)
            self.assertTrue(report["stopped_due_to_quota"])
            report = ScanLedger(path).chunk(scan, lambda item: packet(item["symbol"]),
                                           max_pairs=2, healthy=lambda: True)
            self.assertEqual(report["attempted"], 3)
            self.assertEqual(report["source_validated"], 1)
            self.assertEqual(report["interrupted_or_paused"], 2)
            self.assertEqual(report["zero_signal_reason"], "ZERO_SIGNALS_DUE_TO_INCOMPLETE_SCAN")

    def test_fair_rotation_across_new_boundaries_no_favorite(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = ScanLedger(Path(root)/"scan.db")
            snap, _ = snapshot(["AUSDT", "BUSDT", "CUSDT", "DUSDT", "EUSDT"])
            seen = []
            for offset in range(5):
                scan = ledger.register(snap, packet()["boundary_ms"] + offset*1800000)
                seen.append(ledger.claim(scan)["symbol"])
            self.assertEqual(len(set(seen)), 5)

    def test_no_claim_on_unhealthy_clock_or_source(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = ScanLedger(Path(root)/"scan.db")
            snap, _ = snapshot(["AUSDT"])
            scan = ledger.register(snap, packet()["boundary_ms"])
            result = ledger.chunk(scan, lambda _: self.fail("fetch executed"), max_pairs=1, healthy=lambda: False)
            self.assertEqual(result["attempted"], 0)
            self.assertEqual(result["coverage"], "MARKET_COVERAGE_PARTIAL")


    def test_duplicate_reservation_and_corrupted_snapshot_stop(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = ScanLedger(Path(root)/"scan.db")
            snap, _ = snapshot(["AUSDT"])
            corrupt = copy.deepcopy(snap)
            corrupt["rows"][0]["eligible"] = False
            with self.assertRaises(ValueError):
                ledger.register(corrupt, packet()["boundary_ms"])
            scan = ledger.register(snap, packet()["boundary_ms"])
            ledger.chunk(scan, lambda item: packet(item["symbol"]), max_pairs=1, healthy=lambda: True)
            with self.assertRaises(ValueError):
                ledger.finish(scan, "AUSDT", "EVALUATED", [])
            self.assertIsNone(ledger.claim(scan))

    def test_unsupported_and_inactive_and_invalid_bid_do_not_scan(self):
        snap, receipts = snapshot(["AUSDT", "BUSDT", "CUSDT"])
        receipts[0]["payload"]["symbols"][0]["status"] = "BREAK"
        receipts[1]["payload"][1]["quoteVolume"] = "NaN"
        receipts[2]["payload"][2]["askPrice"] = "0"
        snap = inventory(receipts, snap["decision_at"], scope="SYNTHETIC")
        self.assertFalse(any(r["eligible"] for r in snap["rows"]))

    def test_synthetic_clock_cannot_admit_public_packet(self):
        p = packet()
        p["source_scope"] = "PUBLIC_SPOT_CONDITIONAL_RESEARCH"
        self.assertTrue(all(r["status"] == "QUALIFICATION_BLOCKED" for r in evaluate(p)))

    def test_concurrent_claims_are_disjoint(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"scan.db"
            ledger = ScanLedger(path)
            snap, _ = snapshot(["AUSDT", "BUSDT", "CUSDT"])
            scan = ledger.register(snap, packet()["boundary_ms"])
            with ThreadPoolExecutor(max_workers=3) as pool:
                claims = list(pool.map(lambda _: ScanLedger(path).claim(scan)["symbol"], range(3)))
            self.assertEqual(len(set(claims)), 3)

    def test_source_request_swap_cannot_relabel_symbol(self):
        p = packet()
        receipts = []
        for frame, row in p["frames"].items():
            end = p["boundary_ms"] // FRAMES[frame] * FRAMES[frame]
            receipts.append(dict(path="klines", params=dict(symbol="WRONGUSDT", interval=frame,
                limit="22" if frame == "5m" else "1", endTime=str(end-1)), payload=row["rows"],
                received_at=row["received_at"]))
        with self.assertRaises(ValueError):
            packet_from_receipts(dict(symbol=p["symbol"], market=p["market"]), receipts,
                boundary_ms=p["boundary_ms"], decision_at=p["decision_at"],
                scope="SYNTHETIC_TEST_ONLY", clock_status="SYNTHETIC_TEST_CLOCK")

    def test_missing_raw_shape_rejected_without_fallback(self):
        p = packet()
        p["frames"]["5m"]["rows"][-1] = p["frames"]["5m"]["rows"][-1][:5]
        repin(p, "5m")
        self.assertTrue(all(r["status"] == "DATA_INVALID" for r in evaluate(p)))


    def test_full_flat_detector_coverage_is_separate_from_policy_block(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = ScanLedger(Path(root)/"scan.db")
            snap, _ = snapshot(["AUSDT", "BUSDT"])
            scan = ledger.register(snap, packet()["boundary_ms"])
            report = ledger.chunk(scan, lambda item: packet(item["symbol"], "FLAT"),
                                  max_pairs=2, healthy=lambda: True)
            self.assertEqual(report["detector_zero_reason"], "ZERO_SIGNALS_WITH_FULL_VALID_COVERAGE")
            self.assertEqual(report["zero_signal_reason"], "ZERO_SIGNALS_DUE_TO_POLICY_BLOCK")

    def test_reopened_corrupt_results_are_rejected(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"scan.db"
            ledger = ScanLedger(path)
            snap, _ = snapshot(["AUSDT"])
            scan = ledger.register(snap, packet()["boundary_ms"])
            ledger.chunk(scan, lambda item: packet(item["symbol"]), max_pairs=1, healthy=lambda: True)
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("UPDATE attempts SET result=?", (b"[]",))
            with self.assertRaises(ValueError):
                ScanLedger(path).report(scan)

    def test_previous_true_blocks_repeated_trigger_symmetrically(self):
        for direction in ("UP", "DOWN"):
            p = packet(direction=direction)
            bars = p["frames"]["5m"]["rows"]
            if direction == "UP":
                bars[-2][1:5], bars[-1][1:5] = ["100","113","99","112"], ["112","126","111","125"]
            else:
                bars[-2][1:5], bars[-1][1:5] = ["100","101","87","88"], ["88","89","74","75"]
            bars[-2][7], bars[-1][7] = "1300", "2000"
            children = bars[-6:]
            parent = p["frames"]["30m"]["rows"][0]
            parent[2] = str(max(float(b[2]) for b in children))
            parent[3] = str(min(float(b[3]) for b in children))
            parent[4] = children[-1][4]
            parent[7] = str(sum(float(b[7]) for b in children))
            repin(p, "5m")
            repin(p, "30m")
            result = next(r for r in evaluate(p) if r["direction"] == direction)
            self.assertEqual(result["status"], "NO_TRIGGER")
            self.assertEqual(result["reason"], "NO_FALSE_TO_TRUE_TRANSITION")

    def test_zero_volume_history_invalid_and_late_frame_invalid(self):
        for mode in ("ZERO_VOLUME", "LATE"):
            p = packet(direction="DOWN")
            if mode == "ZERO_VOLUME":
                for row in p["frames"]["5m"]["rows"]:
                    row[7] = "0"
                p["frames"]["30m"]["rows"][0][7] = "0"
                repin(p, "5m")
                repin(p, "30m")
            else:
                p["frames"]["1h"]["received_at"] = "2026-09-01T02:00:10Z"
            self.assertTrue(all(r["status"] == "DATA_INVALID" for r in evaluate(p)))


    def test_new_snapshot_cannot_rescan_same_pair_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = ScanLedger(Path(root)/"scan.db")
            snap, _ = snapshot(["AUSDT"])
            boundary = packet()["boundary_ms"]
            first = ledger.register(snap, boundary)
            ledger.claim(first)
            changed = copy.deepcopy(snap)
            changed["decision_at"] = "2026-09-01T02:00:03Z"
            changed["snapshot_sha256"] = digest(canonical(
                {k: v for k, v in changed.items() if k != "snapshot_sha256"}))
            second = ledger.register(changed, boundary)
            self.assertIsNone(ledger.claim(second))
            report = ledger.report(second)
            self.assertEqual(report["unscanned_symbols"][0]["reason"], "DUPLICATE_PAIR_BOUNDARY_RESERVED")
            self.assertEqual(report["coverage"], "MARKET_COVERAGE_PARTIAL")

    def test_permission_set_omission_preserves_unfiltered_inventory(self):
        snap, receipts = snapshot(["AUSDT", "BUSDT"])
        receipts[0]["params"] = {"showPermissionSets": "false"}
        result = inventory(receipts, snap["decision_at"], scope="ALL_BINANCE_SPOT_INVENTORY")
        self.assertEqual(len(result["rows"]), 2)
