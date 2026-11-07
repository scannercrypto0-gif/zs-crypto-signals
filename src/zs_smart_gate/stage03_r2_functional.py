"""009A synthetic-only Stage03 calculation-to-research-contract E2E bridge.

No production scores, qualification, source ingestion, market requests or
signal assignment. Separate typed 03A and R2 inputs must reconcile exactly:
no invented base volume, clock receipts, rolling ticker or signal ID.
"""
from __future__ import annotations

import hashlib
import json
from typing import Mapping

from .core import MarketSnapshot
from .mtf_contracts import CandleWindow
from .stage03_qualification_readiness import assess_readiness
from .stage03_r2_offline import Candle, Market, evaluate_r2


def _matching_bar(raw: Candle, source: CandleWindow) -> bool:
    return (
        source.source_id == raw.source_id
        and (source.open_at, source.close_at, source.received_at,
             source.available_at) == (raw.open_at, raw.close_at, raw.received_at,
                                      raw.available_at)
        and (source.open, source.high, source.low, source.close, source.quote_volume)
        == (raw.o, raw.h, raw.l, raw.c, raw.q)
    )


def stage03_r2_functional_e2e(*, r2_inputs: Mapping[str, object],
                              readiness_inputs: Mapping[str, object]) -> dict:
    """Connect existing R2 candidates to existing 03A readiness, fail closed.

    Each source enters as its ORIGINAL typed contract. This function neither
    synthesizes a base/quote conversion nor converts a research candidate to
    DETECTED_SIGNAL. Missing R2 features are kept unavailable, not zero.
    """
    if not isinstance(r2_inputs, Mapping) or not isinstance(readiness_inputs, Mapping):
        raise ValueError("STAGE03_TYPED_INPUTS_REQUIRED")
    if readiness_inputs.get("normalized_groups") is not None:
        raise ValueError("UNAPPROVED_NUMERIC_SCORE_INPUT_FORBIDDEN")
    r2 = evaluate_r2(**r2_inputs)
    # The legacy synthetic onset fixture supplies boolean flags but does NOT
    # define/attest the full impulse predicate. Preserve its arithmetic unit
    # test, while withholding N03 from the integrated Stage03 availability.
    if r2["normalizers"].get("MOMENTUM_EARLY_TIMING") is not None:
        r2["normalizers"]["MOMENTUM_EARLY_TIMING"] = None
        r2["missing_reasons"]["MOMENTUM_EARLY_TIMING"] = (
            "FULL_IMPULSE_PREDICATE_NOT_DEFINED_FOR_FUNCTIONAL_CONTRACT")
    readiness = assess_readiness(**readiness_inputs)
    raw_parent, parent = r2_inputs["parent"], readiness_inputs["parent"]
    raw_children, children = r2_inputs["children"], readiness_inputs["children"]
    raw_market, market = r2_inputs["market"], readiness_inputs["market"]
    reasons = []
    if (not isinstance(raw_parent, Candle) or not isinstance(parent, CandleWindow)
            or not raw_parent.source_id.startswith("SYNTHETIC:")
            or not _matching_bar(raw_parent, parent)):
        reasons.append("R2_03A_PARENT_SOURCE_AND_VALUES_DISAGREE")
    if (len(raw_children) != len(children)
            or any(not isinstance(raw, Candle) or not isinstance(view, CandleWindow)
                   or not _matching_bar(raw, view)
                   for raw, view in zip(raw_children, children))):
        reasons.append("R2_03A_CHILD_SOURCE_AND_VALUES_DISAGREE")
    if (r2_inputs["horizon"] != readiness_inputs["horizon"]
            or r2_inputs["direction"] != readiness_inputs["direction"]
            or r2_inputs["decision_at"] != readiness_inputs["decision_at"]):
        reasons.append("R2_03A_DECISION_IDENTITY_DISAGREES")
    if (not isinstance(raw_market, Market) or not isinstance(market, MarketSnapshot)
            or market.quote_asset != "USDT" or not market.spot_enabled
            or market.trading_status != "TRADING"
            or market.bid != raw_market.bid or market.ask != raw_market.ask
            or market.quote_volume_24h != raw_market.quote_24h
            or market.observed_at < max(raw_market.book.available_at,
                                        raw_market.ticker24.available_at)
            or market.observed_at > readiness_inputs["decision_at"]):
        reasons.append("R2_03A_MARKET_SNAPSHOT_UNRECONCILED")
    if r2["status"] == "INVALID":
        reasons.append("R2_INPUT_INVALID")
    if readiness["status"] != "RESEARCH_CANDIDATE":
        reasons.append("STAGE03_RESEARCH_READINESS_REJECTED")
    status = "RESEARCH_CANDIDATE" if not reasons else "REJECTED"
    packet = {
        "schema": "ZS03_009A_SYNTHETIC_FUNCTIONAL_E2E_V1",
        "status": status,
        "qualification_status": "NOT_EVALUATED",
        "identity": readiness["identity"],
        "readiness_status": readiness["status"],
        "readiness_reason_codes": readiness["reason_codes"],
        "source_match_reasons": reasons,
        "r2": r2,
        "provenance": {
            "source_kind": "SYNTHETIC_ONLY_NOT_REAL_PIT",
            "parent_source_id": parent.source_id,
            "market_source_book": raw_market.book.source_id,
            "market_source_ticker24": raw_market.ticker24.source_id,
            "market_book_received_at": raw_market.book.received_at.isoformat(),
            "market_ticker24_received_at": raw_market.ticker24.received_at.isoformat(),
            "market_book_available_at": raw_market.book.available_at.isoformat(),
            "market_ticker24_available_at": raw_market.ticker24.available_at.isoformat(),
            "quote24_unit": raw_market.ticker24_unit,
            "quote24_window": raw_market.ticker24_window,
            "independent_receipt": False,
        },
        "score_status": "SCORE_UNAVAILABLE",
        "score": None,
        "signal_id": None,
        "publishable": False,
        "delivery_authorized": False,
        "full_system_edge_tested": False,
        "market_requests": 0,
        "external_sends": 0,
    }
    blob = json.dumps(packet, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")
    packet["packet_sha256"] = hashlib.sha256(blob).hexdigest()
    return packet
