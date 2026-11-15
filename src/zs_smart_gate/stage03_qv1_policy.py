"""Policy-pinned Intraday UP qualification. Real trust registries start empty."""
from dataclasses import asdict, dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

from .stage03_qv1_intraday_up import POLICY_SHA256, evaluate_up, inputs_payload
from .stage03_r2_offline import Direction, Unavailable, close_parts
from .stage05_contracts import ContractError, canonical, digest, parse_utc
from .stage05_custody import LocalOutbox

APPROVED_REAL_POLICIES = MappingProxyType({})
VERIFIED_REAL_WITNESSES = MappingProxyType({})
VERIFIED_REAL_SOURCES = frozenset()
CONTRACT = "QV1-B-UP-QUALIFICATION-v2"


@dataclass(frozen=True)
class Policy:
    authority: str
    scope: str
    n01_min: str | None
    max_uncertainty_us: int
    max_witness_age_us: int

    @property
    def sha256(self):
        return digest(canonical({"contract": CONTRACT, **asdict(self),
                                 "detector": POLICY_SHA256,
                                 "evaluator_sha256": digest(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
                                 "tolerance": "EXACT_DECIMAL",
                                 "context_age": "LESS_THAN_ONE_FRAME"}))


def _micros(interval):
    return (interval.days * 86400 + interval.seconds) * 1000000 + interval.microseconds


def verify_event_bracket(witness, decision, available, policy):
    """Use event-local UTC intervals and a single monotonic acquisition domain."""
    domain = witness.get("monotonic_domain")
    if not isinstance(domain, str) or not domain:
        raise ContractError("QV1_BRACKET_DOMAIN_REQUIRED")
    intervals = []
    for name, expected in (("availability", available), ("decision", decision)):
        item = witness[name]
        if item.get("monotonic_domain") != domain:
            raise ContractError("QV1_BRACKET_DOMAIN_MISMATCH")
        if parse_utc(item["host_at"]) != expected:
            raise ContractError("QV1_BRACKET_EVENT_TIME_MISMATCH")
        lower, upper = parse_utc(item["utc_lower"]), parse_utc(item["utc_upper"])
        before, marker, after = (item[k] for k in ("before_mono_ns", "event_mono_ns", "after_mono_ns"))
        if (any(type(v) is not int for v in (before, marker, after))
                or not 0 <= before < marker < after or upper < lower):
            raise ContractError("QV1_BRACKET_ORDER_INVALID")
        intervals.append((lower, upper, marker))
    first, last = intervals
    if first[2] > last[2] or available > decision:
        raise ContractError("QV1_BRACKET_FUTURE_AVAILABILITY")
    if any(_micros(hi-lo) > policy.max_uncertainty_us for lo,hi,_ in intervals):
        return "UNKNOWN"
    return "PASS" if first[1] <= last[0] else "UNKNOWN"


def verify_clock(witness, pin, source_sha, decision, available, policy):
    if witness is None or pin is None:
        return "UNKNOWN"
    if digest(canonical(witness)) != pin:
        raise ContractError("QV1_CLOCK_DIGEST_MISMATCH")
    if policy.scope != "SYNTHETIC_TEST_ONLY" and VERIFIED_REAL_WITNESSES.get(pin) != witness.get("identity"):
        return "UNKNOWN"
    if (witness.get("source_sha256") != source_sha or parse_utc(witness["decision_at"]) != decision
            or witness.get("identity") in (None, "", "BINANCE_SPOT", "LOCAL_CLOCK")
            or not witness.get("calibration_ref") or not witness.get("method")):
        raise ContractError("QV1_CLOCK_BINDING_INVALID")
    if witness["method"] == "AUTHENTICATED_EVENT_BRACKET_V1":
        return verify_event_bracket(witness, decision, available, policy)
    measured = parse_utc(witness["measured_at"])
    received = parse_utc(witness["received_at"])
    ready = parse_utc(witness["available_at"])
    if not measured <= received <= ready <= decision or available > decision:
        raise ContractError("QV1_CLOCK_FUTURE_OR_ORDER_INVALID")
    age = _micros(decision - measured)
    offset, uncertainty, drift = (witness[k] for k in ("offset_us", "uncertainty_us", "drift_ppm"))
    if any(type(v) is not int for v in (offset, uncertainty, drift)) or min(uncertainty, drift) < 0:
        raise ContractError("QV1_CLOCK_BOUNDS_INVALID")
    # Both stamps are on the same measured host clock. Add drift from the
    # calibration instant separately for each bound, rounding outward.
    def bound(stamp):
        distance = abs(_micros(stamp - measured))
        return uncertainty + (distance * drift + 999999) // 1000000
    avail_error, decision_error = bound(available), bound(decision)
    if (age > policy.max_witness_age_us
            or max(avail_error, decision_error) > policy.max_uncertainty_us):
        return "UNKNOWN"
    upper = available + timedelta(microseconds=offset + avail_error)
    lower = decision + timedelta(microseconds=offset - decision_error)
    return "PASS" if upper <= lower else "UNKNOWN"


def evaluate_and_store(data, store, *, policy=None, expected_sha=None, witness=None, witness_pin=None):
    """Evaluate one pinned decision. A real signal is minted after verified readback."""
    if type(store) is not LocalOutbox:
        raise ContractError("QV1_LOCAL_CUSTODY_REQUIRED")
    result = evaluate_up(data, policy_sha256=POLICY_SHA256)
    scope = data.evidence["source_scope"]
    gates = {}
    approval = "POLICY_OWNER_APPROVAL_PENDING"
    policy_sha = None
    if policy is not None:
        policy_sha = policy.sha256
        if policy_sha != expected_sha:
            raise ContractError("QV1_APPROVED_POLICY_SHA_MISMATCH")
        if scope != policy.scope:
            raise ContractError("QV1_POLICY_SCOPE_MISMATCH")
        fixture = scope == "SYNTHETIC_TEST_ONLY" and policy.authority == "SYNTHETIC_TEST_ONLY"
        if fixture or (APPROVED_REAL_POLICIES.get(policy_sha) == policy
                       and result["source_sha256"] in VERIFIED_REAL_SOURCES):
            approval = "SYNTHETIC_TEST_ONLY" if fixture else "OWNER_APPROVED"
            gates = _gates(data, result, policy, witness, witness_pin)
    # Invalid/unavailable evidence never becomes a valid rejection just
    # because some unrelated gate also failed.
    outcome = "UNKNOWN"
    if gates and "UNKNOWN" not in gates.values():
        outcome = "REJECTED" if "FAIL" in gates.values() else "QUALIFIED"
    body = {**result, "qualification_contract": CONTRACT, "qualification_policy_sha256": policy_sha,
            "qualification_authority": approval, "qualification_state": outcome, "gates": gates,
            "witness_sha256": witness_pin, "signal_id": None}
    raw = canonical({"decision": body, "policy": asdict(policy) if policy is not None else None,
                     "source_record": data.evidence, "joined_inputs": inputs_payload(data),
                     "witness": witness})
    key = "qualification-policy/" + digest(canonical([result["event_id"], result["source_sha256"], policy_sha]))
    store.create_if_absent(key, raw)
    if store.read(key) != raw:
        raise ContractError("QV1_QUALIFICATION_READBACK_CONFLICT")
    signal = None
    if outcome == "QUALIFIED":
        prefix = "fixture-sig-" if approval == "SYNTHETIC_TEST_ONLY" else "sig-"
        signal = prefix + digest(canonical([result["event_id"], result["source_sha256"], policy_sha]))
    return {**body, "signal_id": signal, "qualification_readback_sha256": digest(raw)}


def _gates(data, result, policy, witness, witness_pin):
    threshold = None if policy.n01_min is None else Decimal(policy.n01_min)
    if ((threshold is not None and (not threshold.is_finite() or not 0 <= threshold <= 1))
            or type(policy.max_uncertainty_us) is not int or type(policy.max_witness_age_us) is not int
            or min(policy.max_uncertainty_us, policy.max_witness_age_us) < 0):
        raise ContractError("QV1_POLICY_LIMITS_INVALID")
    decision = parse_utc(data.evidence["decision_at"])
    latest_context = result["context_complete"] and all(
        decision - bar.close_at < timedelta(hours=1 if bar.timeframe == "1h" else 4)
        for bar in data.context)
    exact = all(getattr(data.tolerance, k) == 0 for k in ("price", "base_volume", "quote_volume"))
    joined = exact and result["reconciliation"] == "PASS"
    available = max(data.received_at, data.parent.available_at, data.market.observed_at,
                    *(bar.available_at for bar in data.context))
    n01 = "UNKNOWN"
    if joined and threshold is not None:
        parent = data.parent
        try:
            k,b,w = close_parts(SimpleNamespace(o=parent.open,h=parent.high,l=parent.low,c=parent.close),
                                Direction.UP)
        except Unavailable:
            pass
        else:
            n01 = "PASS" if (8*k+6*b+6*w)/20 >= threshold else "FAIL"
    market = result["research_market_gate"]
    liquidity = data.evidence["source"].get("liquidity")
    if (not isinstance(liquidity, dict)
            or liquidity.get("book_symbol") != data.market.symbol
            or liquidity.get("ticker_symbol") != data.market.symbol
            or liquidity.get("quote_asset") != data.market.quote_asset
            or liquidity.get("window") != "ROLLING_24H"
            or liquidity.get("bid") != str(data.market.bid)
            or liquidity.get("ask") != str(data.market.ask)
            or liquidity.get("quote_volume") != str(data.market.quote_volume_24h)):
        market = "UNKNOWN"
    else:
        seen = []
        for kind in ("book", "ticker"):
            observed, received, ready = (parse_utc(liquidity[kind + "_" + field])
                                         for field in ("observed_at", "received_at", "available_at"))
            if not observed <= received <= ready <= decision:
                raise ContractError("QV1_LIQUIDITY_FUTURE_OR_ORDER_INVALID")
            if decision - observed > timedelta(seconds=90):
                market = "UNKNOWN"
            seen.append(observed)
            available = max(available, ready)
        if max(seen) != data.market.observed_at:
            raise ContractError("QV1_LIQUIDITY_MARKET_TIMESTAMP_MISMATCH")
    return {**({"N01": n01} if threshold is not None else {}),
            "SETUP": ("PASS" if result["setup_state"] == "DETECTED_SIGNAL" else
                      "FAIL" if result["setup_state"] == "RESEARCH_CANDIDATE" else "UNKNOWN"),
            "EXACT_RECONCILIATION": "PASS" if joined else "UNKNOWN",
            "CONTEXT": "PASS" if latest_context else "UNKNOWN",
            "LIQUIDITY": market,
            "UTC_WITNESS": verify_clock(witness, witness_pin, result["source_sha256"],
                                        decision, available, policy)}
