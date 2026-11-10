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
            fake = Fake((update(101,1,start), update(202,2,start)))
            reply = bounded_interactive(config=config(), transport=fake, store=LocalOutbox(root/"out.sqlite"),
                                        upstream=upstream, source_ref=ref, started_at=start,
                                        session_id="FIXTURE-05C", clock=lambda: clock, simulation=True)
            self.assertEqual(reply["status"], "TWO_API_ACCEPTED_REPLIES")
            self.assertEqual([r[0] for r in fake.sends], ["101", "202"])
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

    def test_approval_rejects_wrong_pin_and_same_reference(self):
        from zs_smart_gate.e2e51 import Stop
        from zs_smart_gate.stage05_contracts import canonical
        spec = importlib.util.spec_from_file_location("runner", Path("scripts/stage51-final-once.py"))
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            path = Path(temp) / "permit.json"
            path.write_bytes(b"{}")
            with self.assertRaisesRegex(Stop, "EXACT_SHA"):
                runner.approval(path, "a", "b", "c")
            ref = "https://github.com/scannercrypto0-gif/zs-crypto-signals/issues/51#issuecomment-1"
            path.write_bytes(canonical(dict(head="a", tree="b", contract_sha256="c",
                session=runner.SESSION, pm_status="EXACT_SHA_GO", owner_status="SESSION_APPROVED",
                pm_ref=ref, owner_ref=ref)))
            with self.assertRaisesRegex(Stop, "DISTINCT_APPROVAL"):
                runner.approval(path, "a", "b", "c")
