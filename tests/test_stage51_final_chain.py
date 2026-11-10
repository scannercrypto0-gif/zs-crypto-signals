from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import tempfile
import unittest

from test_e2e51 import config, fixture
from test_stage05_operational import Fake, update
from zs_smart_gate.stage05_bounded_interactive import bounded_interactive
from zs_smart_gate.stage05_custody import LocalOutbox
from zs_smart_gate.stage05_contracts import digest
from zs_smart_gate.stage51_live_chain import run_chain


class FinalChainTests(unittest.TestCase):
    def run_fixture(self, archive_status):
        rows, now = fixture()
        clocks = iter(v for row in rows for v in (row["started_ms"],row["received_ms"]))
        calls = []
        def get(path, params):
            row = rows[len(calls)]
            self.assertEqual((path,params),(row["path"],row["params"]))
            calls.append(path)
            return row["payload"]
        def archive(manifest, document):
            self.assertEqual(manifest["archive_sha256"],digest(document["document"]))
            calls.append("05B")
            return archive_status
        def interactive(upstream, ref):
            event = upstream.read(*ref)
            self.assertIsNone(event["signal_id"])
            snapshot = upstream.snapshot(*ref, "BTCUSDT")
            self.assertEqual(snapshot["source_sha256"], event["source_manifest_sha256"])
            calls.append("05C")
            clock = datetime.fromtimestamp(now/1000 + 1, timezone.utc)
            start = int(clock.timestamp())
            request = update(101,1,start)
            request["message"]["text"] = "btcusdt"
            fake = Fake((update(202,2,start), request))
            reply = bounded_interactive(config=config(), transport=fake, store=LocalOutbox(root/"out.sqlite"),
                                        upstream=upstream, source_ref=ref, started_at=start,
                                        session_id="FIXTURE-05C", clock=lambda: clock, simulation=True, account_a_only=True)
            self.assertEqual(reply["status"], "ACCOUNT_A_API_ACCEPTED_REPLY")
            self.assertEqual([r[0] for r in fake.sends], ["101"])
            for _, text, _ in fake.sends:
                self.assertIn(snapshot["source_sha256"], text)
                self.assertIn(snapshot["decision_sha256"], text)
            return {"status":"FIXTURE_ONLY", "source_sha256":snapshot["source_sha256"]}
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            result = run_chain(root, session="SYNTHETIC_TEST_ONLY", get=get,
                               acquisition_clock=lambda: next(clocks), decision_clock=lambda: now,
                               archive=archive, interactive=interactive, receipts=[])
        self.assertEqual(result["stage05a"],"NO_QUALIFIED_SIGNAL_OBSERVED")
        return calls, result

    def test_one_fixture_chain_and_unknown_delivery_stop(self):
        calls, result = self.run_fixture("API_ACCEPTED")
        self.assertEqual(len(calls),8)
        self.assertEqual(result["source_sha256"],result["stage05c"]["source_sha256"])
        calls, result = self.run_fixture("UNKNOWN_DELIVERY")
        self.assertEqual(len(calls),7)
        self.assertEqual(result["stage05c"],"NOT_ATTEMPTED")

    def test_owner_scope_rejects_changed_contract(self):
        from zs_smart_gate.e2e51 import Stop
        spec = importlib.util.spec_from_file_location("runner", Path("scripts/stage51-final-once.py"))
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        raw = Path("research/stage51/closure/LIVE_SESSION_CONTRACT.md").read_bytes()
        runner.check_contract(raw)
        self.assertTrue(runner.OWNER_AUTHORITY.endswith("6767851362"))
        with self.assertRaisesRegex(Stop, "CONTRACT_SHA_MISMATCH"):
            runner.check_contract(raw + b"changed")
