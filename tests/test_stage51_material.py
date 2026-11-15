from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import tempfile
import unittest

from test_e2e51 import config
from test_stage05_operational import Fake, update
from zs_smart_gate.e2e51 import Stop
from zs_smart_gate.stage03_qv1 import FRAMES, MINUTES, evaluate
from zs_smart_gate.stage05_bounded_interactive import bounded_interactive
from zs_smart_gate.stage05_contracts import ContractError, canonical, digest, parse_utc
from zs_smart_gate.stage05_custody import LocalOutbox
from zs_smart_gate.stage05_interactive import analysis_request_id
from zs_smart_gate.stage05_telegram_http import ApiResult
from zs_smart_gate.stage51_integration import prepare


def bind(row):
    row["source"].update(candles_sha256=digest(canonical(row["candles"])),
                         components_sha256=digest(canonical(row["components"])),
                         setup_state=row["setup_state"])
    row["source_sha256"] = digest(canonical(row["source"]))
    return row


def fixture(horizon="INTRADAY", direction="UP"):
    close = datetime(2026, 11, 9, tzinfo=timezone.utc)
    def stamp(x):
        return x.isoformat().replace("+00:00", "Z")
    candle = {frame: dict(open_at=stamp(close-timedelta(minutes=MINUTES[frame])),
                          close_at=stamp(close), received_at=stamp(close),
                          available_at=stamp(close), closed=True) for frame in FRAMES[horizon]}
    return bind(dict(symbol="BTCUSDT", horizon=horizon, direction=direction, setup_version="1.1",
                     source_scope="SYNTHETIC_TEST_ONLY", setup_state="DETECTED_SIGNAL",
                     event_close_at=stamp(close), decision_at=stamp(close), candles=candle,
                     components={}, source=dict(symbol="BTCUSDT", liquidity={"available_at": stamp(close)},
                                                clock={"available_at": stamp(close)})))


