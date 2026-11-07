"""Stage05A/B/C isolated integration contract: OFFLINE, DISABLED, SYNTHETIC ONLY.

No Telegram libraries, no network transport, no secrets, no live signal issuance.
Input: explicit synthetic DETECTED_SIGNAL fixture or real ResearchEvent (blocked).
Output: two mock Primary receipts and one independent mock Analytics receipt.
Receipts are memory-only, not a claim of durable GitHub/Telegram readback.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import re
from typing import Protocol

from .core import decimal, utc
from .stage03a_contracts import Direction, EventIdentity, Horizon, ResearchEvent

SCHEMA = "ZS05_OFFLINE_THREE_DESTINATIONS_V1"
MAX_MOCK_ATTEMPTS_PER_DESTINATION = 3
ANALYTICS_SCHEMA = "ZS05_ANALYTICS_SIMULATED_V1"
RECEIPT_SCHEMA = "ZS05_MOCK_RECEIPT_V1"
DESTINATIONS = ("PRIMARY_CHAT_A", "PRIMARY_CHAT_B", "ANALYTICS_CHAT_C")
_ALLOWED_COMMANDS = ("status", "intraday", "swing")
_SIM_ID = re.compile(r"^ZS05-SIM-[a-f0-9]{32}$")
_SYMBOL = re.compile(r"^[A-Z0-9]{2,40}USDT$")


def canonical(obj: object) -> bytes:
    return (json.dumps(obj, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


@dataclass(frozen=True)
class SyntheticDetectedSignal:
    """Offline target interface, NOT a Stage03-qualified or live signal.

    A Stage03A research candidate must never be passed as this type or
    automatically promoted. Source IDs are intentionally non-live.
    """
    identity: EventIdentity
    decision_at: datetime
    source_id: str
    source_ref: str
    evidence_quality: str
    reason_codes: tuple[str, ...]
    score: str | None
    score_version: str
    plan_status: str = "RESEARCH_ONLY"
    plan_reason: str = "SPOT_ENTRY_LEVELS_NOT_SCIENTIFICALLY_VALIDATED"
    simulation_state: str = "SIMULATED_DETECTED_SIGNAL_NOT_QUALIFIED"

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_at", utc(self.decision_at))
        if (self.simulation_state != "SIMULATED_DETECTED_SIGNAL_NOT_QUALIFIED"
                or self.identity.signal_id is not None):
            raise ValueError("SYNTHETIC_ONLY_LIFECYCLE_GUARD")
        if not isinstance(self.identity, EventIdentity):
            raise ValueError("TYPED_STAGE03_EVENT_IDENTITY_REQUIRED")
        if self.decision_at < self.identity.decision_candle_close_at:
            raise ValueError("FUTURE_DECISION_OR_UNCLOSED_PARENT")
        if (not isinstance(self.source_id, str) or
                not self.source_id.startswith("SYNTHETIC:") or
                not isinstance(self.source_ref, str) or
                not self.source_ref.startswith("SYNTHETIC:")):
            raise ValueError("OFFLINE_SYNTHETIC_SOURCE_REQUIRED")
        if (not re.fullmatch(r"SYNTHETIC:[A-Z0-9_]{1,80}",self.source_id) or
                not re.fullmatch(r"SYNTHETIC:[A-Z0-9_]{1,80}",self.source_ref) or
                any(not re.fullmatch(r"[A-Z0-9_]{1,80}",part)
                    for part in (self.identity.setup_type,
                                 self.identity.rule_version,
                                 self.identity.event_discriminator))):
            raise ValueError("UNSAFE_SYNTHETIC_FIXTURE_METADATA")
        if (self.evidence_quality != "SYNTHETIC_PIT_UNVERIFIED" or
                not isinstance(self.reason_codes, tuple) or
                not self.reason_codes or
                not all(isinstance(x, str) and x and len(x) <= 100
                        and re.fullmatch("[A-Z0-9_]+", x) for x in self.reason_codes)):
            raise ValueError("EXPLICIT_SYNTHETIC_QUALITY_AND_REASONS_REQUIRED")
        if self.plan_status != "RESEARCH_ONLY" or self.plan_reason != "SPOT_ENTRY_LEVELS_NOT_SCIENTIFICALLY_VALIDATED":
            raise ValueError("UNVALIDATED_TRADE_PLAN_REJECTED")
        if self.score is None:
            if self.score_version != "SCORE_UNAVAILABLE":
                raise ValueError("SCORE_MISSINGNESS_MUST_BE_TYPED")
        else:
            n = decimal(self.score)
            if n < 0 or n > 100 or self.score_version != "SYNTHETIC_SCORE_FOR_FORMATTER_ONLY":
                raise ValueError("UNVALIDATED_SCORE_VERSION_OR_RANGE")
            object.__setattr__(self, "score", format(n, "f"))

    @property
    def signal_id(self) -> str:
        return "ZS05-SIM-" + sha256(self.identity.detection_event_key.encode("ascii"))[:32]

    def snapshot(self) -> dict:
        return {
            "schema": SCHEMA,
            "signal_id": self.signal_id,
            "simulated": True,
            "simulation_state": self.simulation_state,
            "source": {"source_id": self.source_id, "reference": self.source_ref,
                       "quality": self.evidence_quality,
                       "publisher_time": None, "live_pit_verified": False},
            "identity": self.identity.as_dict(),
            "symbol": self.identity.asset_id.removeprefix("BINANCE:SPOT:"),
            "direction": self.identity.direction.value,
            "horizon": self.identity.horizon.value,
            "setup_type": self.identity.setup_type,
            "decision_at": self.decision_at.isoformat(),
            "decision_close_at": self.identity.decision_candle_close_at.isoformat(),
            "reason_codes": list(self.reason_codes),
            "score": self.score,
            "score_status": ("SCORE_UNAVAILABLE" if self.score is None else
                             "SYNTHETIC_DISPLAY_SCORE_ONLY"),
            "score_version": self.score_version,
            "probability": None,
            "trade_plan": {
                "status": "RESEARCH_ONLY", "reason": self.plan_reason,
                "entry": None, "stop_loss": None, "tp1": None, "tp2": None,
                "tp3": None, "trade_ready": False, "auto_execution": False,
            },
            "qualified_live_signal": False,
            "external_delivery_authorized": False,
        }


def _primary_text(snapshot: dict) -> str:
    score = snapshot["score"] if snapshot["score"] is not None else "SCORE_UNAVAILABLE"
    return "\n".join((
        "SMART GATE | SYNTHETIC / OFFLINE / NOT LIVE",
        "Signal ID: " + snapshot["signal_id"],
        "Asset: " + snapshot["symbol"],
        "Direction: " + snapshot["direction"] +
            (" (bearish observation; NO SHORT)" if snapshot["direction"] == "DOWN" else ""),
        "Horizon: " + snapshot["horizon"],
        "Setup: " + snapshot["setup_type"],
        "Decision UTC: " + snapshot["decision_at"],
        "Score: " + score + " [" + snapshot["score_version"] + "]",
        "TradePlan: RESEARCH_ONLY / " + snapshot["trade_plan"]["reason"],
        "Evidence: " + snapshot["source"]["quality"],
        "Reasons: " + ", ".join(snapshot["reason_codes"]),
        "NO REAL TELEGRAM / NO TRADE / NO PREDICTIVE CERTIFICATION",
    ))


def _analytics(snapshot: dict, digest: str) -> tuple[str, dict]:
    payload = {
        "schema": ANALYTICS_SCHEMA,
        "signal_id": snapshot["signal_id"],
        "source_snapshot_sha256": digest,
        "source_ref": snapshot["source"]["reference"],
        "source_quality": snapshot["source"]["quality"],
        "research_only": True,
        "synthetic": True,
        "decision": {
            "status": snapshot["simulation_state"],
            "reason_codes": snapshot["reason_codes"],
            "score": snapshot["score"], "score_status": snapshot["score_status"],
            "score_version": snapshot["score_version"],
            "plan": snapshot["trade_plan"],
            "identity": snapshot["identity"],
        },
    }
    desc = "\n".join((
        "SMART GATE | MOCK ANALYTICS / NOT LIVE",
        "Signal ID: " + snapshot["signal_id"],
        "Decision: " + snapshot["simulation_state"],
        "Evidence quality: " + snapshot["source"]["quality"],
        "Snapshot SHA256: " + digest,
        "Research-only JSON schema: " + ANALYTICS_SCHEMA,
    ))
    return desc,payload


@dataclass(frozen=True)
class Envelope:
    signal_id: str
    destination: str
    message_kind: str
    human: str
    json_payload: dict | None
    snapshot_sha256: str
    payload_sha256: str
    json_sha256: str | None
    idempotency_key: str

    @classmethod
    def build(cls, snapshot: dict, destination: str) -> "Envelope":
        if destination not in DESTINATIONS:
            raise ValueError("UNKNOWN_OFFLINE_DESTINATION")
        snapshot_sha = sha256(canonical(snapshot))
        if destination in DESTINATIONS[:2]:
            kind = "PRIMARY_HUMAN"
            human,payload = _primary_text(snapshot),None
        else:
            kind = "ANALYTICS_JSON"
            human,payload = _analytics(snapshot,snapshot_sha)
        descriptor = {"kind":kind,"human":human,"json":payload}
        key = snapshot["signal_id"] + ":" + destination + ":" + kind
        return cls(snapshot["signal_id"],destination,kind,human,payload,
                   snapshot_sha,sha256(canonical(descriptor)),
                   sha256(canonical(payload)) if payload is not None else None,key)


@dataclass(frozen=True)
class MockReceipt:
    signal_id: str
    destination: str
    idempotency_key: str
    snapshot_sha256: str
    payload_sha256: str
    attempts: int
    status: str
    reason: str
    schema: str = RECEIPT_SCHEMA
    external_message_id: None = None
    external_sent: bool = False
    durable_readback: bool = False

    def as_dict(self) -> dict:
        return dict(vars(self))


class ReceiptStore(Protocol):
    """Replaceable local mock interface; NOT a persistent database."""
    snapshots: dict[str, bytes]
    receipts: dict[str, MockReceipt]


class MemoryReceiptStore:
    def __init__(self):
        self.snapshots: dict[str, bytes] = {}
        self.receipts: dict[str, MockReceipt] = {}


class DisabledMockTransport:
    """No configurable URL/token, socket, Telegram, or live adapter."""
    def __init__(self, failures: dict[str,int] | None = None):
        self.failures=dict(failures or {})
        if set(self.failures)-set(DESTINATIONS):
            raise ValueError("UNKNOWN_MOCK_FAILURE_DESTINATION")
        if any(type(n) is not int or n < 0 for n in self.failures.values()):
            raise ValueError("INVALID_MOCK_FAILURE_PLAN")
        self.mock_attempts: list[str] = []
        self.external_sends = 0
        self.market_calls = 0

    def attempt(self, envelope: Envelope) -> tuple[bool, str]:
        if envelope.destination not in DESTINATIONS:
            raise ValueError("UNKNOWN_MOCK_DESTINATION")
        self.mock_attempts.append(envelope.destination)
        remaining=self.failures.get(envelope.destination,0)
        if remaining:
            self.failures[envelope.destination]=remaining-1
            return False,"INJECTED_MOCK_FAILURE"
        return True,"SIMULATED_ACK_ONLY_NO_EXTERNAL_DELIVERY"


class OfflineThreeDestinationRouter:
    def __init__(self, store: ReceiptStore, transport: DisabledMockTransport):
        if not isinstance(transport, DisabledMockTransport):
            raise PermissionError("DISABLED_MOCK_TRANSPORT_ONLY")
        if not isinstance(store, MemoryReceiptStore):
            raise PermissionError("OFFLINE_MEMORY_STORE_ONLY_IN_001")
        self.store=store
        self.transport=transport

    def route(self, signal: SyntheticDetectedSignal | ResearchEvent) -> dict:
        if isinstance(signal, ResearchEvent):
            raise PermissionError("RESEARCH_CANDIDATE_NOT_DETECTED_SIGNAL")
        if not isinstance(signal,SyntheticDetectedSignal):
            raise PermissionError("ONLY_EXPLICIT_SYNTHETIC_DETECTED_SIGNAL_FIXTURES")
        snapshot=signal.snapshot()
        sid=snapshot["signal_id"]
        raw=canonical(snapshot)
        if sid in self.store.snapshots and self.store.snapshots[sid] != raw:
            raise ValueError("SAME_EVENT_MUTATED_SNAPSHOT_BLOCKED")
        envelopes=[Envelope.build(snapshot,d) for d in DESTINATIONS]
        # Preflight all identity/consistency checks before the FIRST mock attempt.
        if any(e.signal_id != sid or e.snapshot_sha256 != sha256(raw) for e in envelopes):
            raise ValueError("ENVELOPE_IDENTITY_MISMATCH")
        for envelope in envelopes:
            receipt=self.store.receipts.get(envelope.idempotency_key)
            if receipt is not None and (receipt.signal_id != sid or
                receipt.destination != envelope.destination or
                receipt.payload_sha256 != envelope.payload_sha256 or
                receipt.snapshot_sha256 != envelope.snapshot_sha256):
                raise ValueError("RECEIPT_IDEMPOTENCY_CONFLICT_BLOCKED")
        self.store.snapshots.setdefault(sid,raw)
        for envelope in envelopes:
            prev=self.store.receipts.get(envelope.idempotency_key)
            if prev and prev.status in ("MOCK_DELIVERED","MOCK_RETRY_EXHAUSTED"):
                continue
            if prev and prev.attempts >= MAX_MOCK_ATTEMPTS_PER_DESTINATION:
                self.store.receipts[envelope.idempotency_key] = MockReceipt(
                    sid,envelope.destination,envelope.idempotency_key,
                    envelope.snapshot_sha256,envelope.payload_sha256,
                    prev.attempts,"MOCK_RETRY_EXHAUSTED",
                    "MOCK_ATTEMPT_BUDGET_EXHAUSTED_NO_EXTERNAL_RETRY")
                continue
            try:
                ok,reason=self.transport.attempt(envelope)
            except Exception:
                # Never leak an exception body containing untrusted strings.
                ok,reason=False,"MOCK_TRANSPORT_EXCEPTION_REDACTED"
            receipt=MockReceipt(sid,envelope.destination,envelope.idempotency_key,
                                envelope.snapshot_sha256,envelope.payload_sha256,
                                (prev.attempts if prev else 0)+1,
                                "MOCK_DELIVERED" if ok else "MOCK_FAILED",
                                reason)
            self.store.receipts[envelope.idempotency_key]=receipt
        return {
            "schema":SCHEMA,"signal_id":sid,"snapshot_sha256":sha256(raw),
            "mode":"OFFLINE_DISABLED_SIMULATION",
            "receipts":[self.store.receipts[e.idempotency_key].as_dict()
                        for e in envelopes],
            "message_bodies":[{"destination":e.destination,
                                "kind":e.message_kind,
                                "human":e.human,
                                "analytics_json":e.json_payload,
                                "payload_sha256":e.payload_sha256,
                                "analytics_json_sha256":e.json_sha256} for e in envelopes],
            "external_sends":self.transport.external_sends,
            "market_calls":self.transport.market_calls,
            "real_secrets":0, "qualified_live_signal":False,
            "durable_readback":False, "science_pass":False,
        }


class OfflineInteractiveReader:
    """05C: synchronous allowlisted lookup, never computes an event/market data."""
    def __init__(self, store: MemoryReceiptStore, authorized_callers: frozenset[str]):
        if not isinstance(store, MemoryReceiptStore):
            raise PermissionError("OFFLINE_STORE_REQUIRED")
        if (not isinstance(authorized_callers,frozenset) or
            any(not x.startswith("SYNTHETIC:") for x in authorized_callers)):
            raise PermissionError("SYNTHETIC_ALLOWLIST_ONLY")
        self.store=store
        self.authorized_callers=authorized_callers

    def query(self, caller: str, command: str) -> dict:
        if caller not in self.authorized_callers:
            raise PermissionError("05C_UNAUTHORIZED_CALLER")
        if not isinstance(command,str) or len(command)>100 or not command.startswith("/"):
            raise ValueError("05C_INVALID_QUERY")
        parts=command[1:].split(" ")
        if any(not part for part in parts):
            raise ValueError("05C_INVALID_QUERY")
        op=parts[0].lower()
        if op in _ALLOWED_COMMANDS and len(parts)==1:
            value=None if op=="status" else op.upper()
            snapshots=[json.loads(v) for v in self.store.snapshots.values()]
            subset=[s for s in snapshots if value is None or s["horizon"]==value]
        elif op=="signal" and len(parts)==2 and _SIM_ID.fullmatch(parts[1]):
            key=parts[1]
            if key not in self.store.snapshots:
                raise ValueError("05C_SNAPSHOT_NOT_FOUND")
            subset=[json.loads(self.store.snapshots[key])]
        elif op=="analyze" and len(parts)==2 and _SYMBOL.fullmatch(parts[1]):
            subset=[json.loads(v) for v in self.store.snapshots.values()
                    if json.loads(v)["symbol"]==parts[1]]
        else:
            raise ValueError("05C_COMMAND_NOT_AUTHORIZED_OR_NOT_CACHED")
        if not subset:
            raise ValueError("05C_REQUIRED_CACHED_DATA_UNAVAILABLE")
        # Read-only mock query; no new Signal ID, no clock refresh, no mutation.
        return {
            "schema":"ZS05_MOCK_INTERACTIVE_READ_ONLY_V1",
            "status":"OFFLINE_CACHED_SYNTHETIC_SNAPSHOT_ONLY",
            "request_id":"ZS05-QUERY-SIM-"+sha256(canonical([caller,command]))[:20],
            "count":len(subset),
            "snapshots":subset,
            "market_calls":0,"external_sends":0,"new_signal_generated":False,
        }
