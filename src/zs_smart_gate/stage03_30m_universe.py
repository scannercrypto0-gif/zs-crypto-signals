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

def replay_spot_capture(raw: bytes, expected_sha256: str) -> dict:
    """Replay a pinned capture; recorded timing is conditional research evidence."""
    import json
    from .binance_live import to_candles
    from .core import MarketSnapshot
    from .mtf_contracts import CandleWindow
    from .stage03_r1_closed_parent import MarketReceipt, Closed30mItem, _evaluate_closed_30m
    from .stage03_r2_raw_features import _attach_raw_features
    from .stage05_contracts import parse_utc

    if digest(raw) != expected_sha256:
        raise ContractError("SPOT_CAPTURE_PIN_MISMATCH")
    record = json.loads(raw)
    source = record["source"]["source"]
    joined = record["joined_inputs"]
    witness = record["witness"]
    if (record["scope"] != "READ_ONLY_MARKET_QUALIFICATION_RESEARCH"
            or source["venue"] != "BINANCE_SPOT" or source["feed"] != "BINANCE_SPOT_PUBLIC_REST"
            or digest(canonical(joined)) != source["joined_inputs_sha256"]
            or digest(canonical(source)) != record["source"]["source_sha256"]
            or digest(canonical(witness)) != record["witness_sha256"]
            or witness["source_sha256"] != record["source"]["source_sha256"]
            or witness["decision_at"] != source["decision_at"]):
        raise ContractError("SPOT_CAPTURE_BINDING_MISMATCH")
    closed = parse_utc(source["event_close_at"])
    decision = parse_utc(source["decision_at"])
    feed = source["feed"]

    def stamp(value):
        return parse_utc(value.replace(" ", "T").replace("+00:00", "Z"))

    def window(raw_window):
        return CandleWindow(**{**raw_window, "validity_reasons": tuple(raw_window["validity_reasons"]),
                              **{k: stamp(raw_window[k]) for k in
                                 ("open_at", "close_at", "received_at", "available_at")}})

    market_row = joined["market"]
    market = MarketSnapshot(**{**market_row, "observed_at": stamp(market_row["observed_at"])})
    quote = source["liquidity"]
    if (source["symbol"] != market.symbol or quote["book_symbol"] != market.symbol
            or quote["ticker_symbol"] != market.symbol or quote["window"] != "ROLLING_24H"
            or (quote["bid"], quote["ask"], quote["quote_volume"]) !=
            (str(market.bid), str(market.ask), str(market.quote_volume_24h))):
        raise ContractError("SPOT_CAPTURE_MARKET_BINDING_MISMATCH")
    ready = max(parse_utc(quote[kind + "_available_at"]) for kind in ("book", "ticker"))
    for kind in ("book", "ticker"):
        observed, received, available = (parse_utc(quote[kind + "_" + key])
                                         for key in ("observed_at", "received_at", "available_at"))
        if not closed <= observed <= received <= available <= decision:
            raise ContractError("SPOT_CAPTURE_LIQUIDITY_NOT_CAUSAL")
    children = tuple(CandleWindow.from_five_minute(bar, source_id=feed)
                     for bar in to_candles(joined["klines"], stamp(joined["received_at"]))[-6:])
    parent = window(joined["parent"])
    context = tuple(window(bar) for bar in joined["context"])
    if max(ready, parent.available_at, *(bar.available_at for bar in (*children, *context))) != ready:
        raise ContractError("SPOT_CAPTURE_WITNESS_NOT_BOUND_TO_LATEST_INPUT")
    from .stage03_qv1_policy import Policy, verify_event_bracket
    clock = verify_event_bracket(witness, decision, ready,
                                 Policy("RESEARCH_REPLAY", "RECORDED_PUBLIC_SPOT", None, 1499999, 0))
    if clock != "PASS":
        raise ContractError("SPOT_CAPTURE_CLOCK_NOT_ADMISSIBLE")
    item = Closed30mItem(market, MarketReceipt(feed, market.observed_at,
                        parse_utc(quote["ticker_received_at"]), ready), market.symbol,
                        parent, children, context, record["source"]["source_sha256"],
                        source_scope="RECORDED_PUBLIC_SPOT")
    row = _evaluate_closed_30m(item, closed_at=closed, decision_at=decision,
                              source_scope="RECORDED_PUBLIC_SPOT", expected_feed=feed)
    _attach_raw_features(item, row, decision)
    return {"scope": "RECORDED_PUBLIC_SPOT", "symbol_count": 1,
            "complete_exchange_universe_verified": False, "capture_sha256": expected_sha256,
            "clock": "RECORDED_CONDITIONAL_BRACKET_PASS", "row": row}
