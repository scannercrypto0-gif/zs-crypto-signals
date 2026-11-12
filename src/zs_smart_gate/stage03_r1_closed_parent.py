"""R1: bounded, independently triggered CLOSED-30m research intake.

Offline/local fixture inputs only. Does NOT depend on Setup v1.1 or produce
zs.stage05.event.v1, qualified events, signals, scores or outbound requests.
The existing market screen is RESEARCH universe eligibility, not a policy gate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from decimal import Decimal

from .core import MarketSnapshot, check_eligibility, utc
from .mtf_contracts import (
    CandleWindow, ReconciliationTolerance, available_closed_context, reconcile,
)
from .stage03_r0_identity import DiscoveryReference, EvaluationIdentity, stamp
from .stage05_contracts import ContractError, SHA, canonical, digest
from .stage05_custody import LocalOutbox

VERSION = "zs.r1.closed-30m-research.v1"
MAX_LOCAL_UNIVERSE = 8  # work-budget cap only; NOT a qualification threshold
EXACT_OBSERVATION = ReconciliationTolerance(
    Decimal("0"), Decimal("0"), Decimal("0"), "R1_EXACT_OBSERVATION_NOT_APPROVED_SOURCE_TOLERANCE",
)
AGGREGATION_ERRORS = frozenset((
    "OPEN_AGGREGATION_MISMATCH", "HIGH_AGGREGATION_MISMATCH",
    "LOW_AGGREGATION_MISMATCH", "CLOSE_AGGREGATION_MISMATCH",
    "BASE_VOLUME_AGGREGATION_MISMATCH", "QUOTE_VOLUME_AGGREGATION_MISMATCH",
))


@dataclass(frozen=True)
class MarketReceipt:
    source_id: str
    observed_at: datetime
    received_at: datetime
    available_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise ContractError("R1_MARKET_RECEIPT_SOURCE_REQUIRED")
        for field in ("observed_at", "received_at", "available_at"):
            object.__setattr__(self, field, utc(getattr(self, field)))


@dataclass(frozen=True)
class Closed30mItem:
    """Caller-supplied local fixture; not trusted as a real exchange receipt."""

    market: MarketSnapshot
    market_receipt: MarketReceipt
    candle_symbol: str
    parent: CandleWindow
    children: tuple[CandleWindow, ...]
    context: tuple[CandleWindow, ...]
    source_manifest_sha256: str
    previous_30m: tuple[CandleWindow, ...] = ()
    discovery: DiscoveryReference | None = None
    discriminator: str = "GENERAL_30M"
    source_scope: str = "SYNTHETIC_TEST_ONLY"

    def __post_init__(self) -> None:
        if (self.source_scope != "SYNTHETIC_TEST_ONLY"
                or not isinstance(self.source_manifest_sha256, str)
                or not SHA.fullmatch(self.source_manifest_sha256)
                or not isinstance(self.children, tuple)
                or not isinstance(self.context, tuple)
                or not isinstance(self.previous_30m, tuple)
                or self.discovery is not None and not isinstance(self.discovery, DiscoveryReference)):
            raise ContractError("R1_SYNTHETIC_INPUT_CONTRACT_REQUIRED")


def _jsonable(value):
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return stamp(value)
    if isinstance(value, Decimal):
        return str(value)
    return value


def evidence_digest(item: Closed30mItem) -> str:
    """Independent from the economic event key; includes source and receipt data."""
    return digest(canonical({"contract": VERSION, "input": _jsonable(item)}))


def evaluate_closed_30m(item: Closed30mItem, *, closed_at: datetime,
                        decision_at: datetime) -> dict:
    """A real policy NEVER runs here. No call to Setup.evaluate or network code."""
    closed_at, decision_at = utc(closed_at), utc(decision_at)
    identity = EvaluationIdentity(item.market.symbol, closed_at,
                                  discriminator=item.discriminator)
    identity_row = identity.as_dict()
    if item.parent.close_at != closed_at:
        raise ContractError("R1_TRIGGER_PARENT_CLOSE_MISMATCH")
    source_sha = evidence_digest(item)
    row = {
        "schema": VERSION, "identity": identity_row,
        "event_id": identity_row["event_id"], "candidate_id": identity_row["candidate_id"],
        "source_scope": "SYNTHETIC_TEST_ONLY",
        "source_manifest_sha256": item.source_manifest_sha256,
        "input_sha256": source_sha, "trigger": "ELIGIBLE_UNIVERSE_CLOSED_30M",
        "discovery": item.discovery.as_dict() if item.discovery else None,
        "evaluation_status": "UNKNOWN", "reason_codes": [],
        "research_universe_screen": "NOT_EVALUATED",
        "reconciliation": "NOT_EVALUATED",
        "reconciliation_reasons": [],
        "raw_30m_evaluation_eligible": False,
        "context_close_at": {}, "context_age_policy": "UNAPPROVED",
        "source_tolerance_policy": "UNAPPROVED_EXACT_OBSERVATION_ONLY",
        "market_freshness_policy": "UNAPPROVED",
        "independent_utc_witness": "NOT_ATTESTED",
        "qualification_state": "UNKNOWN", "signal_id": None,
        "score_status": "SCORE_UNAVAILABLE", "score": None, "trade_plan": None,
        "publishable": False, "stage05_event_v1_compatible": False,
        "decision_at": stamp(decision_at),
    }

    def finish(status: str, *reasons: str) -> dict:
        row["evaluation_status"] = status
        row["reason_codes"] = list(dict.fromkeys(reasons))
        return row

    if (item.candle_symbol != item.market.symbol
            or item.market_receipt.source_id != item.parent.source_id
            or not item.parent.source_id.startswith("SYNTHETIC:")
            or any(c.source_id != item.parent.source_id for c in item.context)):
        return finish("INVALID", "R1_MIXED_SOURCE_OR_SYMBOL")
    receipt = item.market_receipt
    if (receipt.observed_at != item.market.observed_at
            or not receipt.observed_at <= receipt.received_at <= receipt.available_at <= decision_at
            or decision_at < closed_at):
        return finish("INVALID", "R1_MARKET_RECEIPT_NOT_CAUSAL")
    if receipt.observed_at < closed_at:
        return finish("UNKNOWN", "R1_MARKET_NOT_OBSERVED_AFTER_PARENT_CLOSE")
    if item.parent.timeframe != "30m":
        return finish("INVALID", "R1_NOT_A_30M_PARENT")

    market_reasons = check_eligibility(item.market, decision_at)
    if market_reasons:
        if "INVALID_BID_ASK" in market_reasons or "MARKET_SNAPSHOT_FROM_FUTURE" in market_reasons:
            return finish("UNKNOWN", *market_reasons)
        row["research_universe_screen"] = "NOT_ELIGIBLE"
        return finish("NOT_ELIGIBLE", *market_reasons)
    row["research_universe_screen"] = "PASS_RESEARCH_ONLY"

    joined = reconcile(item.parent, item.children, decision_at, tolerance=EXACT_OBSERVATION)
    row["reconciliation_reasons"] = list(joined.reason_codes)
    if joined.status != "PASS":
        if set(joined.reason_codes).issubset(AGGREGATION_ERRORS):
            row["reconciliation"] = "EXACT_MISMATCH_TOLERANCE_UNAPPROVED"
            return finish("UNKNOWN", "R1_SOURCE_TOLERANCE_UNAPPROVED", *joined.reason_codes)
        row["reconciliation"] = "INVALID_STRUCTURAL_SOURCE"
        return finish("INVALID", *joined.reason_codes)
    row["reconciliation"] = "EXACT_MATCH_NOT_POLICY_APPROVAL"

    if any(c.timeframe not in ("1h", "4h") for c in item.context):
        return finish("INVALID", "R1_CONTEXT_FRAME_UNSUPPORTED")
    available = {}
    for frame in ("1h", "4h"):
        # Exclude post-event closes even if they were received before a delayed decision.
        admissible = [c for c in item.context if c.close_at <= closed_at]
        selected = available_closed_context(admissible, timeframe=frame, decision_at=decision_at)
        if selected is not None:
            available[frame] = selected
            row["context_close_at"][frame] = stamp(selected.close_at)
    if len(available) != 2:
        return finish("UNKNOWN", "R1_REQUIRED_CLOSED_CONTEXT_UNAVAILABLE")
    row["raw_30m_evaluation_eligible"] = True
    return finish("POLICY_HOLD", "R1_REAL_QUALIFICATION_POLICY_UNAPPROVED",
                  "R1_SOURCE_AND_WITNESS_TRUST_UNAPPROVED")


def evaluate_local_universe(items: tuple[Closed30mItem, ...], *, closed_at: datetime,
                            decision_at: datetime) -> list[dict]:
    """Explicit 30m clock entrypoint, independent of all 5m discovery candidates.

    O(n log n) sorting, max 8 synthetic items, no external acquisition or timers.
    Deterministic one record per symbol/close/discriminator (no retry duplication).
    """
    if not isinstance(items, tuple) or len(items) > MAX_LOCAL_UNIVERSE:
        raise ContractError("R1_BOUNDED_LOCAL_UNIVERSE_REQUIRED")
    symbols = [(x.market.symbol, x.discriminator) for x in items]
    if len(symbols) != len(set(symbols)):
        raise ContractError("R1_DUPLICATE_SYMBOL_DISCRIMINATOR")
    return [evaluate_closed_30m(x, closed_at=closed_at, decision_at=decision_at)
            for x in sorted(items, key=lambda y: (y.market.symbol, y.discriminator))]


def persist_local_research(store: LocalOutbox, row: dict) -> dict:
    """Append-only local research custody; never an authorized Stage05 delivery."""
    if (type(store) is not LocalOutbox or row.get("schema") != VERSION
            or row.get("source_scope") != "SYNTHETIC_TEST_ONLY"
            or row.get("signal_id") is not None or row.get("publishable") is not False
            or row.get("qualification_state") != "UNKNOWN"):
        raise ContractError("R1_RESEARCH_ONLY_CUSTODY_REQUIRED")
    payload = canonical(row)
    key = "research-closed-parent/" + digest(canonical([
        row["event_id"], row["input_sha256"], VERSION,
    ]))
    store.create_if_absent(key, payload)
    if store.read(key) != payload:
        raise ContractError("R1_CUSTODY_READBACK_CONFLICT")
    return {"research_event_id": row["event_id"], "record_key": key,
            "record_sha256": digest(payload), "readback": "PASS",
            "signal_id": None, "dispatch_allowed": False}
