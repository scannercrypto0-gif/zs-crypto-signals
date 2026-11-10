"""Focused 05C live-shaped offline tests using only synthetic Telegram fakes.

Never calls Bot API or Binance. Does not re-run earlier accepted 16 tests.
"""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_e2e51 import config
from zs_smart_gate.pre05_offline_chain import LocalChainJournal
from zs_smart_gate.stage05_bounded_interactive import bounded_interactive
from zs_smart_gate.stage05_custody import LocalOutbox, VerifiedUpstream
from zs_smart_gate.stage05_telegram_http import ApiResult, OwnerPermit, RuntimeFlags

START = 1762770000


def row(account, message_id, update_id, *, text="BTCUSDT"):
    return {"update_id": update_id, "message": {
        "from": {"id": account, "is_bot": False},
        "chat": {"id": account, "type": "private"},
        "text": text, "message_id": message_id, "date": START}}


class SequenceTelegram:
    def __init__(self, batches):
        self.batches = iter(batches)
        self.offsets = []
        self.sent = []

    def verify_interactive_identity(self, **_):
        return ApiResult("ACCEPTED")

    def verify_no_webhook(self, **_):
        return ApiResult("ACCEPTED")

    def get_updates(self, *, offset, **_):
        self.offsets.append(offset)
        return ApiResult("ACCEPTED", updates=tuple(next(self.batches, ())))

    def send_text(self, chat_id, _text, **opts):
        self.sent.append((str(chat_id), opts.get("reply_to")))
        return ApiResult("ACCEPTED", 900 + len(self.sent), "2026-11-10T09:10:00Z")


class Stage05CBoundedForensicIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.store = LocalOutbox(root / "out.sqlite")
        self.upstream = VerifiedUpstream(LocalChainJournal(root / "journal.sqlite"), {})
        self.clock = lambda: datetime.fromtimestamp(START, timezone.utc)
        head = "a" * 40
        self.permit = OwnerPermit("OWNER-APPROVED-LOCAL-FIXTURE", head,
                                  "2099-01-01T00:00:00Z",
                                  frozenset(("INTERACTIVE_POLL", "INTERACTIVE_REPLY")),
                                  True, True)
        self.opts = dict(config=config(), transport=None, store=self.store,
                         upstream=self.upstream, source_ref=None,
                         started_at=START, session_id="ONLY-LOCAL-FIXTURE",
                         head_sha=head, permit=self.permit,
                         flags=RuntimeFlags(send=True, interactive_poll=True,
                                            interactive_reply=True),
                         clock=self.clock, ready=lambda: None)

    def invoke(self, fake):
        with patch("zs_smart_gate.stage05_bounded_interactive.TelegramHTTP", return_value=fake), patch(
                "zs_smart_gate.stage05_bounded_interactive.time.sleep"):
            return bounded_interactive(**self.opts)

    def test_two_humans_split_polls_normalized_and_reply_bound(self):
        old = row(101, 5, 10)
        a = row(101, 31, 11, text=" btcusdt ")
        b = row(202, 42, 12)
        fake = SequenceTelegram(((old,), (old, a), (old, a, b)))
        result = self.invoke(fake)
        self.assertEqual(result["status"], "TWO_API_ACCEPTED_REPLIES")
        self.assertEqual(fake.offsets, [0, 0, 0])
        self.assertEqual(fake.sent, [("101", 31), ("202", 42)])
        self.assertEqual(result["inbound_diagnostics"]["seen"], {"A": True, "B": True})
        self.assertEqual(result["inbound_diagnostics"]["baseline_update_count"], 1)
        self.assertEqual(result["inbound_diagnostics"]["reason_totals"]["BELOW_BASELINE"], 2)

    def test_backlog_full_fails_closed_without_advancing_offset(self):
        full = tuple(row(303, i, i) for i in range(1, 21))
        fake = SequenceTelegram(((), full))
        result = self.invoke(fake)
        self.assertEqual(result["status"], "INTERACTIVE_BACKLOG_FULL_NO_CURSOR_ADVANCE")
        self.assertEqual(fake.offsets, [0, 0])
        self.assertEqual(fake.sent, [])
        self.assertEqual(result["inbound_diagnostics"]["reason_totals"],
                         {"UNAUTHORIZED_ACCOUNT": 20})

    def test_empty_vs_rejected_updates_disambiguated(self):
        fake = SequenceTelegram(((), (row(303, 1, 11),), ()))
        result = self.invoke(fake)
        self.assertEqual(result["status"], "TWO_HUMAN_REQUESTS_NOT_OBSERVED")
        self.assertEqual(result["inbound_diagnostics"]["reason_totals"],
                         {"EMPTY_BATCH": 6, "UNAUTHORIZED_ACCOUNT": 1})
        self.assertEqual(fake.offsets, [0] * 8)
        self.assertEqual(fake.sent, [])


if __name__ == "__main__":
    unittest.main()