class MaterialGapTests(unittest.TestCase):
    def test_four_research_paths_never_promote(self):
        ids = set()
        for horizon in FRAMES:
            for direction in ("UP","DOWN"):
                row = fixture(horizon,direction)
                result = evaluate(row)
                self.assertEqual(result, evaluate(deepcopy(row)))
                self.assertEqual(result["state"], "DETECTED_SIGNAL")
                self.assertIsNone(result["signal_id"])
                self.assertIsNone(result["score"])
                ids.add(result["event_id"])
        self.assertEqual(len(ids), 4)

    def test_missing_future_tampered_and_n03(self):
        row = fixture()
        del row["candles"]["5m"]
        with self.assertRaisesRegex(ContractError, "NOT_BOUND"):
            evaluate(row)
        self.assertEqual(evaluate(bind(row))["state"], "UNKNOWN")
        row = fixture()
        row["candles"]["5m"]["available_at"] = "2026-11-09T00:00:01Z"
        with self.assertRaisesRegex(ContractError, "CAUSAL_FRAME"):
            evaluate(bind(row))
        row = fixture()
        row["components"]["N03"] = {"status":"PRESENT","reason":"SYNTHETIC"}
        with self.assertRaisesRegex(ContractError, "N03_NOT_APPROVED"):
            evaluate(bind(row))

    def test_recorded_market_to_both_replies_with_durable_bindings(self):
        evidence = Path("research/stage51/live-followup-6761924797")
        row = json.loads((evidence/"stage04-readback.json").read_bytes())
        source = json.loads((evidence/"market-receipts.json").read_bytes())
        decision = parse_utc(row["stage05_event"]["timestamps"]["decision_at"])
        now = decision + timedelta(hours=1)
        def run(fake, session, store, upstream, ref):
            return bounded_interactive(config=config(), transport=fake, store=store,
                                       upstream=upstream, source_ref=ref, started_at=int(now.timestamp())-1,
                                       session_id=session, clock=lambda: now, simulation=True)
        a,b = update(101,1,int(now.timestamp())), update(202,2,int(now.timestamp()))
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            with self.assertRaisesRegex(Stop, "INTEGRATION_READBACK_PIN_MISMATCH"):
                prepare(root, session_id="WRONG-PIN", receipts=source,
                        decision_ms=int(decision.timestamp()*1000), reviewed_readback_sha="0"*64)
            self.assertFalse((root/"journal.sqlite").exists())
            upstream, ref, manifest = prepare(root, session_id="MAT002-RECORDED-REPLAY", receipts=source,
                                              decision_ms=int(decision.timestamp()*1000),
                                              reviewed_readback_sha="a580da9fe08cf44e36d775cfc239704a50014b5d4edc86412f33bf4dcee5da11")
            store = LocalOutbox(root/"outbox.sqlite")
            unauthorized = Fake((a,update(303,3,int(now.timestamp()))))
            self.assertEqual(run(unauthorized,"unauthorized",store,upstream,ref)["replies"], {})
            self.assertEqual(unauthorized.sends, [])
            fake = Fake((a,a,b))
            self.assertEqual(run(fake,"manifest",store,upstream,ref)["status"],"TWO_API_ACCEPTED_REPLIES")
            manifest["routes"] = {}
            for label, (chat, text, opts), message in zip(("A","B"), fake.sends, (1,2), strict=True):
                self.assertEqual(opts["action"],"INTERACTIVE_REPLY")
                self.assertIn("HISTORICAL_SNAPSHOT_ONLY",text)
                self.assertIn("Closed 5m UTC: "+manifest["closed_at"],text)
                self.assertIn("Source SHA256: "+manifest["source_sha256"],text)
                self.assertIn("Decision SHA256: "+manifest["decision_sha256"],text)
                key = digest(canonical({"analysis_request_id":analysis_request_id(chat,chat,message),
                                        "bot":"INTERACTIVE","destination_label":"INTERACTIVE_REQUEST_CHAT"}))
                receipt = json.loads(LocalOutbox(store.path).read("interactive-outcome/"+key))
                self.assertEqual(receipt["reply_sha256"],digest(text.encode()))
                self.assertEqual(receipt["source_sha256"],manifest["source_sha256"])
                manifest["routes"][label] = {"reply_sha256":receipt["reply_sha256"],
                                             "source_sha256":receipt["source_sha256"],
                                             "decision_sha256":manifest["decision_sha256"],
                                             "transport":"SYNTHETIC_FIXTURE"}
            self.assertEqual(run(fake,"manifest-restart",store,upstream,ref)["status"],
                             "INTERACTIVE_PRIOR_REPLY_NO_NEW_SEND")
            self.assertEqual(len(fake.sends),2)
            out = os.environ.get("ZS_MAT002_MANIFEST_OUTPUT")
            if out:
                Path(out).write_bytes(canonical(manifest))

    def test_missing_source_and_unknown_reply(self):
        source = Path("research/stage51/live-followup-6761924797")
        row = json.loads((source/"stage04-readback.json").read_bytes())
        receipts = json.loads((source/"market-receipts.json").read_bytes())
        now = int(datetime.now(timezone.utc).timestamp())
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root=Path(temp)
            upstream, _, _ = prepare(root, session_id="NO-SNAPSHOT", receipts=receipts,
                                     decision_ms=int(parse_utc(row["stage05_event"]["timestamps"]["decision_at"]).timestamp()*1000),
                                     reviewed_readback_sha="a580da9fe08cf44e36d775cfc239704a50014b5d4edc86412f33bf4dcee5da11")
            fake=Fake((update(101,1,now), update(202,2,now)), (ApiResult("UNKNOWN_DELIVERY"),))
            result=bounded_interactive(config=config(), transport=fake, store=LocalOutbox(root/"out.sqlite"),
                                       upstream=upstream, source_ref=None, started_at=now,
                                       session_id="absent", simulation=True)
            self.assertEqual(result["status"],"INTERACTIVE_PARTIAL_STOP")
            self.assertEqual(len(fake.sends),1)
            self.assertIn("NO_APPROVED_SNAPSHOT",fake.sends[0][1])
