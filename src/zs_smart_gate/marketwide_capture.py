"""Bounded public inventory and optional clock-admitted candle chunk, Windows only."""
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, ProxyHandler, build_opener

from .binance_live import BASE, is_spot_enabled
from .e2e51 import NoRedirect
from .marketwide_cursor import PauseScan, ScanLedger
from .marketwide_research import FRAMES, inventory, packet_from_receipts
from .ops_windows_time import COMMANDS, assess, command, now
from .stage05_contracts import canonical, digest
from .ops_windows_child import sync_age

def _is_admin():
    """Check the current Windows process token, never trust a caller flag."""
    if os.name != "nt":
        return False
    import ctypes
    return ctypes.windll.shell32.IsUserAnAdmin() == 1


MAX_REQUESTS = 11
MAX_WEIGHT = 140
MAX_USED_WEIGHT = 5500  # 500-point reserve below documented Spot 6000 weight/min per IP
MAX_SECONDS = 110
MAX_BODY = 16 * 1024 * 1024
MAX_TOTAL_BODY = 32 * 1024 * 1024
WEIGHTS = {"exchangeInfo": 20, "ticker/24hr": 80, "ticker/bookTicker": 4, "klines": 2}

# Preserve the existing 90-second 30m-boundary entry gate. This is not a
# scheduler and never waits for a future market boundary.
CANDLE_ENTRY_WINDOW_SECONDS = 90


def boundary_preflight(epoch_seconds, *, boundary_ms=None):
    """Public pure gate: evaluate the real 30m boundary before any HTTP."""
    if boundary_ms is None:
        boundary_ms = int(epoch_seconds * 1000) // 1800000 * 1800000
    age_s = epoch_seconds - boundary_ms / 1000
    remaining_s = CANDLE_ENTRY_WINDOW_SECONDS - age_s
    admitted = 0 <= age_s <= CANDLE_ENTRY_WINDOW_SECONDS
    return dict(boundary_ms=boundary_ms, age_seconds=round(age_s, 3),
                remaining_seconds=round(max(0.0, remaining_s), 3),
                freshness_window_seconds=CANDLE_ENTRY_WINDOW_SECONDS,
                admitted=admitted,
                status="WITHIN_CANDLE_ENTRY_WINDOW" if admitted
                       else "CANDLE_ENTRY_WINDOW_EXPIRED")


class PublicCapture:
    def __init__(self, root, *, opener=None, monotonic=time.monotonic):
        self.root = Path(root)
        self.opener = opener or build_opener(ProxyHandler({}), NoRedirect())
        self.monotonic = monotonic
        self.start = monotonic()
        self.weight = self.attempts = self.bytes = 0
        self.used = 0
        self.receipts = []

    def record(self, row):
        with (self.root/"requests.jsonl").open("ab") as stream:
            stream.write(canonical(row)+b"\n")
            stream.flush()
            os.fsync(stream.fileno())

    def healthy(self):
        return (self.monotonic()-self.start < MAX_SECONDS
                and self.attempts < MAX_REQUESTS and self.used < MAX_USED_WEIGHT
                and self.bytes < MAX_TOTAL_BODY)

    def get(self, path, params):
        if path not in WEIGHTS:
            raise ValueError("ENDPOINT_NOT_ALLOWED")
        units = WEIGHTS[path]
        if (not self.healthy() or self.weight + units > MAX_WEIGHT
                or self.used + units > MAX_USED_WEIGHT):
            raise PauseScan("BUDGET_OR_HEADROOM_STOP")
        allowed = ({}, {"showPermissionSets": "false"}) if path == "exchangeInfo" else ({},)
        if path != "klines" and params not in allowed:
            raise ValueError("UNFILTERED_DISCOVERY_REQUIRED")
        self.attempts += 1
        self.weight += units
        row = dict(attempt=self.attempts, path=path, params=params, started_at=now(),
                   estimated_weight=units, state="RESERVED")
        self.record(row)
        url = BASE + "/api/v3/" + path + ("?" + urlencode(params) if params else "")
        try:
            request = Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache"})
            with self.opener.open(request, timeout=min(8, MAX_SECONDS-(self.monotonic()-self.start))) as response:
                status = response.status
                header = response.headers.get("X-MBX-USED-WEIGHT-1M")
                raw = response.read(min(MAX_BODY, MAX_TOTAL_BODY-self.bytes)+1)
        except HTTPError as exc:
            self.record({**row, "state": "HTTP_STOP", "http_status": exc.code})
            exc.close()
            raise PauseScan("HTTP_STOP") from None
        except (URLError, TimeoutError, OSError):
            self.record({**row, "state": "NETWORK_OR_HTTP_STOP"})
            raise PauseScan("NETWORK_OR_HTTP_STOP") from None
        if isinstance(header, str) and header.isascii() and header.isdecimal() and len(header) <= 9:
            self.used = int(header)
        self.bytes += len(raw)
        private = self.root / ("response-" + str(self.attempts) + ".private")
        private.write_bytes(raw)
        meta = {**row, "state": "RECEIVED", "received_at": now(), "http_status": status,
                "body_sha256": digest(raw), "body_bytes": len(raw), "used_weight_1m": header}
        self.record(meta)
        if (status != 200 or not isinstance(header, str) or not header.isascii()
                or not header.isdecimal() or len(header) > 9
                or len(raw) > MAX_BODY or self.bytes > MAX_TOTAL_BODY):
            raise PauseScan("UNVERIFIED_RESPONSE_OR_SIZE")
        self.used = int(header)
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            raise PauseScan("INVALID_JSON") from None
        receipt = dict(path=path, params=params, payload=payload, received_at=meta["received_at"],
                       body_sha256=meta["body_sha256"])
        self.receipts.append(receipt)
        if self.used > MAX_USED_WEIGHT or not self.healthy():
            raise PauseScan("QUOTA_OR_DEADLINE_STOP")
        return receipt


