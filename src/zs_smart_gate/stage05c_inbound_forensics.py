"""05C inbound matching and privacy-safe diagnostics. Pure offline logic.

No external I/O; never retains account identifiers, unrelated message text,
update payloads or Telegram message IDs in diagnostic output.
"""
from collections import Counter

# Exactly one terminal reason per nonempty Telegram update.
REASONS = frozenset({
    "UPDATE_ID_INVALID", "BELOW_BASELINE", "NO_MESSAGE",
    "MALFORMED_SENDER_CHAT", "INVALID_IDS", "BOT_SENDER",
    "NON_PRIVATE_CHAT", "CHAT_USER_MISMATCH", "UNAUTHORIZED_ACCOUNT",
    "TEXT_MISMATCH", "DATE_OUTSIDE_WINDOW", "MISSING_MESSAGE_ID",
    "DUPLICATE_AUTHORIZED", "MATCH_A", "MATCH_B",
})


def classify_inbound(update, *, baseline, accounts, started_at, observed_at, seen,
                     simulation=False):
    """Return (safe reason code, authorized role, reply-to message id).

    The only accepted payload is a private human text BTCUSDT from one of the
    two distinct owner-approved accounts, with a fresh strictly positive
    Telegram message ID. Case and outer whitespace are insignificant.
    The exact bot-command form /analyze is NOT expanded here.

    `seen` is role->message_id for this in-memory one-shot; no extra logging.
    """
    if not isinstance(update, dict):
        return "UPDATE_ID_INVALID", None, None
    update_id = update.get("update_id")
    if type(update_id) is not int:
        # Preserve older accepted synthetic fixtures that omit update_id.
        # The real listener never enables simulation.
        if not (simulation and update_id is None):
            return "UPDATE_ID_INVALID", None, None
    elif update_id <= baseline:
        return "BELOW_BASELINE", None, None
    msg = update.get("message")
    if not isinstance(msg, dict):
        return "NO_MESSAGE", None, None
    sender, chat = msg.get("from"), msg.get("chat")
    if not isinstance(sender, dict) or not isinstance(chat, dict):
        return "MALFORMED_SENDER_CHAT", None, None
    uid, cid = sender.get("id"), chat.get("id")
    if type(uid) is not int or type(cid) is not int or uid <= 0 or cid <= 0:
        return "INVALID_IDS", None, None
    if sender.get("is_bot") is not False:
        return "BOT_SENDER", None, None
    if chat.get("type") != "private":
        return "NON_PRIVATE_CHAT", None, None
    if uid != cid:
        return "CHAT_USER_MISMATCH", None, None
    # Membership uses only the externally validated, exact A/B allowlist.
    role = next((key for key, val in accounts.items() if str(uid) == val), None)
    if role is None:
        return "UNAUTHORIZED_ACCOUNT", None, None
    text = msg.get("text")
    if not isinstance(text, str) or text.strip().upper() != "BTCUSDT":
        return "TEXT_MISMATCH", None, None
    date = msg.get("date")
    if type(date) is not int or not started_at <= date <= observed_at:
        return "DATE_OUTSIDE_WINDOW", None, None
    message_id = msg.get("message_id")
    if type(message_id) is not int or message_id <= 0:
        return "MISSING_MESSAGE_ID", None, None
    if role in seen:
        return "DUPLICATE_AUTHORIZED", None, None
    return "MATCH_" + role, role, message_id


class InboundDiagnostics:
    """Aggregate only; no raw Telegram payload, account IDs or message IDs."""

    def __init__(self):
        self._totals = Counter()
        self._polls = []
        self.seen = {"A": False, "B": False}

    def record(self, updates, *, baseline, accounts, started_at, observed_at, pending,
               simulation=False):
        updates = tuple(updates)
        reasons = Counter()
        if not updates:
            reasons["EMPTY_BATCH"] = 1
        for update in updates:
            code, role, message_id = classify_inbound(
                update, baseline=baseline, accounts=accounts,
                started_at=started_at, observed_at=observed_at, seen=pending,
                simulation=simulation)
            reasons[code] += 1
            if role is not None:
                pending[role] = message_id
                self.seen[role] = True
        self._totals.update(reasons)
        poll = {"batch_count": len(updates), "reason_counts": dict(sorted(reasons.items()))}
        self._polls.append(poll)
        return poll

    def summary(self):
        return {"poll_count": len(self._polls),
                "polls": [dict(x) for x in self._polls],
                "reason_totals": dict(sorted(self._totals.items())),
                "seen": dict(self.seen),
                "privacy": "COUNTS_AND_ROLE_BOOLEANS_ONLY"}
