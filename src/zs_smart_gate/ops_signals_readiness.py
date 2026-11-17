"""Signals-only readiness gates. No external transports or real trust roots."""
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable
from types import SimpleNamespace

from .stage03_qv1_policy import verify_event_bracket
from .stage05_contracts import ContractError, SHA, canonical, digest, parse_utc
from .stage13_operational_harness import CycleController, SCOPE, VERSION as FIXTURE_SCHEMA

VERSION = "zs.ops.signals-readiness.v1"


@dataclass(frozen=True)
class FixtureAuthority:
    """Pins from a separate fixture operator, not from the scanner packet."""
    policy_pin: str
    calibration_pin: str
    signer: str
    verify_signature: Callable[[bytes, str], bool]


def _pin(value, expected):
    return isinstance(expected, str) and SHA.fullmatch(expected) and digest(canonical(value)) == expected


def _microseconds(delta):
    return delta // timedelta(microseconds=1)


def verify_witness(witness, calibration, authority, *, source_pin, policy, available, decision):
    """Verify signed canonical evidence and bound event time using pinned calibration."""
    if not isinstance(witness, dict) or not isinstance(calibration, dict):
        return "UNKNOWN"
    try:
        proof, signature = witness["proof"], witness["signature"]
        if (not _pin(calibration, authority.calibration_pin)
                or calibration["scope"] != SCOPE or calibration["signer"] != authority.signer
                or calibration["revoked"] is not False or proof["signer"] != authority.signer
                or proof["schema"] != VERSION or proof["method"] != "AUTHENTICATED_EVENT_BRACKET_V1"
                or proof["source_sha256"] != source_pin
                or proof["policy_sha256"] != authority.policy_pin
                or proof["calibration_ref"] != authority.calibration_pin
                or proof["monotonic_domain"] != calibration["monotonic_domain"]
                or not isinstance(signature, str)
                or authority.verify_signature(canonical(proof), signature) is not True):
            return "UNKNOWN"
        measured = parse_utc(calibration["measured_at"])
        received = parse_utc(calibration["received_at"])
        ready = parse_utc(calibration["available_at"])
        expiry = parse_utc(calibration["expires_at"])
        uncertainty, drift, offset = (calibration[k] for k in ("uncertainty_us", "drift_ppm", "offset_us"))
        if (any(type(v) is not int for v in (uncertainty, drift, offset))
                or uncertainty < 0 or drift < 0
                or not measured <= received <= ready <= available <= decision < expiry
                or _microseconds(decision - measured) > policy["max_age_us"]):
            return "UNKNOWN"
        for label, event in (("availability", available), ("decision", decision)):
            age = _microseconds(event - measured)
            bound = uncertainty + (age * drift + 999999)//1000000
            if bound >= policy["max_uncertainty_us"]:
                return "UNKNOWN"
            estimate = event + timedelta(microseconds=offset)
            lower, upper = (parse_utc(proof[label][field]) for field in ("utc_lower","utc_upper"))
            # Require the signed bracket to fit inside the admitted calibration envelope.
            if not estimate - timedelta(microseconds=bound) <= lower <= upper <= estimate + timedelta(microseconds=bound):
                return "UNKNOWN"
        limits = SimpleNamespace(max_uncertainty_us=policy["max_uncertainty_us"] - 1)
        return verify_event_bracket(proof, decision, available, limits)
    except (ContractError, KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return "UNKNOWN"


def assess(packet, authority, decision, *, max_age_seconds):
    """Only review fixtures may advance; real qualification registries stay untouched."""
    if not isinstance(packet, dict) or packet.get("scope") != SCOPE:
        return "QUALIFICATION_BLOCKED", "REAL_POLICY_NOT_ADMITTED"
    try:
        row, policy = packet["snapshot"], packet["policy"]
        if (not _pin(row, packet["source_sha256"]) or not _pin(policy, authority.policy_pin)
                or policy["schema"] != VERSION or policy["authority"] != SCOPE
                or policy["revoked"] is not False or row["scope"] != SCOPE
                or row["source_id"] not in policy["source_allowlist"]
                or row["symbol"] not in policy["symbols"] or row["direction"] not in policy["directions"]
                or row["rule"] != policy["rule"]):
            return "QUALIFICATION_BLOCKED", "SOURCE_OR_POLICY_PIN_INVALID"
        for name, ceiling in (("max_age_us", 90000000), ("max_uncertainty_us", 1500000)):
            if type(policy[name]) is not int or not 0 < policy[name] <= ceiling:
                return "QUALIFICATION_BLOCKED", "POLICY_LIMIT_INVALID"
        closed, received, available = (parse_utc(row[key]) for key in
                                       ("closed_at","received_at","available_at"))
        if (row["closed"] is not True or row["coverage"] != "COMPLETE_FIXTURE"
                or not closed <= received <= available <= decision
                or (decision-closed).total_seconds() > max_age_seconds):
            return "QUALIFICATION_BLOCKED", "SOURCE_TIME_OR_COVERAGE_INVALID"
        if verify_witness(packet.get("witness"), packet.get("calibration"), authority,
                          source_pin=packet["source_sha256"], policy=policy,
                          available=available, decision=decision) != "PASS":
            return "QUALIFICATION_BLOCKED", "UTC_WITNESS_UNKNOWN"
        if row.get("context_complete") is not True or row.get("liquidity_verified") is not True:
            return "QUALIFICATION_BLOCKED", "CONTEXT_OR_LIQUIDITY_MISSING"
        if row.get("setup_trigger") is False:
            return "NO_TRIGGER", None
        if row.get("setup_trigger") is not True:
            return "QUALIFICATION_BLOCKED", "SETUP_UNDETERMINED"
        return "FIXTURE_QUALIFIED", None
    except (ContractError, AttributeError, TypeError, KeyError, ValueError, OverflowError):
        return "QUALIFICATION_BLOCKED", "EVIDENCE_INVALID"


class SignalsReadinessController(CycleController):
    """Offline gate wired to the existing archive/delivery/recovery controller."""

    def __init__(self, *, authority, **kwargs):
        super().__init__(**kwargs)
        self.authority = authority

    def _signal(self, packet):
        decision = parse_utc(self.ports.utc_now())
        status, reason = assess(packet, self.authority, decision, max_age_seconds=self.max_age_seconds)
        if status == "NO_TRIGGER":
            return None
        if status != "FIXTURE_QUALIFIED":
            raise ContractError("QUALIFICATION_BLOCKED:" + reason)
        return self._build_signal(packet, decision)

    def _build_signal(self, packet, decision):
        row = packet["snapshot"]
        close = parse_utc(row["closed_at"]).isoformat()
        identity = [VERSION, SCOPE, row["source_id"], close, row["symbol"],
                    row["direction"], row["rule"]]
        evidence = {"source_sha256": packet["source_sha256"],
                    "policy_sha256": self.authority.policy_pin,
                    "witness_sha256": digest(canonical(packet["witness"]))}
        return {"schema": FIXTURE_SCHEMA, "scope": SCOPE,
                "signal_id": "fixture-" + digest(canonical([identity, evidence])),
                "symbol": row["symbol"], "direction": row["direction"], "rule": row["rule"],
                "closed_at":close, "trading_authorized":False, "readiness_contract":VERSION,
                "evidence":evidence, "packet":packet, "decision_at":decision.isoformat().replace("+00:00", "Z")}

    def _stored_signal_valid(self, signal):
        try:
            decision = parse_utc(signal["decision_at"])
            packet = signal["packet"]
            if assess(packet, self.authority, decision, max_age_seconds=self.max_age_seconds)[0] != "FIXTURE_QUALIFIED":
                return False
            return self._build_signal(packet, decision) == signal
        except (KeyError, TypeError, ValueError):
            return False
