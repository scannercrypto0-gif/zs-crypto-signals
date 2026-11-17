"""Default-off readiness seam for isolated destination adapters.

No service clients are constructed here. A future operator must independently
verify permits and bind injected adapters to the approved destinations.
"""
from dataclasses import dataclass
import json

from .stage05_contracts import ContractError, SHA, canonical, digest

ROLES = ("telegram-a", "telegram-b", "telegram-c", "archive", "sql", "outcome")
VERSION = "zs.ops.isolated-effects.v1"


@dataclass
class EffectGate:
    journal: object
    adapters: dict
    verify_permit: object = None
    verify_qualification: object = None

    def step(self, role, signal, permit=None):
        if (self.verify_permit is None or self.verify_qualification is None
                or role not in ROLES or role not in self.adapters or permit is None
                or self.verify_permit(role, permit) is not True):
            return {"status":"BLOCKED_PERMISSION"}
        if (not isinstance(signal, dict) or signal.get("scope") != "APPROVED_REAL_SOURCE"
                or signal.get("trading_authorized") is not False
                or not isinstance(signal.get("signal_id"), str)
                or not signal["signal_id"].startswith("sig-")
                or not SHA.fullmatch(signal["signal_id"][4:])
                or self.verify_qualification(signal) is not True):
            return {"status":"BLOCKED_QUALIFICATION"}
        raw = canonical(signal)
        pin = digest(raw)
        key = digest(canonical([role,signal["signal_id"]]))
        intent = canonical(dict(schema=VERSION, role=role, signal_id=signal["signal_id"], sha256=pin))
        intent_key, ack_key = "effect-intent/"+key, "effect-ack/"+key
        adapter = self.adapters[role]
        previous = self.journal.read(intent_key)
        cached = self.journal.read(ack_key)
        if ((previous is not None and previous != intent)
                or (cached is not None and previous is None)):
            return {"status":"EFFECT_CONTENT_CONFLICT"}
        expected = dict(role=role, signal_id=signal["signal_id"], sha256=pin, state="VERIFIED")
        if cached is not None:
            if cached != canonical(expected):
                raise ContractError("OPS_EFFECT_ACK_CONFLICT")
            return json.loads(cached)
        # After reservation, never automatically repeat an effect: an absent
        # acknowledgement can mean the previous operation actually succeeded.
        won = self.journal.create_if_absent(intent_key,intent)
        if self.journal.read(intent_key) != intent:
            return {"status":"EFFECT_CONTENT_CONFLICT"}
        try:
            receipt = adapter.execute(key, raw) if won else adapter.reconcile(key, pin)
        except (OSError, RuntimeError):
            return {"status":"EFFECT_RECONCILIATION_REQUIRED"}
        if receipt != expected:
            return {"status":"EFFECT_RECONCILIATION_REQUIRED"}
        self.journal.create_if_absent(ack_key,canonical(expected))
        if self.journal.read(ack_key) != canonical(expected):
            raise ContractError("OPS_EFFECT_ACK_CONFLICT")
        return expected
