"""Bounded read-only Spot verification. Importing this module performs no I/O."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

from .binance_live import BASE, FIVE_MS, LiveFailure, is_spot_enabled, timestamp
from .e2e51 import NoRedirect
from .mtf_contracts import CandleWindow
from .stage05_contracts import ContractError, digest, parse_utc

SYMBOLS = ("BTCUSDT", "ETHUSDT")
PLAN = (("time", 1), ("exchangeInfo", 20), ("klines", 2), ("klines", 2), ("time", 1))
MAX_WEIGHT = 40
MAX_SECONDS = 120
MAX_USED_WEIGHT = 200  # conservative operator-side threshold, not an exchange limit
MAX_BODY = 262144


def public_get(path, params, timeout):
    """No proxies, redirects or retries. The caller supplies the exact route."""
    url = BASE + "/api/v3/" + path
    if params:
        url += "?" + urlencode(params)
    request = Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache"})
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=timeout) as response:
            return response.status, response.headers.get("X-MBX-USED-WEIGHT-1M"), response.read(MAX_BODY+1)
    except HTTPError as exc:
        exc.close()
        return exc.code, None, b""
    except (URLError, TimeoutError, OSError):
        raise ContractError("OPS_NETWORK_UNAVAILABLE") from None


def run_preflight(*, get, monotonic, utc_now, record):
    """Execute once with injected transport and durable attempt receipt callback."""
    start = monotonic()
    attempts = weight = 0
    anchor = server_before = None
    status = "SOURCE_READBACK_PASS_CLOCK_PENDING"
    for index, (path, units) in enumerate(PLAN):
        remaining = MAX_SECONDS - (monotonic() - start)
        if remaining <= 0 or weight + units > MAX_WEIGHT:
            status = "OPS_BUDGET_STOP"
            break
        params = {}
        if path == "exchangeInfo":
            params["symbols"] = json.dumps(SYMBOLS, separators=(",", ":"))
        elif path == "klines":
            params = {"symbol": SYMBOLS[index-2], "interval": "5m",
                      "limit": "1", "endTime": str(anchor-1)}
        attempts += 1
        weight += units
        entry = {"attempt":attempts, "path":path, "params":params,
                 "estimated_weight":units, "started_at":utc_now()}
        record({**entry, "state":"ATTEMPT_RESERVED"})
        try:
            http_status, used_weight, raw = get(path, params, min(5, remaining))
            received = utc_now()
            if monotonic() - start >= MAX_SECONDS:
                raise ContractError("OPS_BUDGET_STOP")
            if http_status != 200:
                raise ContractError("OPS_HTTP_" + str(http_status))
            if not isinstance(raw, bytes) or len(raw) > MAX_BODY:
                raise ContractError("OPS_RESPONSE_SIZE_OR_TYPE")
            if (not isinstance(used_weight, str) or not used_weight.isascii()
                    or not used_weight.isdecimal() or len(used_weight) > 9
                    or int(used_weight) > MAX_USED_WEIGHT):
                raise ContractError("OPS_QUOTA_HEADROOM_UNVERIFIED")
            body = json.loads(raw)
            if path == "time":
                server = body["serverTime"]
                if type(server) is not int or server <= 0:
                    raise ContractError("OPS_SERVER_TIME_INVALID")
                if index == 0:
                    server_before = server
                    anchor = server // FIVE_MS * FIVE_MS
                elif not server_before <= server <= server_before + MAX_SECONDS*1000:
                    raise ContractError("OPS_SERVER_TIME_INCONSISTENT")
            elif path == "exchangeInfo":
                symbols = body["symbols"]
                if (not isinstance(symbols, list) or len(symbols) != len(SYMBOLS)
                        or {row["symbol"] for row in symbols} != set(SYMBOLS)
                        or any(row.get("quoteAsset") != "USDT" or row.get("status") != "TRADING"
                               or not is_spot_enabled(row) for row in symbols)):
                    raise ContractError("OPS_SPOT_SCOPE_INVALID")
            elif (not isinstance(body, list) or len(body) != 1 or not isinstance(body[0], list)
                  or len(body[0]) < 11 or type(body[0][0]) is not int or type(body[0][6]) is not int
                  or body[0][0] != anchor-FIVE_MS or body[0][6] != anchor-1):
                raise ContractError("OPS_CLOSED_CANDLE_INVALID")
            if path == "klines":
                bar = body[0]
                at = parse_utc(received)
                candle = CandleWindow("5m", timestamp(bar[0]), timestamp(anchor), at, at,
                                      "BINANCE_SPOT_PUBLIC_REST", *bar[1:6], bar[7])
                if candle.errors_at(at):
                    raise ContractError("OPS_CANDLE_OHLCV_OR_LOCAL_TIME_INVALID")
            record({**entry, "state":"VALIDATED", "received_at":received, "http_status":http_status,
                    "used_weight_1m":int(used_weight), "response_sha256":digest(raw)})
        except ContractError as exc:
            status = str(exc)
            record({**entry, "state":"STOPPED", "reason":status})
            break
        except (ValueError, KeyError, TypeError, AttributeError, ArithmeticError, LiveFailure):
            status = "OPS_RESPONSE_INVALID"
            record({**entry, "state":"STOPPED", "reason":status})
            break
    return {"status":status, "requests":attempts, "estimated_weight":weight,
            "independent_clock":"NOT_VERIFIED", "readiness":"NOT_READY"}
