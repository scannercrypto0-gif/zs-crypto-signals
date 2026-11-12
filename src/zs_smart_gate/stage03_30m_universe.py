"""Stage03 30m-independent universe coordinator for caller-provided closed candles.

The scheduling integration seam is independent of Setup v1.1 and its 5m
false→true discovery. No timer, Binance client, network, or production signal;
real-source trust is not granted by passing synthetic examples through here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

from .core import utc
from .stage03_r1_closed_parent import Closed30mItem, MAX_LOCAL_UNIVERSE
from .stage03_r2_raw_features import evaluate_raw_research_batch
from .stage05_contracts import ContractError, canonical, digest

VERSION = "zs.stage03.closed-30m-universe-research.v1"
MAX_UNIVERSE_ITEMS = 2048  # engineering resource guard, NOT a market eligibility threshold


def run_closed_30m_research_universe(
    items: Sequence[Closed30mItem], *, closed_at: datetime, decision_at: datetime,
) -> dict:
    """Every provided eligible-or-ineligible item gets an evaluation row.

    Inputs must be a complete externally supplied closed-parent inventory for
    that decision boundary. This function does not assert that market discovery
    or authoritative all-symbol acquisition has actually occurred. A missing
    external symbol cannot be inferred or silently backfilled.
    """
    closed = utc(closed_at)
    decision = utc(decision_at)
    if (closed > decision or closed.second or closed.microsecond
            or closed.minute % 30):
        raise ContractError("UNIVERSE_PARENT_CLOSE_BOUNDARY_INVALID")
    if (not isinstance(items, (tuple, list))
            or not 1 <= len(items) <= MAX_UNIVERSE_ITEMS
            or any(type(x) is not Closed30mItem for x in items)):
        raise ContractError("UNIVERSE_BOUNDED_TYPED_INPUT_REQUIRED")
    keys = [(item.market.symbol, item.discriminator) for item in items]
    if len(set(keys)) != len(keys):
        raise ContractError("UNIVERSE_DUPLICATE_ASSET_EVENT")
    # Stable order and bounded sub-batches; R1's eight-item local safety cap
    # must never be mistaken for an eight-symbol *discovery* gate.
    ordered = sorted(items, key=lambda x: (x.market.symbol, x.discriminator))
    rows = []
    for i in range(0, len(ordered), MAX_LOCAL_UNIVERSE):
        batch = tuple(ordered[i:i + MAX_LOCAL_UNIVERSE])
        rows.extend(evaluate_raw_research_batch(
            batch, closed_at=closed, decision_at=decision))
    if len(rows) != len(ordered):
        raise ContractError("UNIVERSE_SILENTLY_DROPPED_ITEM")
    for row in rows:
        if (row["signal_id"] is not None
                or row["qualification_state"] != "UNKNOWN"
                or row["publishable"] is not False):
            raise ContractError("UNIVERSE_QUALIFICATION_PROMOTION_FORBIDDEN")
    inventory = [{
        "symbol": item.market.symbol,
        "event_id": row["event_id"],
        "candidate_id": row["candidate_id"],
        "evaluation_status": row["evaluation_status"],
        "raw_features_status": row["raw_features_status"],
        "source_manifest_sha256": item.source_manifest_sha256,
        "source_scope": "SYNTHETIC_TEST_ONLY",
    } for item, row in zip(ordered, rows)]
    digest_value = digest(canonical({
        "version": VERSION, "closed_at": closed.isoformat(),
        "decision_at": decision.isoformat(), "inventory": inventory,
    }))
    return {
        "schema": VERSION, "status": "RESEARCH_ONLY_INVENTORY_EVALUATED",
        "closed_at": closed.isoformat(), "decision_at": decision.isoformat(),
        "input_inventory_count": len(items), "evaluated_count": len(rows),
        "inventory_sha256": digest_value, "inventory": inventory,
        "rows": rows, "qualification_state": "UNKNOWN",
        "real_source_verified": False, "complete_exchange_universe_verified": False,
        "signal_id": None, "dispatch_authorized": False,
    }
