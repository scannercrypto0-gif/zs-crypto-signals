"""ORDER007 bounded ORIGINAL public Spot capture and honest UP/DOWN admission.

Manual Windows foreground only. Data capture is not scientific qualification.
Raw bodies remain on D:; sanitized derived manifest contains only source hashes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import time

from .marketwide_capture import (PublicCapture, MAX_REQUESTS, MAX_WEIGHT, MAX_SECONDS, MAX_USED_WEIGHT, MAX_TOTAL_BODY, WEIGHTS)
from .marketwide_cursor import PauseScan
from .marketwide_research import FRAMES, evaluate, inventory, packet_from_receipts
from .stage05_contracts import canonical, digest
from .ops_windows_time import command, COMMANDS, assess
from .ops_windows_child import sync_age


VERSION = "zs.order007.original-public-spot-source.v1"
MAX_SYMBOLS = 2


class CompleteBoundedCapture(PublicCapture):
    """Allows a complete 11th response but never a 12th GET.

    The inherited capture's healthy() uses attempts < MAX_REQUESTS both
    before AND after the response, stopping after an otherwise valid 11th
    receipt. This strictly bounded subclass preserves the 11-attempt budget
    and additionally enforces the actual observed one-minute exchange limit.
    """
    runtime_guard = MAX_USED_WEIGHT

    def healthy(self):
        return (self.monotonic()-self.start < MAX_SECONDS
                and self.attempts <= MAX_REQUESTS
                and self.used < self.runtime_guard
                and self.bytes < MAX_TOTAL_BODY)

    def get(self, path, params):
        if path not in WEIGHTS:
            raise ValueError("ENDPOINT_NOT_ALLOWED")
        if (self.attempts >= MAX_REQUESTS
                or self.weight + WEIGHTS[path] > MAX_WEIGHT
                or self.used + WEIGHTS[path] >= self.runtime_guard):
            raise PauseScan("ORDER007_DYNAMIC_RATE_HEADROOM_STOP")
        return super().get(path, params)


def _adopt_runtime_budget(receipt, transport):
    limits = receipt["payload"].get("rateLimits")
    if not isinstance(limits, list):
        raise PauseScan("MISSING_EXCHANGE_REQUEST_WEIGHT_POLICY")
    values = [x.get("limit") for x in limits
              if isinstance(x, dict) and x.get("rateLimitType") == "REQUEST_WEIGHT"
              and x.get("interval") == "MINUTE" and x.get("intervalNum") == 1]
    if len(values) != 1 or type(values[0]) is not int or values[0] <= 500:
        raise PauseScan("UNVERIFIED_EXCHANGE_REQUEST_WEIGHT_POLICY")
    observed_cap = min(MAX_USED_WEIGHT, values[0]-500)
    if observed_cap <= 100:
        raise PauseScan("INSUFFICIENT_DYNAMIC_RATE_HEADROOM")
    if isinstance(transport, CompleteBoundedCapture):
        transport.runtime_guard = observed_cap
    return {"exchange_request_weight_per_minute": values[0],
            "internal_headroom_guard": observed_cap}


def bounded_source(root: Path, symbols: tuple[str, ...], *, transport=None,
                   timestamp_ms=None, check_clock=True) -> dict:
    """One bounded independent original sample. No loops, sends or trading.

    CLI must enforce Windows 3.12, D-only and a clean Git checkout; transport
    injection is for synthetic/offline unit testing.
    """
    root = Path(root)
    if not root.is_dir() or not isinstance(symbols, tuple) or not 1 <= len(symbols) <= MAX_SYMBOLS:
        raise ValueError("ORDER007_CAPTURE_ROOT_OR_SYMBOLS")
    if len(set(symbols)) != len(symbols) or any(
            not isinstance(s, str) or not 3 <= len(s) <= 30
            or not s.isascii() or not s.isalnum()
            or not s.endswith("USDT") or not s.isupper() for s in symbols):
        raise ValueError("ORDER007_CAPTURE_SYMBOL_IDENTITY")
    transport = transport or CompleteBoundedCapture(root)
    clock = {"status": "BLOCKED", "blockers": ["NO_REVIEWED_OPERATIONAL_TIME_POLICY"]}
    result = {
        "schema": VERSION, "symbols_requested": list(symbols),
        "status": "PARTIAL", "clock_state": clock["status"],
        "scientific_state": "SCIENCE_NOT_APPROVED",
        "up_real_science": "NOT_QUALIFIED",
        "down_real_science": "NOT_QUALIFIED",
        "qualified_signal_ids": [], "external_effects": "OFF",
        "accepted_5m_event_windows": 0,
        "directions_source_validated": 0, "coverage": [],
        "stop": None,
    }
    source_rows = []
    try:
        receipts = [transport.get("exchangeInfo", {"showPermissionSets": "false"})]
        result["dynamic_rate_budget"] = _adopt_runtime_budget(receipts[0], transport)
        for endpoint in ("ticker/24hr", "ticker/bookTicker"):
            receipts.append(transport.get(endpoint, {}))
        snap = inventory(receipts, datetime.now(timezone.utc),
                         scope="ALL_BINANCE_SPOT_INVENTORY")
        active = {row["symbol"]: row for row in snap["rows"] if row["eligible"]}
        result["discovered_instruments"] = len(snap["rows"])
        result["eligible_supported"] = len(active)
        result["eligible_inventory_sha256"] = snap["snapshot_sha256"]
        if check_clock:
            obs = {key: command(args) for key, args in COMMANDS.items()}
            for key, value in obs.items():
                (root/("clock-"+key+".private.json")).write_bytes(canonical(value))
            clock = assess(obs, sync_age_s=sync_age(obs["status"]["stdout"]))
            result["clock_state"] = clock["status"]
            result["clock_blockers"] = clock["blockers"]
        # No "current 30m" future candle. Most starts are historical, honestly
        # marked LATE; never label that historical snapshot as prospective PIT.
        millis = int(time.time()*1000) if timestamp_ms is None else timestamp_ms
        if type(millis) is not int or millis <= 0:
            raise ValueError("INVALID_SOURCE_TIMESTAMP")
        boundary = millis // FRAMES["30m"] * FRAMES["30m"]
        result["reference_boundary_ms"] = boundary
        result["arrival_lag_seconds_at_start"] = (millis-boundary)/1000
        for symbol in symbols:
            if symbol not in active:
                result["coverage"].append({
                    "symbol": symbol, "status": "UNSCANNED_INELIGIBLE_OR_UNAVAILABLE",
                    "reason": "NOT_IN_TIMESTAMPED_ELIGIBLE_INVENTORY"})
                continue
            item = active[symbol]
            frame_receipts = []
            frame_body_files = {}
            # This is a bounded original source sample, not full market coverage.
            # Exactly 22 closed 5m bars plus 30m, 1h and 4h anchors.
            for frame, duration in FRAMES.items():
                end = boundary // duration * duration
                rec = transport.get("klines", {
                    "symbol": symbol, "interval": frame,
                    "endTime": str(end-1),
                    "limit": "22" if frame == "5m" else "1"})
                frame_receipts.append(rec)
                frame_body_files[frame] = {
                    "file": "response-" + str(transport.attempts) + ".private",
                    "sha256": rec["body_sha256"]}
            packet = packet_from_receipts(
                item, frame_receipts, boundary_ms=boundary,
                decision_at=datetime.now(timezone.utc),
                scope="PUBLIC_SPOT_CONDITIONAL_RESEARCH",
                clock_status=("OPERATIONAL_TIME_ACCEPTED" if
                              clock["status"] == "OPERATIONAL_TIME_ACCEPTED"
                              else "CLOCK_UNVERIFIED"))
            packet_digest = digest(canonical(packet))
            # Only local D: stores authentic payload and combined input.
            private = root/(symbol+"-source.private.json")
            private.write_bytes(canonical(packet))
            outcomes = evaluate(packet)
            admission = all(r["source_validated"] for r in outcomes)
            result["directions_source_validated"] += sum(
                r["source_validated"] for r in outcomes)
            result["accepted_5m_event_windows"] += int(admission)
            outcome_summary = [{
                "direction": r["direction"], "status": r["status"],
                "reason": r["reason"], "source_validated": r["source_validated"],
                "event_id": r["event_id"], "signal_id": None,
            } for r in outcomes]
            result["coverage"].append({
                "symbol": symbol,
                "status": ("SOURCE_VALIDATED_CLOCK_BLOCKED"
                           if admission and clock["status"] != "OPERATIONAL_TIME_ACCEPTED"
                           else "SOURCE_VALIDATED_RESEARCH_ONLY"
                           if admission else "SOURCE_INVALID_OR_INCOMPLETE"),
                "packet_sha256": packet_digest,
                "private_packet_sha256": digest(private.read_bytes()),
                "input_payload_sha256": {
                    row["params"]["interval"]: row["body_sha256"]
                    for row in frame_receipts},
                "private_body_files": frame_body_files,
                "event_30m_boundary_ms": boundary,
                "first_5m_row_count": len(frame_receipts[0]["payload"]),
                "directional_admission": outcome_summary,
            })
            source_rows.append(packet_digest)
        result["status"] = ("RESEARCH_CAPTURED_NO_SCIENCE_AUTHORITY"
                            if result["accepted_5m_event_windows"] else "PARTIAL_NO_VALID_CANDLES")
    except PauseScan as exc:
        result["stop"] = "BOUNDED_SOURCE_STOP:"+str(exc)
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        # Do not leak raw endpoint content or exception text to sanitized Git.
        result["stop"] = "SOURCE_VALIDATION_STOP:"+type(exc).__name__
    finally:
        result["requests"] = transport.attempts
        result["estimated_request_weight"] = transport.weight
        result["last_observed_ip_weight"] = transport.used
        result["private_body_bytes"] = transport.bytes
        result["source_chain_sha256"] = digest(canonical(transport.receipts))
        result["raw_body_receipts"] = [
            {"file": "response-" + str(i) + ".private",
             "sha256": row.get("body_sha256")}
            for i, row in enumerate(transport.receipts, 1)]
        result["packet_chain_sha256"] = digest(canonical(source_rows))
        (root/"sanitized-source-manifest.json").write_bytes(canonical(result))
    return result