def discovery_only(receipt):
    """Derive complete listing metadata after a quota stop; no market eligibility."""
    if (receipt["path"] != "exchangeInfo"
            or receipt["params"] not in ({}, {"showPermissionSets": "false"})):
        raise ValueError("UNFILTERED_EXCHANGE_INVENTORY_REQUIRED")
    symbols = receipt["payload"]["symbols"]
    if not isinstance(symbols, list) or not 1 <= len(symbols) <= 20000:
        raise ValueError("DISCOVERY_RESOURCE_BOUND")
    seen = set()
    rows = []
    for row in symbols:
        symbol = row["symbol"]
        if symbol in seen or symbol != row["baseAsset"] + row["quoteAsset"]:
            raise ValueError("DISCOVERY_IDENTITY_INVALID")
        seen.add(symbol)
        spot = is_spot_enabled(row)
        rows.append(dict(symbol=symbol, base=row["baseAsset"], quote=row["quoteAsset"],
                         spot=spot, active=spot and row["status"] == "TRADING",
                         eligibility="UNKNOWN",
                         reason=("UNSUPPORTED_QUOTE_POLICY" if row["quoteAsset"] != "USDT"
                                 else "TICKER_AND_BOOK_NOT_OBSERVED"),
                         scan_state="UNSCANNED"))
    rows.sort(key=lambda row: row["symbol"])
    return dict(scope="ALL_BINANCE_INSTRUMENTS_RETURNED_WITH_EXPLICIT_SPOT_FLAGS",
                received_at=receipt["received_at"], body_sha256=receipt["body_sha256"],
                discovered=len(rows), spot_discovered=sum(r["spot"] for r in rows),
                active_spot=sum(r["active"] for r in rows),
                supported_eligible="NOT_ESTABLISHED",
                actually_evaluated=0, coverage="MARKET_COVERAGE_PARTIAL", rows=rows)


