"""Bounded 05C TEST ONLY orchestration over actual private Telegram updates."""
from datetime import datetime, timezone

from .stage05_contracts import ContractError, canonical, digest
from .stage05_custody import LocalOutbox, VerifiedUpstream
from .stage05_interactive import InteractiveService, respond_once
from .stage05_telegram_http import TelegramHTTP, require_live_permission


def bounded_interactive(*, config, transport, store, upstream, source_ref, started_at,
                        session_id, flags=None, permit=None, head_sha=None,
                        clock=None, simulation=False):
    """One poll and at most two replies. No update acknowledgement or replay."""
    config.validate()
    if type(store) is not LocalOutbox or type(upstream) is not VerifiedUpstream:
        raise ContractError("LOCAL_VERIFIED_CUSTODY_REQUIRED")
    if type(started_at) is not int or started_at <= 0:
        raise ContractError("SESSION_START_REQUIRED")
    if not simulation:
        if transport is not None:
            raise ContractError("LIVE_TRANSPORT_INJECTION_FORBIDDEN")
        transport = TelegramHTTP(config.interactive_token)
        for action in ("INTERACTIVE_POLL", "INTERACTIVE_REPLY"):
            require_live_permission(flags=flags, permit=permit, head_sha=head_sha, action=action)
    clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
    now = int(clock().timestamp())
    if not 0 <= now-started_at <= 180:
        raise ContractError("INTERACTIVE_SESSION_EXPIRED")
    snapshot = upstream.snapshot(*source_ref, "BTCUSDT") if source_ref else None
    if not store.create_if_absent("interactive-session/" + digest(canonical(session_id)),
                                  canonical({"started_at": started_at, "head_sha": head_sha})):
        raise ContractError("INTERACTIVE_SESSION_ALREADY_CONSUMED")
    reply_service = InteractiveService(config=config, supported_symbols=["BTCUSDT"],
                                       lookup=lambda _: snapshot, clock=clock)
    opts = dict(flags=flags, permit=permit, head_sha=head_sha)
    for check in (transport.verify_interactive_identity, transport.verify_no_webhook):
        if check(**opts).status != "ACCEPTED":
            return {"status": "INTERACTIVE_IDENTITY_OR_WEBHOOK_BLOCKED", "replies": {}}
    updates = transport.get_updates(offset=0, **opts)
    if updates.status != "ACCEPTED" or len(updates.updates) > 20:
        return {"status": "INTERACTIVE_POLL_FAILED_OR_UNKNOWN", "replies": {}}
    pair = {"A": config.signals_chat_a, "B": config.signals_chat_b}
    pending = {}
    for update in updates.updates:
        msg = update.get("message") if isinstance(update, dict) else None
        if not isinstance(msg, dict):
            continue
        sender, chat = msg.get("from"), msg.get("chat")
        if not isinstance(sender, dict) or not isinstance(chat, dict):
            continue
        uid, cid = sender.get("id"), chat.get("id")
        if (type(uid) is not int or type(cid) is not int or uid != cid
                or sender.get("is_bot") is not False or chat.get("type") != "private"
                or msg.get("text") != "BTCUSDT" or type(msg.get("date")) is not int
                or not started_at <= msg["date"] <= int(clock().timestamp())
                or type(msg.get("message_id")) is not int or msg["message_id"] <= 0):
            continue
        for role, account in pair.items():
            if str(uid) == account:
                pending.setdefault(role, msg["message_id"])
    if set(pending) != set(pair):
        return {"status": "TWO_HUMAN_REQUESTS_NOT_OBSERVED", "replies": {}}
    results = {}
    for role, account in pair.items():
        if not 0 <= int(clock().timestamp())-started_at <= 180:
            return {"status": "INTERACTIVE_SESSION_EXPIRED", "replies": results}
        request = reply_service.accept(text="BTCUSDT", user_id=account, chat_id=account,
                                       message_id=pending[role])
        if request["status"] != "QUEUED":
            raise ContractError("INTERACTIVE_REQUEST_NOT_QUEUED")
        answer = reply_service.process_one()
        answer["reply_text"] = "ZS 05C TEST ONLY / NOT A TRADING SIGNAL\n" + reply_service.format_reply(answer)
        result = respond_once(response=answer, chat_id=account, user_id=account, config=config,
                              store=store, transport=transport, clock=clock, simulation=simulation,
                              reply_to=pending[role], **opts)
        results[role] = {k: result[k] for k in ("status", "telegram_message_date_at") if k in result}
        if result.get("replayed"):
            return {"status": "INTERACTIVE_PRIOR_REPLY_NO_NEW_SEND", "replies": results}
        if result["status"] != "ACCEPTED":
            return {"status": "INTERACTIVE_PARTIAL_STOP", "replies": results}
    return {"status": "TWO_API_ACCEPTED_REPLIES", "replies": results}
