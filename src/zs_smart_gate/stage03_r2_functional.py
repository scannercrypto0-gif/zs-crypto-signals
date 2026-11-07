"""009A synthetic-only Stage03 calculation-to-research-contract E2E bridge.

No production scores, qualification, source ingestion, market requests or
signal assignment. Separate typed 03A and R2 inputs must reconcile exactly:
no invented base volume, clock receipts, rolling ticker or signal ID.
"""
from __future__ import annotations

import hashlib
import json
from typing import Mapping, Sequence

from .core import MarketSnapshot
from .mtf_contracts import CandleWindow
from .stage03_qualification_readiness import assess_readiness
from .stage03_r2_offline import Candle, Market, Unavailable, evaluate_r2
from .stage03_r2_source_contract import (
    BookTickerPacket, Ticker24Packet, CausalImpulseObservation,
    VersionedFullImpulsePredicate, ModeSourceEvidence,
    inspect_full_impulse_trace, market_from_explicit_packets, require_prior_mode,
)


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
                              readiness_inputs: Mapping[str, object],
                              full_impulse_definition: VersionedFullImpulsePredicate | None = None,
                              full_impulse_trace: Sequence[CausalImpulseObservation] | None = None,
                              market_source_packets: tuple[BookTickerPacket, Ticker24Packet] | None = None,
                              mode_source_evidence: ModeSourceEvidence | None = None) -> dict:
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
    # Legacy booleans remain synthetic arithmetic fixtures only. Even a typed
    # complete trace is UNAPPROVED; the PM expressly rejected any implicit
    # full-impulse meaning (including equality with Setup v1.1).
    trace_review = None
    impulse_reason = "FULL_IMPULSE_PREDICATE_NOT_DEFINED_FOR_FUNCTIONAL_CONTRACT"
    if full_impulse_definition is not None or full_impulse_trace is not None:
        try:
            past = r2_inputs["context"].get("5m", ())
            trace_review = inspect_full_impulse_trace(
                definition=full_impulse_definition, trace=full_impulse_trace,
                candles=tuple(past[-39:]) + tuple(r2_inputs["children"]),
                direction=r2_inputs["direction"], horizon=r2_inputs["horizon"],
                mode=r2_inputs["mode"], decision_at=r2_inputs["decision_at"],
                witness=r2_inputs["witness"])
            impulse_reason = trace_review["reason"]
        except Unavailable as exc:
            impulse_reason = str(exc)
            trace_review = {"status": "TRACE_BLOCKED", "reason": impulse_reason}
    if "MOMENTUM_EARLY_TIMING" in r2["normalizers"]:
        r2["normalizers"]["MOMENTUM_EARLY_TIMING"] = None
        r2["missing_reasons"]["MOMENTUM_EARLY_TIMING"] = impulse_reason

    mode_review = None
    if r2_inputs["horizon"].value == "SWING":
        try:
            mode_review = require_prior_mode(
                mode_source_evidence, mode=r2_inputs["mode"],
                direction=r2_inputs["direction"], horizon=r2_inputs["horizon"],
                parent=r2_inputs["parent"], decision_at=r2_inputs["decision_at"],
                witness=r2_inputs["witness"])
        except Unavailable as exc:
            mode_review = {"status": "MODE_BLOCKED", "reason": str(exc)}
            for group in ("MARKET_STRUCTURE", "DAILY_WEEKLY_CONTEXT"):
                if r2["normalizers"].get(group) is not None:
                    r2["normalizers"][group] = None
                    r2["missing_reasons"][group] = str(exc)
            r2["structural_event"] = False
            r2["structural_event_kind"] = None
            r2["candidate_level_id"] = None

    source_review = {"status": "SOURCE_EXPLICIT_PACKETS_ABSENT",
                     "real_pit_verified": False}
    source_mismatch = None
    if market_source_packets is not None:
        try:
            if not isinstance(market_source_packets, tuple) or len(market_source_packets) != 2:
                raise Unavailable("SOURCE_PACKETS_PAIR_REQUIRED")
            book, ticker = market_source_packets
            supplied = market_from_explicit_packets(
                book=book, ticker=ticker, decision_at=r2_inputs["decision_at"],
                witness=r2_inputs["witness"])
            expected = r2_inputs["market"]
            if (not isinstance(expected, Market) or supplied != expected):
                raise Unavailable("EXPLICIT_BOOK_TICKER_R2_MARKET_MISMATCH")
            if book.symbol != readiness_inputs["symbol"]:
                raise Unavailable("EXPLICIT_BOOK_TICKER_IDENTITY_MISMATCH")
            source_review = {
                "status": "SYNTHETIC_PACKETS_VALID_NOT_REAL_PIT",
                "real_pit_verified": False,
                "book_source": book.receipt.source_id,
                "ticker24_source": ticker.receipt.source_id,
                "book_available_at": book.receipt.available_at.isoformat(),
                "ticker24_available_at": ticker.receipt.available_at.isoformat(),
                "atomicity_claim": False,
            }
        except Unavailable as exc:
            source_mismatch = str(exc)
            source_review = {"status": "SOURCE_PACKETS_BLOCKED",
                             "reason": source_mismatch,
                             "real_pit_verified": False}
    if source_review["status"] != "SYNTHETIC_PACKETS_VALID_NOT_REAL_PIT":
        if r2["normalizers"].get("LIQUIDITY_QUALITY") is not None:
            r2["normalizers"]["LIQUIDITY_QUALITY"] = None
            r2["missing_reasons"]["LIQUIDITY_QUALITY"] = (
                source_mismatch or "EXPLICIT_BOOK_TICKER_REQUIRED_FOR_E2E")
        if r2_inputs["horizon"].value == "SWING":
            if r2["normalizers"].get("MARKET_STRUCTURE") is not None:
                r2["normalizers"]["MARKET_STRUCTURE"] = None
                r2["missing_reasons"]["MARKET_STRUCTURE"] = (
                    source_mismatch or "EXPLICIT_BOOK_TICKER_REQUIRED_FOR_E2E")
            r2["structural_event"] = False
            r2["structural_event_kind"] = None
            r2["candidate_level_id"] = None
    readiness = assess_readiness(**readiness_inputs)
    raw_parent, parent = r2_inputs["parent"], readiness_inputs["parent"]
    raw_children, children = r2_inputs["children"], readiness_inputs["children"]
    raw_market, market = r2_inputs["market"], readiness_inputs["market"]
    reasons = []
    if source_mismatch is not None:
        reasons.append("R2_SOURCE_PACKET_REJECTED:" + source_mismatch)
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
        "full_impulse_trace_review": trace_review,
        "mode_evidence_review": mode_review,
        "market_source_review": source_review,
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