def run(root, cursor, *, transport=None, admin_clock_pilot=False):
    # Owner-approved P0 is a single 120s elevated foreground experiment ONLY.
    # No normal-user process may trust an admin JSON report from writable D:.
    from .ops_windows_time import CANDIDATE, POLICY_ID, SOURCE, REVIEWED_POLICY_SHA256
    policy = None
    if admin_clock_pilot:
        if not _is_admin():
            raise PermissionError("CLOCK_PILOT_ADMIN_CONTEXT_REQUIRED")
        policy = {"policy_id": POLICY_ID, "source": SOURCE, "limits": CANDIDATE}
        if digest(canonical(policy)) != REVIEWED_POLICY_SHA256:
            raise PermissionError("CLOCK_PILOT_REVIEWED_POLICY_PIN_MISMATCH")
    root = Path(root)
    transport = transport or PublicCapture(root)
    result = dict(status="MARKET_COVERAGE_PARTIAL", qualification="QV1_REAL_POLICY_BLOCKED",
                  live_e2e="LIVE_E2E_NOT_PROVEN", source="BINANCE_SPOT",
                  snapshot=None, funnel=None, stop=None)
    # Fail fast before expensive discovery, without modifying clock/source,
    # quota limits, or the existing 90s guard at each candle claim.
    # Existing 30m boundaries still govern packet identity.
    preflight = boundary_preflight(time.time())
    result["boundary_preflight"] = preflight
    if not preflight["admitted"]:
        result["stop"] = "CANDLE_ENTRY_WINDOW_EXPIRED_BEFORE_DISCOVERY"
        result["requests"] = transport.attempts
        result["estimated_weight"] = transport.weight
        result["body_bytes"] = transport.bytes
        result["observed_used_weight"] = transport.used
        result["receipt_manifest_sha256"] = digest(canonical(transport.receipts))
        (root/"result.json").write_bytes(canonical(result))
        return result
    try:
        for path in ("exchangeInfo", "ticker/24hr", "ticker/bookTicker"):
            transport.get(path, {"showPermissionSets": "false"} if path == "exchangeInfo" else {})
        snap = inventory(transport.receipts[:3], now(), scope="ALL_BINANCE_SPOT_INVENTORY")
        (root/"snapshot.private.json").write_bytes(canonical(snap))
        result["snapshot"] = {k: v for k, v in snap.items() if k not in ("rows",)}
        result["snapshot"]["rows"] = [{k: v for k, v in r.items() if k != "market"} for r in snap["rows"]]
        observations = {name: command(argv) for name, argv in COMMANDS.items()}
        for name, value in observations.items():
            (root/("time-" + name + ".private.json")).write_bytes(canonical(value))
        clock = assess(observations, sync_age_s=sync_age(observations["status"]["stdout"]), policy=policy)
        result["clock"] = {k: v for k, v in clock.items() if k != "last_successful_sync_display"}
        result["clock"]["pilot_mode"] = ("OWNER_APPROVED_BOUNDED_ELEVATED" if admin_clock_pilot
                                          else "NORMAL_USER_NO_WITNESS")
        result["clock"]["policy_sha256"] = (REVIEWED_POLICY_SHA256 if admin_clock_pilot else None)
        # No invented reviewed policy. Discovery is distinct from clock-admitted scans.
        boundary = preflight["boundary_ms"]
        result["boundary_preflight_at_scan"] = boundary_preflight(time.time(), boundary_ms=boundary)
        ledger = ScanLedger(cursor)
        scan = ledger.register(snap, boundary)

        def fetch(item):
            receipts = []
            for frame, period in FRAMES.items():
                # Never issue a candle GET after the original 30m entry window.
                if not boundary_preflight(time.time(), boundary_ms=boundary)["admitted"]:
                    raise PauseScan("CANDLE_ENTRY_WINDOW_EXPIRED")
                end = boundary // period * period
                receipts.append(transport.get("klines", dict(
                    symbol=item["symbol"], interval=frame, endTime=str(end-1),
                    limit="22" if frame == "5m" else "1")))
            return packet_from_receipts(item, receipts, boundary_ms=boundary, decision_at=now(),
                                        scope="PUBLIC_SPOT_CONDITIONAL_RESEARCH",
                                        clock_status="OPERATIONAL_TIME_ACCEPTED")

        if not result["boundary_preflight_at_scan"]["admitted"]:
            # Preserve the registered snapshot but never claim a pair or send
            # a candle GET after the entry window closes.
            result["funnel"] = ledger.report(scan, stopped="CANDLE_ENTRY_WINDOW_EXPIRED")
        else:
            result["funnel"] = ledger.chunk(
                scan, fetch, max_pairs=2,
                healthy=lambda: transport.healthy() and clock["status"] == "OPERATIONAL_TIME_ACCEPTED"
                and boundary_preflight(time.time(), boundary_ms=boundary)["admitted"],
                stop_reason=lambda: (
                    "CANDLE_ENTRY_WINDOW_EXPIRED"
                    if not boundary_preflight(time.time(), boundary_ms=boundary)["admitted"]
                    else "CLOCK_SOURCE_OR_BUDGET_UNHEALTHY"))
    except PauseScan as exc:
        result["stop"] = str(exc)
    except (ValueError, KeyError, TypeError):
        result["stop"] = "INVALID_SOURCE_INVENTORY"
    if result["snapshot"] is None and transport.receipts:
        try:
            result["discovery_only"] = discovery_only(transport.receipts[0])
        except (ValueError, KeyError, TypeError):
            result["discovery_only"] = {"status": "UNVERIFIED"}
    if result.get("funnel") and result["funnel"].get("stopped_reason"):
        result["stop"] = result["funnel"]["stopped_reason"]
    result["requests"] = transport.attempts
    result["estimated_weight"] = transport.weight
    result["body_bytes"] = transport.bytes
    result["observed_used_weight"] = transport.used
    result["receipt_manifest_sha256"] = digest(canonical(transport.receipts))
    (root/"result.json").write_bytes(canonical(result))
    return result
