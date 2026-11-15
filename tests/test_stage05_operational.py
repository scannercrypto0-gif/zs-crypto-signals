from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from test_e2e51 import config, fixture
from zs_smart_gate.e2e51 import analyze, persist
from zs_smart_gate.pre05_offline_chain import LocalChainJournal
from zs_smart_gate.stage05_bounded_interactive import bounded_interactive
from zs_smart_gate.stage05_contracts import ContractError, canonical, digest
from zs_smart_gate.stage05_custody import LocalOutbox, VerifiedUpstream
from zs_smart_gate.stage05_delivery import DeliveryCoordinator
from zs_smart_gate.stage05_telegram_http import ApiResult, OwnerPermit, RuntimeFlags


class Fake:
    def __init__(self, updates=(), outcomes=()):
        self.updates = updates
        self.outcomes = iter(outcomes)
        self.sends = []

    def verify_interactive_identity(self, **_):
        return ApiResult("ACCEPTED")

    def verify_no_webhook(self, **_):
        return ApiResult("ACCEPTED")

    def get_updates(self, **_):
        return ApiResult("ACCEPTED", updates=self.updates)

    def send_text(self, chat, text, **opts):
        self.sends.append((chat, text, opts))
        return next(self.outcomes, ApiResult("ACCEPTED", 1, "2026-11-09T12:00:00Z"))

    def send_document(self, chat, text, filename, payload, **opts):
        return self.send_text(chat, text, **opts)


def update(account, msg_id, now, *, bot=False):
    return {"message": {"from": {"id": account, "is_bot": bot}, "chat": {"id": account, "type": "private"},
                        "text": "BTCUSDT", "date": now, "message_id": msg_id}}


class OperationalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = LocalOutbox(self.root / "out.sqlite")
        source, now = fixture()
        self.event = analyze(source, now, synthetic=False)
        self.stored, _ = persist(self.root, source, self.event)
        self.journal = LocalChainJournal(self.root / "journal.sqlite")
        self.ref = self.journal.append_readback(self.stored)[0], digest(canonical(self.stored))
        self.upstream = VerifiedUpstream(self.journal, dict([self.ref]))

    def test_upstream_source_replay_and_policy_veto(self):
        self.assertEqual(self.upstream.read(*self.ref), self.event)
        with self.assertRaisesRegex(ContractError, "REFERENCE_NOT_REVIEWED"):
            self.upstream.read(self.ref[0], "0"*64)
        wrong = VerifiedUpstream(self.journal, {self.ref[0]: "0"*64})
        with self.assertRaisesRegex(ContractError, "READBACK_SHA_MISMATCH"):
            wrong.read(self.ref[0], "0"*64)
        changed = {**self.stored, "source_id": "other", "source_receipts": []}
        ref, _ = self.journal.append_readback(changed)
        with self.assertRaisesRegex(ContractError, "SOURCE_SHA_MISMATCH"):
            sha = digest(canonical(changed))
            VerifiedUpstream(self.journal, {ref: sha}).read(ref, sha)
        fake = Fake()
        coordinator = DeliveryCoordinator(store=self.out, config=config(), transports={"ANALYTICS": fake})
        with self.assertRaisesRegex(ContractError, "OWNER_ACTIVATION"):
            coordinator.step_verified(self.upstream, *self.ref, "C")
        self.assertEqual(fake.sends, [])
        flags = RuntimeFlags(send=True, analytics=True)
        head = "a"*40
        permit = OwnerPermit("OWNER-APPROVED-FIXTURE", head, "2099-01-01T00:00:00Z",
                             frozenset(("ANALYTICS",)), True, True)
        coordinator = DeliveryCoordinator(store=self.out, config=config(), transports={"ANALYTICS": fake},
                                          flags=flags, permit=permit, head_sha=head)
        self.assertEqual(coordinator.step_verified(self.upstream, *self.ref, "C")["status"], "ACCEPTED")
        self.assertEqual(coordinator.step_verified(self.upstream, *self.ref, "C")["status"], "ACCEPTED")
        self.assertEqual(len(fake.sends), 1)
        with self.assertRaisesRegex(ContractError, "UNAUTHORIZED_DESTINATION"):
            coordinator.step_verified(self.upstream, *self.ref, "A")

    def test_local_atomic_claim_and_append_only(self):
        key = "attempt/"+"a"*64
        def reserve(_):
            return LocalOutbox(self.out.path).create_if_absent(key, b"test")
        with ThreadPoolExecutor(max_workers=4) as executor:
            self.assertEqual(sum(executor.map(reserve, range(12))), 1)
        self.assertEqual(LocalOutbox(self.out.path).read(key), b"test")
        with closing(sqlite3.connect(self.out.path)) as db:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "APPEND_ONLY"):
                db.execute("DELETE FROM records")

    def test_outbox_backup_reopen_and_corruption_fail_closed(self):
        key = "attempt/"+"b"*64
        self.out.create_if_absent(key, b"approved")
        dest = self.root / "restore.sqlite"
        with closing(sqlite3.connect(self.out.path)) as src, closing(sqlite3.connect(dest)) as dst:
            src.backup(dst)
        restored = LocalOutbox(dest)
        self.assertEqual(restored.read(key), b"approved")
        with closing(sqlite3.connect(dest)) as db, db:
            db.execute("DROP TRIGGER no_UPDATE")
            db.execute("UPDATE records SET payload=? WHERE key=?", (b"modified", key))
        with self.assertRaisesRegex(ContractError, "PAYLOAD_SHA_MISMATCH"):
            restored.read(key)

    def test_crash_attempt_reopen_no_send(self):
        from zs_smart_gate.stage05_delivery import plan
        job = plan(self.event)[0]
        key = "attempt/" + digest((job.delivery_id+":1").encode())
        self.out.create_if_absent(key, b"previous intent")
        fake = Fake()
        coordinator = DeliveryCoordinator(store=LocalOutbox(self.out.path), config=config(),
                                          simulation=True, transports={"ANALYTICS": fake})
        self.assertEqual(coordinator.step(self.event, "C")["status"], "UNKNOWN_DELIVERY")
        self.assertEqual(fake.sends, [])

    def run_interactive(self, fake, session):
        now = int(datetime.now(timezone.utc).timestamp())
        return bounded_interactive(config=config(), transport=fake, store=LocalOutbox(self.out.path),
                                   upstream=self.upstream, source_ref=self.ref,
                                   started_at=now-10, session_id=session, simulation=True)

    def test_two_real_shaped_humans_readback_and_restart(self):
        now = int(datetime.now(timezone.utc).timestamp())
        fake = Fake((update(101, 1, now), update(101, 1, now), update(202, 2, now)))
        self.assertEqual(self.run_interactive(fake, "one")["status"], "TWO_API_ACCEPTED_REPLIES")
        self.assertEqual([x[0] for x in fake.sends], ["101","202"])
        self.assertEqual([x[2]["reply_to"] for x in fake.sends], [1,2])
        self.assertIn("Snapshot age seconds", fake.sends[0][1])
        self.assertIn("HISTORICAL_SNAPSHOT_ONLY", fake.sends[0][1])
        with self.assertRaisesRegex(ContractError, "ALREADY_CONSUMED"):
            self.run_interactive(fake, "one")
        self.assertEqual(self.run_interactive(fake, "two")["status"], "INTERACTIVE_PRIOR_REPLY_NO_NEW_SEND")
        self.assertEqual(len(fake.sends), 2)

    def test_missing_human_and_unknown_first_reply_stop(self):
        now = int(datetime.now(timezone.utc).timestamp())
        fake = Fake((update(101,1,now), update(202,2,now,bot=True)))
        self.assertEqual(self.run_interactive(fake, "one")["status"], "TWO_HUMAN_REQUESTS_NOT_OBSERVED")
        self.assertEqual(fake.sends, [])
        fake = Fake((update(101,1,now), update(202,2,now)), (ApiResult("UNKNOWN_DELIVERY"),))
        self.assertEqual(self.run_interactive(fake, "two")["status"], "INTERACTIVE_PARTIAL_STOP")
        self.assertEqual(len(fake.sends), 1)

    def test_live_baseline_gate_claim_and_nonacknowledging_poll(self):
        clock = lambda: datetime.now(timezone.utc)
        now = int(clock().timestamp())
        head = "a"*40
        actions = frozenset(("INTERACTIVE_POLL", "INTERACTIVE_REPLY"))
        permit = OwnerPermit("OWNER-APPROVED-FIXTURE", head, "2099-01-01T00:00:00Z",
                             actions, True, True)
        flags = RuntimeFlags(send=True, interactive_poll=True, interactive_reply=True)
        opts = dict(config=config(), transport=None, store=self.out, upstream=self.upstream,
                    source_ref=self.ref, started_at=now, session_id="live",
                    clock=clock, head_sha=head, permit=permit, flags=flags)
        fake = Fake()
        fake.verify_no_webhook = lambda **_: ApiResult("PERMANENT_FAILURE")
        with patch("zs_smart_gate.stage05_bounded_interactive.TelegramHTTP", return_value=fake):
            failed = bounded_interactive(**opts, ready=lambda: self.fail("premature READY"))
        self.assertFalse(failed["claimed"])
        old = {**update(101, 1, now), "update_id": 10}
        new_a = {**update(101, 3, now), "update_id": 11}
        new_b = {**update(202, 4, now), "update_id": 12}
        fake = Fake()
        state = iter(((old,), (old, new_a, new_b)))
        offsets = []
        def get_updates(*, offset, **_):
            offsets.append(offset)
            return ApiResult("ACCEPTED", updates=next(state))
        fake.get_updates = get_updates
        ready = []
        with patch("zs_smart_gate.stage05_bounded_interactive.TelegramHTTP", return_value=fake), patch(
                "zs_smart_gate.stage05_bounded_interactive.time.sleep"):
            result = bounded_interactive(**opts, ready=lambda: ready.append(len(offsets)))
        self.assertEqual(result["status"], "TWO_API_ACCEPTED_REPLIES")
        self.assertEqual(ready, [1])
        self.assertEqual(offsets, [0, 0])
        self.assertEqual([row[2]["reply_to"] for row in fake.sends], [3, 4])
