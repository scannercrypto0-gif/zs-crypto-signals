"""Real Telegram Bot API HTTP adapter, inert unless owner/runtime gates pass.

Stdlib HTTPS POST, bounded responses, explicit 429, ambiguous 5xx/network.
No automatic polling, background worker, retries on uncertain delivery, or
credential logging. Fake opener is used only for explicitly offline tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
import re
import secrets
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from .stage05_contracts import ContractError, parse_utc

BASE_URL = "https://api.telegram.org/bot"
MAX_RESPONSE_BYTES = 65536
MAX_JSON_BYTES = 4096
TIMEOUT_S = 6
MAX_RETRY_AFTER_S = 60
ID = re.compile(r"-?[0-9]{1,20}\Z")
TOKEN = re.compile(r"[0-9]{5,15}:[A-Za-z0-9_-]{20,80}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")


@dataclass(frozen=True)
class RuntimeFlags:
    send: bool = False
    signals: bool = False
    analytics: bool = False
    interactive_poll: bool = False
    interactive_reply: bool = False

    @classmethod
    def from_environ(cls, env=None):
        e = os.environ if env is None else env
        def enabled(name):
            return e.get(name, "false").lower() == "true"
        return cls(enabled("ZS_TELEGRAM_SEND_ENABLED"),
                   enabled("ZS_SIGNALS_DISPATCH_ENABLED"),
                   enabled("ZS_ANALYTICS_DISPATCH_ENABLED"),
                   enabled("ZS_INTERACTIVE_POLLING_ENABLED"),
                   enabled("ZS_INTERACTIVE_REPLY_ENABLED"))


@dataclass(frozen=True, repr=False)
class BotSecrets:
    signals_token: str = field(repr=False)
    signals_chat_a: str
    signals_chat_b: str
    interactive_token: str = field(repr=False)
    interactive_users: frozenset[str]
    interactive_chats: frozenset[str]
    analytics_token: str = field(repr=False)
    analytics_chat: str

    def __repr__(self):
        return "<BotSecrets REDACTED>"

    @classmethod
    def from_environ(cls, env=None):
        e = os.environ if env is None else env
        def ids(name):
            raw = e.get(name, "")
            return frozenset(x.strip() for x in raw.split(",") if x.strip())
        cfg = cls(
            e.get("ZS_SIGNALS_BOT_TOKEN", ""),
            e.get("ZS_SIGNALS_CHAT_ID_A", ""),
            e.get("ZS_SIGNALS_CHAT_ID_B", ""),
            e.get("ZS_INTERACTIVE_BOT_TOKEN", ""),
            ids("ZS_INTERACTIVE_ALLOWED_USER_IDS"),
            ids("ZS_INTERACTIVE_ALLOWED_CHAT_IDS"),
            e.get("ZS_ANALYTICS_BOT_TOKEN", ""),
            e.get("ZS_ANALYTICS_CHAT_ID", ""),
        )
        cfg.validate()
        return cfg

    def validate(self):
        if (not all(TOKEN.fullmatch(x or "") for x in (
            self.signals_token, self.analytics_token, self.interactive_token))
            or len({self.signals_token, self.analytics_token,
                    self.interactive_token}) != 3):
            raise ContractError("THREE_DISTINCT_BOT_TOKENS_REQUIRED")
        # Owner's two-account contract: Signals A/B differ; archive C is A.
        # These are per-bot destinations, not three distinct Telegram users.
        chats = (self.signals_chat_a, self.signals_chat_b, self.analytics_chat)
        if not all(ID.fullmatch(x or "") for x in chats):
            raise ContractError("DELIVERY_CHAT_ID_INVALID")
        if self.signals_chat_a == self.signals_chat_b:
            raise ContractError("SIGNALS_A_B_MUST_DIFFER")
        if self.analytics_chat != self.signals_chat_a:
            raise ContractError("ANALYTICS_C_MUST_EQUAL_SIGNALS_A")
        # 05C uses the same two private accounts; fail closed on missing,
        # partial, extra or malformed authorization values.
        accounts = frozenset((self.signals_chat_a, self.signals_chat_b))
        if self.interactive_users != accounts or self.interactive_chats != accounts:
            raise ContractError("INTERACTIVE_TWO_ACCOUNT_ALLOWLIST_REQUIRED")
        if any(not ID.fullmatch(x) for x in
               self.interactive_users | self.interactive_chats):
            raise ContractError("INTERACTIVE_ALLOWLIST_INVALID")


@dataclass(frozen=True)
class OwnerPermit:
    """External authorization reference, NOT a cryptographic signature.

    The separately approved runtime must verify this reference independently.
    Its mere presence cannot replace approval and readiness.
    """
    decision_ref: str
    approved_head_sha: str
    expires_at: str
    authorized_actions: frozenset[str]
    runtime_ready: bool = False
    independently_verified: bool = False


def require_live_permission(*, flags, permit, head_sha, action):
    if not isinstance(flags, RuntimeFlags):
        raise ContractError("ACTIVATION_SWITCHES_REQUIRED")
    if (not isinstance(permit, OwnerPermit)
            or not permit.runtime_ready
            or not permit.independently_verified
            or not permit.decision_ref.startswith("OWNER-APPROVED-")
            or not SHA.fullmatch(permit.approved_head_sha)
            or permit.approved_head_sha != head_sha
            or action not in permit.authorized_actions):
        raise ContractError("OWNER_ACTIVATION_AND_RUNTIME_READINESS_REQUIRED")
    # No more than a permission *reference*: human authorization still binding.
    if parse_utc(permit.expires_at, "PERMIT_EXPIRY") <= datetime.now(timezone.utc):
        raise ContractError("OWNER_PERMIT_EXPIRED")
    if action == "SIGNALS" and not (flags.send and flags.signals):
        raise ContractError("SIGNALS_DISPATCH_DISABLED")
    if action == "ANALYTICS" and not (flags.send and flags.analytics):
        raise ContractError("ANALYTICS_DISPATCH_DISABLED")
    if action == "INTERACTIVE_REPLY" and not (flags.send and flags.interactive_reply):
        raise ContractError("INTERACTIVE_REPLY_DISABLED")
    if action == "INTERACTIVE_POLL" and not flags.interactive_poll:
        raise ContractError("INTERACTIVE_POLLING_DISABLED")
    if action not in ("SIGNALS", "ANALYTICS", "INTERACTIVE_REPLY", "INTERACTIVE_POLL"):
        raise ContractError("UNKNOWN_ACTIVATION_ACTION")


@dataclass(frozen=True)
class ApiResult:
    status: str
    message_id: int | None = None
    message_date_at: str | None = None
    retry_after_s: int | None = None
    updates: tuple = ()


class TelegramHTTP:
    """Real HTTP; test_opener never called unless explicitly passed by tests.

    The real branch ALWAYS checks the separate owner permit and all switches.
    No request is made on construction. Every exception returned is sanitized.
    """

    def __init__(self, token, *, test_opener=None, timeout=TIMEOUT_S):
        if not isinstance(token, str) or not TOKEN.fullmatch(token):
            raise ContractError("BOT_TOKEN_FORMAT_INVALID")
        if not isinstance(timeout, (int, float)) or timeout < 1 or timeout > 12:
            raise ContractError("TELEGRAM_TIMEOUT_OUT_OF_RANGE")
        self._token = token
        self._test_opener = test_opener
        self._timeout = timeout

    def __repr__(self):
        return "<TelegramHTTP REDACTED>"

    def _call(self, method, payload, *, flags=None, permit=None,
              head_sha=None, action=None, document=None):
        if method not in ("sendMessage", "sendDocument", "getUpdates"):
            raise ContractError("TELEGRAM_METHOD_NOT_ALLOWED")
        if self._test_opener is None:
            require_live_permission(flags=flags, permit=permit,
                                    head_sha=head_sha, action=action)
        if method == "getUpdates":
            if action != "INTERACTIVE_POLL":
                raise ContractError("POLLING_ACTION_MISMATCH")
            if (payload.get("timeout") != 0 or payload.get("limit", 0) > 20
                    or payload.get("allowed_updates") != ["message"]):
                raise ContractError("BOUNDED_POLLING_REQUIRED")
        else:
            if action not in ("SIGNALS", "ANALYTICS", "INTERACTIVE_REPLY"):
                raise ContractError("SEND_ACTION_REQUIRED")
            if not ID.fullmatch(str(payload.get("chat_id", ""))):
                raise ContractError("CHAT_DESTINATION_INVALID")
        url = BASE_URL + self._token + "/" + method
        if document is None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            if len(data) > MAX_JSON_BYTES:
                raise ContractError("TELEGRAM_MESSAGE_TOO_LARGE")
            content_type = "application/json"
        else:
            filename, contents = document
            if (method != "sendDocument" or not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", filename)
                    or not isinstance(contents, bytes)
                    or len(contents) > 256 * 1024):
                raise ContractError("DOCUMENT_CONTRACT_INVALID")
            boundary = "ZS05" + secrets.token_hex(18).upper()
            fields = "".join(
                "--" + boundary + "\r\nContent-Disposition: form-data; name=\"" +
                str(k) + "\"\r\n\r\n" + str(v) + "\r\n"
                for k, v in payload.items()
            ).encode("utf-8")
            data = (fields + ("--" + boundary + "\r\nContent-Disposition: form-data; name=\"document\"; filename=\"" +
                               filename + "\"\r\nContent-Type: application/json\r\n\r\n").encode("utf-8")
                    + contents + ("\r\n--" + boundary + "--\r\n").encode("ascii"))
            content_type = "multipart/form-data; boundary=" + boundary
        request = Request(url, data=data, headers={
            "Content-Type": content_type, "User-Agent": "zs-stage05-disabled-by-default",
        }, method="POST")
        opener = urlopen if self._test_opener is None else self._test_opener
        try:
            with opener(request, timeout=self._timeout) as response:
                status = response.status
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                headers = response.headers
        except HTTPError as e:
            status = e.code
            raw = e.read(MAX_RESPONSE_BYTES + 1)
            headers = e.headers
        except (URLError, TimeoutError, OSError, ConnectionError):
            return ApiResult("UNKNOWN_DELIVERY")
        if len(raw) > MAX_RESPONSE_BYTES:
            return ApiResult("UNKNOWN_DELIVERY")
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            return ApiResult("UNKNOWN_DELIVERY")
        if not isinstance(data, dict):
            return ApiResult("UNKNOWN_DELIVERY")
        if status == 429:
            retry = None
            params = data.get("parameters")
            if isinstance(params, dict):
                retry = params.get("retry_after")
            if retry is None:
                retry = headers.get("Retry-After", "1") if headers else "1"
            try:
                retry = max(1, min(MAX_RETRY_AFTER_S, int(retry)))
            except (ValueError, TypeError, OverflowError):
                retry = MAX_RETRY_AFTER_S
            return ApiResult("RATE_LIMITED", retry_after_s=retry)
        if status >= 500:
            return ApiResult("UNKNOWN_DELIVERY")
        if status != 200 or data.get("ok") is not True:
            return ApiResult("PERMANENT_FAILURE")
        result = data.get("result")
        if method == "getUpdates":
            if not isinstance(result, list) or len(result) > 20:
                return ApiResult("UNKNOWN_DELIVERY")
            return ApiResult("ACCEPTED", updates=tuple(result))
        if (not isinstance(result, dict)
                or not isinstance(result.get("message_id"), int)
                or isinstance(result["message_id"], bool)
                or not isinstance(result.get("date"), int)):
            return ApiResult("UNKNOWN_DELIVERY")
        # Telegram server provides seconds, not fabricated milliseconds.
        server_time = datetime.fromtimestamp(result["date"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return ApiResult("ACCEPTED", result["message_id"], server_time)

    def send_text(self, chat_id, text, *, flags=None, permit=None, head_sha=None,
                  action="SIGNALS"):
        if not isinstance(text, str) or not text or len(text) > 3900:
            raise ContractError("SIGNAL_MESSAGE_TEXT_INVALID")
        return self._call("sendMessage", {"chat_id": chat_id, "text": text,
                         "disable_web_page_preview": True},
                          flags=flags, permit=permit, head_sha=head_sha, action=action)

    def send_document(self, chat_id, caption, filename, content, *,
                      flags=None, permit=None, head_sha=None, action="ANALYTICS"):
        if not isinstance(caption, str) or len(caption.encode("utf-8")) > 1024:
            raise ContractError("DOCUMENT_CAPTION_INVALID")
        return self._call("sendDocument", {"chat_id": chat_id, "caption": caption},
                          flags=flags, permit=permit, head_sha=head_sha,
                          action=action, document=(filename, content))

    def get_updates(self, *, offset=0, flags=None, permit=None, head_sha=None):
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ContractError("INVALID_POLL_OFFSET")
        return self._call("getUpdates", {
            "offset": offset, "limit": 20, "timeout": 0,
            "allowed_updates": ["message"],
        }, flags=flags, permit=permit, head_sha=head_sha,
        action="INTERACTIVE_POLL")
