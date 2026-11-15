import copy
import importlib.util
from pathlib import Path
import tempfile
import time
import unittest

from zs_smart_gate.e2e51 import FIVE_MS, PATHS, Stop, analyze, capture, persist
from zs_smart_gate.pre05_offline_chain import LocalChainJournal
from zs_smart_gate.stage05_contracts import extract_desktop_export, make_document
from zs_smart_gate.stage05_telegram_http import BotSecrets

spec = importlib.util.spec_from_file_location(
    "e2e51_launcher", Path(__file__).resolve().parents[1] / "scripts/e2e51-windows.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def fixture():
    boundary = int(time.time() * 1000) // FIVE_MS * FIVE_MS - FIVE_MS
    now = boundary + 10000
    raw = []
    for i in range(34):
        opened = boundary - (34-i)*FIVE_MS
        raw.append([opened, "100", "102", "99", "101", "10", opened+FIVE_MS-1,
                    "1000", 10, "5", "500", "0"])
    payloads = [
        {"serverTime": now+5},
        {"symbols": [{"symbol": "BTCUSDT", "quoteAsset": "USDT", "status": "TRADING",
                      "isSpotTradingAllowed": True}]},
        raw,
        {"symbol": "BTCUSDT", "closeTime": now, "quoteVolume": "300000000"},
        {"symbol": "BTCUSDT", "bidPrice": "100.99", "askPrice": "101.00"},
        {"serverTime": now+505},
    ]
    rows = []
    for i, path in enumerate(PATHS):
        params = {} if path == "time" else {"symbol": "BTCUSDT"}
        if path == "klines":
            params.update(interval="5m", limit="34", endTime=str(boundary-1))
        rows.append(dict(path=path, params=params, status="RECEIVED", payload=payloads[i],
                         started_ms=now+i*100, received_ms=now+i*100+10, elapsed_ms=10))
    return rows, now+600


def config():
    a, b = "101", "202"
    return BotSecrets("10001:"+"a"*24, a, b, "10002:"+"b"*24,
                      frozenset((a,b)), frozenset((a,b)), "10003:"+"c"*24, a)


class ChainTests(unittest.TestCase):
    def test_offline_full_path(self):
        rows, now = fixture()
        event = analyze(rows, now, synthetic=True)
        self.assertEqual(event["source_scope"], "SYNTHETIC_TEST_ONLY")
        self.assertEqual([r["indicator_id"] for r in event["indicators"] if r["value"] is not None],
                         ["N01", "N02", "N04"])
        self.assertIsNone(event["signal_id"])
        self.assertIsNone(event["score"])
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            folder = Path(directory)
            stored, outcome = persist(folder, rows, event)
            self.assertEqual(outcome, "LOCAL_SQLITE_COMMITTED_READBACK")
            self.assertEqual(persist(folder, rows, event)[1], "LOCAL_SQLITE_DUPLICATE_IDENTICAL")
            self.assertEqual(stored["sql_projection"]["signals"], [])
            restore = LocalChainJournal(folder / "journal.sqlite").backup_restore_verify(folder / "restore.sqlite")
            self.assertEqual(restore["rows"], 1)
        archive = make_document(event)
        file = archive["manifest"]["file_name"]
        result = extract_desktop_export({"messages": [{"text": archive["caption"], "file": file}]},
                                        {file: archive["document"]})
        self.assertEqual(result["archive_count"], 1)
        calls, notes = [], []
        def api(role, method, fields, attachment):
            calls.append((role, method, fields, attachment))
            if method == "getUpdates":
                case = event["candidate_id"][-12:]
                return [{"message": {"text": "btcusdt " + case, "date": 100, "message_id": n,
                                     "from": {"id": n}, "chat": {"id": n, "type": "private"}}}
                        for n in (101,202)]
            return {"message_id": len(calls), "date": 100,
                    "chat": {"type": "private", "id": int(fields["chat_id"])}}
        launcher.deliver(event, config(), api, lambda label, receipt: notes.append((label, receipt)),
                         lambda _: "", clock=lambda: 100)
        self.assertEqual([x[0] for x in calls], ["05A", "05A", "05B", "05B", "05C", "05C", "05C"])
        self.assertEqual(calls[3][3], (file, archive["document"]))
        self.assertEqual(len(notes), 12)
        self.assertIn("SYNTHETIC_TEST_ONLY", calls[-1][2]["text"])

    def test_malformed_or_future_inputs_are_rejected(self):
        rows, now = fixture()
        for name, mutate in (
            ("gap", lambda r: r[2]["payload"].pop(5)),
            ("duplicate", lambda r: r[2]["payload"].__setitem__(5, r[2]["payload"][4])),
            ("forming", lambda r: r[2]["payload"][-1].__setitem__(6, now+1)),
            ("inverted", lambda r: r[3].__setitem__("received_ms", now+1)),
            ("stale ticker", lambda r: r[3]["payload"].__setitem__("closeTime", now-90000)),
            ("wrong symbol", lambda r: r[4]["payload"].__setitem__("symbol", "ETHUSDT")),
            ("bad clock", lambda r: r[5]["payload"].__setitem__("serverTime", now+5000)),
            ("future boundary", lambda r: r[2]["params"].__setitem__("endTime", str(now+FIVE_MS))),
        ):
            with self.subTest(name=name):
                changed = copy.deepcopy(rows)
                mutate(changed)
                with self.assertRaises(Stop):
                    analyze(changed, now, synthetic=True)

    def test_network_failure_is_not_retried(self):
        rows = []
        def broken(*_):
            raise TimeoutError
        with self.assertRaisesRegex(Stop, "MARKET_REQUEST_FAILED_1"):
            capture(rows, get=broken)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "FAILED")

    def test_partial_delivery_is_not_retried_or_advanced(self):
        rows, now = fixture()
        event = analyze(rows, now, synthetic=True)
        receipts, calls = [], []
        def api(role, method, fields, attachment):
            calls.append(role)
            if len(calls) == 2:
                raise TimeoutError
            return {"message_id": 1, "date": 100,
                    "chat": {"type": "private", "id": int(fields["chat_id"])}}
        with self.assertRaises(TimeoutError):
            launcher.deliver(event, config(), api, lambda _, row: receipts.append(row["status"]), lambda _: "")
        self.assertEqual(calls, ["05A", "05A"])
        self.assertEqual(receipts, ["UNKNOWN_DELIVERY", "API_ACCEPTED", "UNKNOWN_DELIVERY"])

    def test_restart_cannot_overwrite_claim_and_stop_is_sticky(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            folder = Path(directory)
            launcher.save(folder / "market.claim.json", {})
            with self.assertRaises(FileExistsError):
                launcher.save(folder / "market.claim.json", {})
            launcher.save(folder / "stop.json", {})
            with self.assertRaisesRegex(Stop, "KILL_SWITCH_SET"):
                launcher.guard(folder)
