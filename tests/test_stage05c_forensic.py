"""Focused offline-only Stage05C matcher diagnostics; no Bot API, Binance, or live runner."""
import unittest

from zs_smart_gate.stage05c_inbound_forensics import InboundDiagnostics, classify_inbound

ACCOUNTS = {"A": "101", "B": "202"}
START = 1762770000


def update(account, number, *, update_id=11, when=START, text="BTCUSDT",
           bot=False, chat_type="private", chat=None):
    return {"update_id": update_id, "message": {
        "from": {"id": account, "is_bot": bot},
        "chat": {"id": account if chat is None else chat, "type": chat_type},
        "date": when, "message_id": number, "text": text}}


class InboundForensicTests(unittest.TestCase):
    def check(self, payload, reason, *, baseline=10, now=START):
        code, role, message_id = classify_inbound(
            payload, baseline=baseline, accounts=ACCOUNTS,
            started_at=START, observed_at=now, seen={})
        self.assertEqual(code, reason)
        return role, message_id

    def test_two_human_accounts_across_polls_and_nonacknowledging_replay(self):
        d = InboundDiagnostics()
        seen = {}
        first = d.record((update(101, 31),), baseline=10, accounts=ACCOUNTS,
                         started_at=START, observed_at=START, pending=seen)
        second = d.record((update(101, 31), update(202, 42, update_id=12)),
                          baseline=10, accounts=ACCOUNTS, started_at=START,
                          observed_at=START, pending=seen)
        self.assertEqual(first["reason_counts"], {"MATCH_A": 1})
        self.assertEqual(second["reason_counts"], {"DUPLICATE_AUTHORIZED": 1, "MATCH_B": 1})
        self.assertEqual(seen, {"A": 31, "B": 42})
        self.assertEqual(d.summary()["seen"], {"A": True, "B": True})
        self.assertNotIn("101", str(d.summary()))
        self.assertNotIn("202", str(d.summary()))
        self.assertNotIn("31", str(d.summary()))
        self.assertNotIn("42", str(d.summary()))

    def test_case_and_outer_whitespace_for_plain_symbol(self):
        self.assertEqual(self.check(update(101, 1, text=" btcusdt \n"), "MATCH_A"), ("A", 1))
        self.check(update(101, 1, text="/analyze BTCUSDT"), "TEXT_MISMATCH")
        self.check(update(101, 1, text="ETHUSDT"), "TEXT_MISMATCH")

    def test_ready_same_second_inclusive_and_future_rejected(self):
        self.check(update(101, 1, when=START), "MATCH_A")
        self.check(update(101, 1, when=START - 1), "DATE_OUTSIDE_WINDOW")
        self.check(update(101, 1, when=START + 1), "DATE_OUTSIDE_WINDOW")

    def test_only_offline_simulation_may_omit_update_id(self):
        missing = update(101, 1)
        del missing["update_id"]
        self.check(missing, "UPDATE_ID_INVALID")
        self.assertEqual(classify_inbound(missing, baseline=-1, accounts=ACCOUNTS,
                         started_at=START, observed_at=START, seen={},
                         simulation=True), ("MATCH_A", "A", 1))

    def test_update_id_baseline_replay_invalid_and_not_acknowledged(self):
        self.check(update(101, 1, update_id=10), "BELOW_BASELINE")
        self.check(update(101, 1, update_id=9), "BELOW_BASELINE")
        item = update(101, 1)
        item["update_id"] = True
        self.check(item, "UPDATE_ID_INVALID")
        self.check({"message": {}}, "UPDATE_ID_INVALID")

    def test_allowlist_and_cross_account_fails_closed(self):
        self.check(update(303, 1), "UNAUTHORIZED_ACCOUNT")
        self.check(update(101, 1, chat=202), "CHAT_USER_MISMATCH")
        self.check(update(101, 1, bot=True), "BOT_SENDER")
        self.check(update(101, 1, chat_type="group"), "NON_PRIVATE_CHAT")

    def test_missing_inbound_fields_and_malformed_nontext(self):
        self.check({"update_id": 11}, "NO_MESSAGE")
        self.check({"update_id": 11, "message": {"from": {}}}, "MALFORMED_SENDER_CHAT")
        p = update(101, 1)
        p["message"]["text"] = None
        self.check(p, "TEXT_MISMATCH")
        p = update(101, 1)
        p["message"]["date"] = True
        self.check(p, "DATE_OUTSIDE_WINDOW")
        p = update(101, 1)
        p["message"]["message_id"] = None
        self.check(p, "MISSING_MESSAGE_ID")

    def test_empty_and_full_batch_diagnostics_without_private_payload(self):
        d = InboundDiagnostics()
        seen = {}
        d.record([], baseline=10, accounts=ACCOUNTS,
                 started_at=START, observed_at=START, pending=seen)
        # Full 20-update backlog below baseline; orchestrator must STOP
        # rather than call getUpdates with an acknowledging higher offset.
        full = [update(303, n, update_id=n) for n in range(1, 21)]
        d.record(full, baseline=30, accounts=ACCOUNTS,
                 started_at=START, observed_at=START, pending=seen)
        self.assertEqual(d.summary()["polls"][0]["reason_counts"], {"EMPTY_BATCH": 1})
        self.assertEqual(d.summary()["polls"][1]["batch_count"], 20)
        self.assertEqual(d.summary()["reason_totals"]["BELOW_BASELINE"], 20)
        self.assertEqual(seen, {})

    def test_unrelated_payload_never_exposed_in_diagnostics(self):
        d = InboundDiagnostics()
        rows = [update(909000, 432, text="PRIVATE_UNRELATED_SENSITIVE_TEXT")]
        d.record(rows, baseline=0, accounts=ACCOUNTS,
                 started_at=START, observed_at=START, pending={})
        safe = str(d.summary())
        self.assertEqual(d.summary()["reason_totals"], {"UNAUTHORIZED_ACCOUNT": 1})
        self.assertNotIn("909000", safe)
        self.assertNotIn("432", safe)
        self.assertNotIn("PRIVATE_UNRELATED_SENSITIVE_TEXT", safe)


if __name__ == "__main__":
    unittest.main()
