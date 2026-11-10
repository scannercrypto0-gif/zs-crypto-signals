"""Only new Stage05 3-bot/HTTP/outbox/SQL/UTC/auth tests; Windows-only.

Every Telegram response is fake. No bot secrets, network, SQL connection,
market data, old 00-04 tests, GitHub writer, polling or auto activation.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
import unittest
from unittest.mock import patch

from zs_smart_gate.stage05_contracts import (
    ContractError, canonical, digest, ensure_event, make_document,
    extract_desktop_export, sql_projection, utc_now,
)
from zs_smart_gate.stage05_delivery import (
    DeliveryCoordinator, MemoryOutbox, GithubOutbox, plan,
)
from zs_smart_gate.stage05_telegram_http import (
    ApiResult, BotSecrets, RuntimeFlags, TelegramHTTP, require_live_permission,
)
from zs_smart_gate.stage05_interactive import (
    InteractiveService, parse_symbol, respond_once,
)

DUMMY_SIGNAL_TOKEN = "123456:" + "A" * 35
DUMMY_ANALYTICS_TOKEN = "234567:" + "B" * 35
DUMMY_INTERACTIVE_TOKEN = "345678:" + "C" * 35
T0 = datetime(2026, 11, 9, 9, 0, 0, tzinfo=timezone.utc)


def config():
    return BotSecrets(
        DUMMY_SIGNAL_TOKEN, "1001", "1002", DUMMY_INTERACTIVE_TOKEN,
        frozenset(("1001", "1002")), frozenset(("1001", "1002")),
        DUMMY_ANALYTICS_TOKEN, "1001",
    )


def event(rejected=False):
    return {
        "schema": "zs.stage05.event.v1",
        "event_type": "REJECTED_CANDIDATE" if rejected else "QUALIFIED_SIGNAL",
        "candidate_id": "SYNTHETIC.CANDIDATE.001",
        "signal_id": None if rejected else "SYNTHETIC.SIGNAL.001",
        "detection_event_key": "SYNTHETIC.EVENT.20261109.001",
        "qualification_status": "REJECTED" if rejected else "QUALIFIED",
        "qualification_authority": None if rejected else "EXPLICIT_APPROVED_UPSTREAM",
        "qualification_evidence_sha256": None if rejected else "a" * 64,
        "source_scope": "SYNTHETIC_TEST_ONLY",
        "candidate_origin": "QUALIFICATION_CANDIDATE",
        "source_quality": "VALIDATED",
        "symbol": "BTCUSDT", "direction": "UP", "horizon": "INTRADAY",
        "setup_version": "V1.1",
        "timestamps": {
            "decision_candle_open_at": "2026-11-09T08:30:00Z",
            "decision_candle_close_at": "2026-11-09T08:35:00Z",
            "received_at": "2026-11-09T08:35:01.100Z",
            "available_at": "2026-11-09T08:35:01.200Z",
            "decision_at": "2026-11-09T08:35:01.201Z",
            "record_created_at": "2026-11-09T08:35:01.250Z",
        },
        "clock": {
            "source": "SYNTHETIC_CLOCK", "precision": "MILLISECONDS",
            "offset_ms": 0, "uncertainty_ms": 0,
        },
        "gates": [{
            "gate_id": "SYNTHETIC_DEMO_GATE",
            "state": "FAIL" if rejected else "PASS",
            "reason_codes": ["TEST_REJECT"] if rejected else [],
        }],
        "reject_reason_codes": ["TEST_REJECT"] if rejected else [],
        "indicators": [{
            "indicator_id": "N01", "value": "0.62", "availability": "PRESENT",
            "unit": "fraction", "timeframe": "30m", "source": "SYNTHETIC",
            "as_of": "2026-11-09T08:35:00Z", "version": "N01.V1",
            "raw_value": "0.62", "threshold": None, "evaluation": "UNKNOWN",
            "reason_codes": [],
        }, {
            "indicator_id": "N03", "value": None, "availability": "MISSING",
            "unit": None, "timeframe": None, "source": None,
            "as_of": None, "version": None, "raw_value": None,
            "threshold": None, "evaluation": "UNKNOWN",
            "reason_codes": ["R2_MOMENTUM_EARLY_TIMING_UNAVAILABLE"],
        }],
        "score": None, "trade_plan": None,
        "source_metadata": {"source_id": "SYNTHETIC:TEST", "receipt_scope": "TEST_ONLY"},
        "candle_metadata": {"timeframe": "30m", "closed": True},
        "scan_metadata": {"scan_cycle_id": "SYNTHETIC.SCAN.001"},
        "quality_metadata": {"source_quality": "VALIDATED"},
        "outcome_links": [],
    }


class FakeBot:
    def __init__(self, statuses=None):
        self.statuses = list(statuses or ["ACCEPTED"])
        self.requests = []

    def send_text(self, chat, text, **kwargs):
        self.requests.append(("text", chat, text, kwargs.get("action")))
        status = self.statuses.pop(0)
        return ApiResult(status, 91, "2026-11-09T09:00:00Z") if status == "ACCEPTED" else (
            ApiResult(status, retry_after_s=2) if status == "RATE_LIMITED" else ApiResult(status))

    def send_document(self, chat, caption, filename, data, **kwargs):
        self.requests.append(("doc", chat, caption, filename, digest(data)))
        status = self.statuses.pop(0)
        return ApiResult(status, 92, "2026-11-09T09:00:00Z") if status == "ACCEPTED" else ApiResult(status)


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self.headers = {}
        self.raw = canonical(payload)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, n=-1):
        return self.raw[:n]


class Stage05RealTransportTargeted(unittest.TestCase):

    def test_three_distinct_bot_config_and_live_switches_fail_closed(self):
        cfg = config()
        cfg.validate()
        self.assertNotIn(DUMMY_SIGNAL_TOKEN, repr(cfg))
        self.assertEqual(RuntimeFlags.from_environ({}), RuntimeFlags())
        leak = event()
        leak["bot_token"] = DUMMY_SIGNAL_TOKEN
        with self.assertRaisesRegex(ContractError, "UNRECOGNIZED_ARCHIVE_FIELDS"):
            make_document(leak)
        leak = event()
        leak["source_metadata"]["secret_token"] = DUMMY_SIGNAL_TOKEN
        with self.assertRaisesRegex(ContractError, "SENSITIVE_ARCHIVE_FIELD_FORBIDDEN"):
            make_document(leak)
        all_on = RuntimeFlags(True, True, True, True, True)
        with self.assertRaisesRegex(ContractError, "OWNER_ACTIVATION"):
            require_live_permission(flags=all_on, permit=None,
                                    head_sha="f" * 40, action="SIGNALS")
        http = TelegramHTTP(DUMMY_SIGNAL_TOKEN)
        self.assertNotIn(DUMMY_SIGNAL_TOKEN, repr(http))
        with patch("zs_smart_gate.stage05_telegram_http.build_opener") as actual:
            with self.assertRaisesRegex(ContractError, "OWNER_ACTIVATION"):
                http.send_text("1001", "not sent", flags=all_on,
                               permit=None, head_sha="f" * 40)
            actual.assert_not_called()
        with self.assertRaisesRegex(ContractError, "OUTBOX_DEDICATED_STAGE05_BRANCH_REQUIRED"):
            GithubOutbox(object(), "main", verified_backend=True)
        dedicated = GithubOutbox(object(), "evidence-stage05-owner-test")
        self.assertFalse(dedicated.verified_backend)
        with self.assertRaisesRegex(ContractError, "THREE_DISTINCT"):
            BotSecrets(DUMMY_SIGNAL_TOKEN, "1001", "1002",
                       DUMMY_SIGNAL_TOKEN, frozenset(("1001", "1002")),
                       frozenset(("1001", "1002")),
                       DUMMY_ANALYTICS_TOKEN, "1001").validate()

    def test_owner_two_account_contract_rejects_cross_account_and_third_chat(self):
        cfg = config()
        cfg.validate()  # A=1001, B=1002, C=A
        self.assertEqual(cfg.analytics_chat, cfg.signals_chat_a)
        self.assertNotEqual(cfg.signals_chat_a, cfg.signals_chat_b)
        changed = dict(
            signals_token=cfg.signals_token, signals_chat_a=cfg.signals_chat_a,
            signals_chat_b=cfg.signals_chat_b,
            interactive_token=cfg.interactive_token,
            interactive_users=cfg.interactive_users,
            interactive_chats=cfg.interactive_chats,
            analytics_token=cfg.analytics_token, analytics_chat=cfg.analytics_chat,
        )
        cases = (
            ("SIGNALS_A_B_MUST_DIFFER", {"signals_chat_b": "1001"}),
            ("ANALYTICS_C_MUST_EQUAL_SIGNALS_A", {"analytics_chat": "1003"}),
            ("INTERACTIVE_TWO_ACCOUNT_ALLOWLIST_REQUIRED",
             {"interactive_users": frozenset(("1001",))}),
            ("INTERACTIVE_TWO_ACCOUNT_ALLOWLIST_REQUIRED",
             {"interactive_chats": frozenset(("1001", "1002", "1003"))}),
            ("INTERACTIVE_TWO_ACCOUNT_ALLOWLIST_REQUIRED",
             {"interactive_users": frozenset()}),
            ("INTERACTIVE_TWO_ACCOUNT_ALLOWLIST_REQUIRED",
             {"interactive_chats": frozenset()}),
            ("THREE_DISTINCT_BOT_TOKENS_REQUIRED",
             {"analytics_token": cfg.signals_token}),
        )
        for error, overrides in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ContractError, error):
                    BotSecrets(**{**changed, **overrides}).validate()

    def test_qualified_abc_same_signal_rejected_only_c(self):
        good, bad = event(), event(True)
        self.assertEqual([j.destination for j in plan(good)], ["A", "B", "C"])
        self.assertEqual([j.destination for j in plan(bad)], ["C"])
        self.assertEqual({j.signal_id for j in plan(good)},
                         {"SYNTHETIC.SIGNAL.001"})
        self.assertEqual(plan(bad)[0].signal_id, None)
        self.assertEqual(len(sql_projection(good)["signals"]), 1)
        self.assertEqual(len(sql_projection(bad)["signals"]), 0)
        self.assertTrue(sql_projection(bad)["candidate_decisions"])
        with self.assertRaisesRegex(ContractError, "REJECTED_MUST_NOT"):
            changed = event(True)
            changed["signal_id"] = "FORGED"
            ensure_event(changed)
        # Real send cannot use synthetic fixtures even with fake transport.
        coord = DeliveryCoordinator(store=MemoryOutbox(), config=config())
        with self.assertRaisesRegex(ContractError, "SYNTHETIC_EVENT_LIVE"):
            coord.step(good, "A")
        # Self-declared real-source hashes are NOT independent qualification evidence.
        forged = event()
        forged.update(source_scope="APPROVED_REAL_SOURCE",
                      source_manifest_id="FAKE.MANIFEST",
                      source_manifest_sha256="b" * 64,
                      candle_window_sha256="c" * 64,
                      scan_cycle_id="FAKE.SCAN", quality_policy_version="TEST")
        forged["clock"]["source"] = "MEASURED_CLOCK"
        with self.assertRaisesRegex(ContractError, "VERIFIED_UPSTREAM_READBACK_REQUIRED"):
            coord.step(forged, "A")

    def test_independent_per_chat_receipts_and_duplicate_suppression(self):
        t = [0]
        def clock():
            return T0 + timedelta(seconds=t[0])
        sig, ana = FakeBot(["ACCEPTED", "ACCEPTED"]), FakeBot()
        store = MemoryOutbox()
        coord = DeliveryCoordinator(
            store=store, config=config(), clock=clock,
            transports={"SIGNALS": sig, "ANALYTICS": ana},
            simulation=True)
        observed = []
        for dest in ("A", "B", "C"):
            t[0] += 2
            result = coord.step(event(), dest)
            self.assertEqual(result["status"], "ACCEPTED", result)
            observed.append(result["receipt"])
        self.assertEqual([r["destination_label"] for r in observed],
                         ["A", "B", "C"])
        self.assertEqual({r["signal_id"] for r in observed},
                         {"SYNTHETIC.SIGNAL.001"})
        self.assertEqual(len({r["delivery_id"] for r in observed}), 3)
        self.assertEqual(len(sig.requests), 2)
        self.assertEqual(len(ana.requests), 1)
        self.assertEqual(sig.requests[0][1], "1001")
        self.assertIn("SCORE_UNAVAILABLE (NO_APPROVED_SCORE)", sig.requests[0][2])
        self.assertIn("Gate decisions:", sig.requests[0][2])
        self.assertIn("Trade plan: RESEARCH_ONLY", sig.requests[0][2])
        complete = event()
        complete["trade_plan"] = {"approved": True, "version": "TEST.V1",
                                  "entry_zone": "100-101", "stop_loss": "98",
                                  "tp1": "103", "tp2": "105", "tp3": "108"}
        complete["score"] = {"approved": True, "value": "75", "version": "TEST.V1"}
        with_plan = DeliveryCoordinator(store=MemoryOutbox(), config=config(),
                                        clock=clock, transports={"SIGNALS": FakeBot()},
                                        simulation=True)
        with_plan.step(complete, "A")
        self.assertIn("Entry zone: 100-101", with_plan.transports["SIGNALS"].requests[0][2])
        self.assertIn("Score: 75", with_plan.transports["SIGNALS"].requests[0][2])
        self.assertEqual(sig.requests[1][1], "1002")
        self.assertEqual(ana.requests[0][1], "1001")
        self.assertEqual(sig.requests[0][3], "SIGNALS")
        self.assertEqual(ana.requests[0][0], "doc")
        again = coord.step(event(), "A")
        self.assertEqual(again["status"], "ACCEPTED")
        self.assertEqual(len(sig.requests), 2)
        for receipt in observed:
            self.assertIsNotNone(receipt["telegram_accepted_at"])
            self.assertEqual(receipt["telegram_message_date_at"],
                             "2026-11-09T09:00:00Z")
            self.assertNotIn(DUMMY_SIGNAL_TOKEN, str(receipt))
        self.assertGreater(len(store.records), 6)

    def test_429_bounded_retry_and_unknown_outcome_never_replayed(self):
        tick = [0]
        def clock():
            return T0 + timedelta(seconds=tick[0])
        # 429 is explicitly not accepted; permitted retry after 2s.
        bot = FakeBot(["RATE_LIMITED", "ACCEPTED"])
        coord = DeliveryCoordinator(
            store=MemoryOutbox(), config=config(), clock=clock,
            transports={"SIGNALS": bot}, simulation=True)
        first = coord.step(event(), "A")
        self.assertEqual(first["status"], "RATE_LIMITED")
        self.assertEqual(coord.step(event(), "A")["status"], "RATE_LIMITED")
        self.assertEqual(len(bot.requests), 1)
        tick[0] += 3
        second = coord.step(event(), "A")
        self.assertEqual(second["status"], "ACCEPTED")
        self.assertEqual(len(bot.requests), 2)
        # 5xx/timeout could be delivered: never automatically send twice.
        uncertain = FakeBot(["UNKNOWN_DELIVERY"])
        store = MemoryOutbox()
        one = DeliveryCoordinator(store=store, config=config(), clock=clock,
                                  transports={"SIGNALS": uncertain},
                                  simulation=True)
        self.assertEqual(one.step(event(), "B")["status"], "UNKNOWN_DELIVERY")
        restarted = DeliveryCoordinator(store=store, config=config(), clock=clock,
                                        transports={"SIGNALS": uncertain},
                                        simulation=True)
        self.assertEqual(restarted.step(event(), "B")["status"], "UNKNOWN_DELIVERY")
        self.assertEqual(len(uncertain.requests), 1)

    def test_real_http_request_shapes_429_5xx_network_and_seconds(self):
        requests = []
        def good_opener(request, timeout):
            requests.append((request.get_method(), request.full_url,
                             request.get_header("Content-type"), request.data,
                             timeout))
            return FakeResponse(200, {"ok": True, "result": {
                "message_id": 71, "date": 1794214800,
                "chat": {"id": 1001, "type": "private"}}})
        http = TelegramHTTP(DUMMY_SIGNAL_TOKEN, test_opener=good_opener)
        result = http.send_text("1001", "SYNTHETIC TEST")
        self.assertEqual(result.status, "ACCEPTED")
        self.assertEqual(result.message_id, 71)
        self.assertRegex(result.message_date_at, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(requests[0][0], "POST")
        self.assertTrue(requests[0][1].endswith("/sendMessage"))
        self.assertEqual(json.loads(requests[0][3])["chat_id"], "1001")
        archive = make_document(event())
        http.send_document("1003", archive["caption"], archive["manifest"]["file_name"],
                           archive["document"], action="ANALYTICS")
        self.assertIn(b'name="document"', requests[1][3])
        self.assertTrue(requests[1][1].endswith("/sendDocument"))
        self.assertIn(archive["document"], requests[1][3])
        def rate(request, timeout):
            raise HTTPError(request.full_url, 429, "rate", {"Retry-After": "3"},
                            BytesIO(canonical({"ok": False, "parameters": {"retry_after": 3}})))
        self.assertEqual(TelegramHTTP(DUMMY_SIGNAL_TOKEN, test_opener=rate)
                         .send_text("1001", "test").retry_after_s, 3)
        def server(request, timeout):
            return FakeResponse(503, {"ok": False})
        self.assertEqual(TelegramHTTP(DUMMY_SIGNAL_TOKEN, test_opener=server)
                         .send_text("1001", "test").status, "UNKNOWN_DELIVERY")
        def network(request, timeout):
            raise URLError("synthetic network failure")
        self.assertEqual(TelegramHTTP(DUMMY_SIGNAL_TOKEN, test_opener=network)
                         .send_text("1001", "test").status, "UNKNOWN_DELIVERY")

    def test_utc_sha_archive_desktop_and_sql_normalization_conflicts(self):
        good = event(True)
        archive = make_document(good)
        self.assertEqual(digest(archive["document"]), archive["manifest"]["sha256"])
        export = {"messages": [{"id": 90, "text": archive["caption"],
                                 "file": archive["manifest"]["file_name"]}]}
        docs = {archive["manifest"]["file_name"]: archive["document"]}
        extracted = extract_desktop_export(export, docs)
        self.assertEqual(extracted["archive_count"], 1)
        self.assertFalse(extracted["stage06b_real_roundtrip_verified"])
        self.assertIn(b"REJECTED_CANDIDATE", extracted["events_ndjson"])
        with self.assertRaisesRegex(ContractError, "EXPORT_ATTACHMENT_MISSING"):
            extract_desktop_export(export, {})
        with self.assertRaisesRegex(ContractError, "EXPORT_ATTACHMENT_SHA_MISMATCH"):
            extract_desktop_export(export, {archive["manifest"]["file_name"]: b"corrupt"})
        changed = event(True)
        changed["reject_reason_codes"] = ["DIFFERENT"]
        second = make_document(changed)
        export["messages"].append({
            "id": 91, "text": second["caption"],
            "file": second["manifest"]["file_name"],
        })
        docs[second["manifest"]["file_name"]] = second["document"]
        with self.assertRaisesRegex(ContractError, "EXPORT_DUPLICATE_CONTENT_CONFLICT"):
            extract_desktop_export(export, docs)
        with self.assertRaisesRegex(ContractError, "FUTURE_INDICATOR_FORBIDDEN"):
            future = event()
            future["indicators"][0]["as_of"] = "2026-11-09T10:00:00Z"
            ensure_event(future)
        self.assertEqual(utc_now(lambda: T0), "2026-11-09T09:00:00Z")
        self.assertEqual(utc_now(lambda: T0.replace(microsecond=184000)),
                         "2026-11-09T09:00:00.184000Z")
        proj = sql_projection(good)
        self.assertEqual(proj["candidates"][0]["qualification_status"], "REJECTED")
        self.assertIsNone(good["signal_id"])

    def test_interactive_lowercase_auth_no_new_signal_separate_bot(self):
        def lookup(symbol):
            return {"symbol": symbol, "as_of": "2026-11-09T08:55:00Z",
                    "source_scope": "SYNTHETIC_TEST_ONLY",
                    "decision": "RESEARCH_ONLY", "score": None,
                    "indicators": [{
                        "indicator_id": "N01", "value": "0.62", "raw_value": "0.620",
                        "availability": "PRESENT", "evaluation": "UNKNOWN",
                        "threshold": "NOT_APPROVED", "unit": "fraction",
                        "timeframe": "30m", "source": "SYNTHETIC",
                        "as_of": "2026-11-09T08:55:00Z", "version": "N01.V1",
                        "reason_codes": [],
                    }]}
        service = InteractiveService(
            config=config(), supported_symbols={"BTCUSDT", "ETHUSDT"},
            lookup=lookup, clock=lambda: T0)
        self.assertEqual(parse_symbol("btcusdt", {"BTCUSDT"}), "BTCUSDT")
        self.assertEqual(service.accept(text="btcusdt", user_id=1003,
                                        chat_id=1003, message_id=1)["status"], "UNAUTHORIZED")
        queued = service.accept(text="btcusdt", user_id=1001,
                                chat_id=1001, message_id=123)
        self.assertEqual(queued["symbol"], "BTCUSDT")
        self.assertIsNone(queued["signal_id"])
        second = service.accept(text="ethusdt", user_id=1002,
                                chat_id=1002, message_id=124)
        self.assertEqual(second["symbol"], "ETHUSDT")
        self.assertNotEqual(second["analysis_request_id"], queued["analysis_request_id"])
        self.assertIsNone(second["signal_id"])
        # Both IDs belong to allowed accounts, but crossed pairs must fail.
        self.assertEqual(service.accept(text="btcusdt", user_id=1001,
                                        chat_id=1002, message_id=125)["status"], "UNAUTHORIZED")
        self.assertEqual(service.accept(text="btcusdt", user_id=1002,
                                        chat_id=1001, message_id=126)["status"], "UNAUTHORIZED")
        self.assertEqual(len(service.queue), 2)
        result = service.process_one()
        self.assertEqual(result["status"], "READ_ONLY_ANALYSIS")
        rendered = service.format_reply(result)
        for token in ("N01", "raw=0.620", "evaluation=UNKNOWN", "version=N01.V1",
                      "Freshness: NOT_REALTIME_VERIFIED",
                      "Source scope: SYNTHETIC_TEST_ONLY", "SCORE_UNAVAILABLE"):
            self.assertIn(token, rendered)
        self.assertEqual(service.accept(text="btcusdt", user_id=1001,
                                        chat_id=1001, message_id=123)["status"], "DUPLICATE")
        with self.assertRaisesRegex(ContractError, "SPOT_USDT_SYMBOL_NOT_IN"):
            parse_symbol("solusdt", {"BTCUSDT", "ETHUSDT"})
        response = dict(result, reply_text=service.format_reply(result))
        # Two authorized independent private chats require two fake ACKs.
        fake = FakeBot(["ACCEPTED", "ACCEPTED"])
        ack = respond_once(response=response, chat_id=1001, user_id=1001,
                           config=config(), store=MemoryOutbox(),
                           transport=fake, clock=lambda: T0, simulation=True)
        self.assertEqual(ack["status"], "ACCEPTED")
        self.assertEqual(fake.requests[0][3], "INTERACTIVE_REPLY")
        second_result = service.process_one()
        self.assertEqual(second_result["status"], "READ_ONLY_ANALYSIS")
        second_response = dict(second_result, reply_text=service.format_reply(second_result))
        ack_b = respond_once(response=second_response, chat_id=1002, user_id=1002,
                             config=config(), store=MemoryOutbox(),
                             transport=fake, clock=lambda: T0, simulation=True)
        self.assertEqual(ack_b["status"], "ACCEPTED")
        self.assertEqual([str(request[1]) for request in fake.requests], ["1001", "1002"])
        for bad_user, bad_chat in ((1001, 1002), (1002, 1001), (1003, 1003)):
            with self.subTest(user=bad_user, chat=bad_chat):
                with self.assertRaisesRegex(ContractError, "RECIPIENT_NOT_AUTHORIZED"):
                    respond_once(response=response, chat_id=bad_chat, user_id=bad_user,
                                 config=config(), store=MemoryOutbox(),
                                 transport=fake, clock=lambda: T0, simulation=True)
        self.assertEqual(len(fake.requests), 2)

    def test_sql_server_ddl_primary_foreign_unique_and_no_runtime_connection(self):
        path = Path(__file__).resolve().parents[1] / "research" / "stage05" / "sqlserver-contract-v1.sql"
        sql = path.read_text(encoding="utf-8")
        for name in ("assets", "candidates", "signals", "indicator_values",
                     "candidate_decisions", "telegram_deliveries",
                     "signal_features", "trade_plans", "signal_outcomes",
                     "signal_updates", "analysis_requests", "source_manifests",
                     "scan_cycles", "delivery_attempts"):
            with self.subTest(table=name):
                self.assertIn("dbo." + name, sql)
        self.assertIn("FOREIGN KEY", sql.upper() if "FOREIGN KEY" in sql.upper() else sql)
        self.assertIn("UQ_telegram_actual_message", sql)
        self.assertIn("CK_delivery_subject_exactly_one", sql)
        self.assertIn("UQ_delivery_interactive_request_route", sql)
        self.assertIn("analysis_request_id char(64) NULL REFERENCES", sql)
        self.assertIn("datetime2(6)", sql.lower())
        self.assertNotIn("CREATE DATABASE", sql)
