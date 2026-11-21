"""B1 source acquisition: bounded concurrency, one inventory/boundary/decision."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import closing
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

from .binance_live import BASE
from .e2e51 import NoRedirect
from .marketwide_research import FRAMES, inventory, packet_from_receipts, evaluate
from .stage05_contracts import canonical, digest
from .ops24_budget import Budget, Hold


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic(path, data):
    path = Path(path)
    temp = path.with_name(path.name+".partial")
    with temp.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def public_get(path, params, timeout, limit):
    url = BASE+"/api/v3/"+path+("?" + urlencode(params) if params else "")
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(
                Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache"}),
                timeout=timeout) as response:
            return response.status, dict(response.headers), response.read(limit+1)
    except HTTPError as exc:
        headers = dict(exc.headers)
        code = exc.code
        exc.close()
        return code, headers, b""
    except (URLError, TimeoutError, OSError):
        raise Hold("TRANSPORT_UNKNOWN_NO_REISSUE") from None


class Client:
    def __init__(self, budget, *, get=public_get, guard=lambda: False, stamp=now, clock_receipt=lambda: None):
        self.budget, self.transport, self.guard, self.stamp = budget, get, guard, stamp
        self.clock_receipt=clock_receipt

    def get(self, path, params):
        if not self.guard():
            raise Hold(self.budget.state()["halt"] or "CLOCK_STOP_OR_SOURCE_GUARD")
        key, limit, cached = self.budget.reserve(path, params)
        if cached is not None:
            raw = (self.budget.root/(key+".private")).read_bytes()
            return {**cached, "payload": json.loads(raw)}
        receipt = dict(path=path,params=params,started_at=self.stamp(),started_mono_ns=time.monotonic_ns(),
                       started_clock=self.clock_receipt(),http_attempted=False)
        if not self.guard():
            reason=self.budget.state()["halt"] or "CLOCK_STOP_BEFORE_HTTP"
            self.budget.finish(key,limit,{**receipt,"body_bytes":0},reason=reason)
            raise Hold(reason)
        receipt.update(started_at=self.stamp(),started_mono_ns=time.monotonic_ns(),
                       started_clock=self.clock_receipt(),http_attempted=True)
        try:
            status, headers, raw = self.transport(
                path, params, max(.001,min(self.budget.policy.request_timeout,self.budget.remaining())),limit)
        except Hold as exc:
            self.budget.finish(key,limit,receipt,reason=str(exc))
            raise
        except (OSError, TimeoutError):
            self.budget.finish(key,limit,receipt,reason="TRANSPORT_UNKNOWN_NO_REISSUE")
            raise Hold("TRANSPORT_UNKNOWN_NO_REISSUE") from None
        receipt.update(received_at=self.stamp(),received_mono_ns=time.monotonic_ns(),http_status=status,body_bytes=len(raw),
                       body_sha256=digest(raw))
        atomic(self.budget.root/(key+".private"), raw)
        header = next((v for k,v in headers.items() if k.lower()=="x-mbx-used-weight-1m"), None)
        reason = None
        if isinstance(header,str) and header.isascii() and header.isdecimal() and len(header)<=9:
            receipt["used_weight_1m"] = int(header)
        else:
            reason = "UNVERIFIED_WEIGHT_HEADER"
        if status in (429,418):
            reason = "HTTP_"+str(status)+"_BACKOFF"
            receipt["retry_after"] = next((v for k,v in headers.items() if k.lower()=="retry-after"), None)
        elif status != 200:
            reason = "HTTP_ERROR_STOP"
        elif len(raw)>limit:
            reason = "BODY_CAP"
        elif not self.guard():
            reason = self.budget.state()["halt"] or "CLOCK_STOP_OR_SOURCE_GUARD"
        try:
            payload = json.loads(raw) if reason is None else None
        except (ValueError,UnicodeError):
            reason, payload = "INVALID_JSON", None
        if reason is None and path=="exchangeInfo":
            try:
                limits=[r["limit"] for r in payload["rateLimits"]
                        if r["rateLimitType"]=="REQUEST_WEIGHT" and r["interval"]=="MINUTE"
                        and r["intervalNum"]==1]
                if len(limits)!=1:
                    raise Hold("UNVERIFIED_SERVER_RATE_LIMIT")
                self.budget.adopt_server_limit(limits[0])
            except (Hold,ValueError,KeyError,TypeError):
                reason="UNVERIFIED_SERVER_RATE_LIMIT"
        receipt["received_clock"]=self.clock_receipt()
        atomic(self.budget.root/(key+".receipt.json"),canonical(receipt))
        self.budget.finish(key,limit,receipt,reason=reason)
        return {**receipt,"payload":payload}


def discover(client):
    receipts = [client.get(path, {"showPermissionSets":"false"} if path=="exchangeInfo" else {})
                for path in ("exchangeInfo","ticker/24hr","ticker/bookTicker")]
    return receipts, inventory(receipts,client.stamp(),scope="ALL_BINANCE_SPOT_INVENTORY")


def scan(client, *, boundary_ms, wall=time.time, stamp=now):
    """Cohort freeze before candles, complete revalidation at a common decision."""
    budget = client.budget
    result = dict(version=budget.policy.version,policy_sha256=budget.policy.sha256,
                  boundary_ms=boundary_ms,scope="SHADOW_RESEARCH_ONLY",
                  coverage="BLOCKED",qualification="QV1_REAL_POLICY_BLOCKED",
                  signal_ids=[],telegram_calls=0,sql_writes=0,stop=None,rows=[])
    result_path = budget.root/"result.json"
    pin_path = budget.root/"result.sha256"
    if result_path.exists():
        if not pin_path.exists() or digest(result_path.read_bytes()) != pin_path.read_text().strip():
            raise Hold("RESULT_READBACK_CORRUPTION")
        return json.loads(result_path.read_bytes())
    packets = {}
    eligible = []
    try:
        age = wall()-boundary_ms/1000
        if not 0<=age<=budget.policy.freshness_seconds:
            raise Hold("BOUNDARY_ENTRY_EXPIRED")
        _, snapshot = discover(client)
        inventory_path = budget.root/"inventory.private.json"
        if inventory_path.exists():
            frozen = json.loads(inventory_path.read_bytes())
            if frozen["source_manifest_sha256"] != snapshot["source_manifest_sha256"]:
                raise Hold("FROZEN_INVENTORY_DRIFT")
            snapshot = frozen
        else:
            atomic(inventory_path,canonical(snapshot))
        result["inventory_id"] = snapshot["snapshot_sha256"]
        result["discovered"] = len(snapshot["rows"])
        eligible = [row for row in snapshot["rows"] if row["eligible"]]
        result["eligible"] = len(eligible)
        if not eligible:
            raise Hold("EMPTY_ELIGIBLE_SCOPE")
        budget.freeze_universe(len(eligible))
        def fetch(item):
            receipts = []
            for frame,period in FRAMES.items():
                if wall()-boundary_ms/1000 > budget.policy.freshness_seconds:
                    raise Hold("BOUNDARY_DEADLINE")
                end = boundary_ms//period*period
                receipts.append(client.get("klines",dict(symbol=item["symbol"],interval=frame,
                    endTime=str(end-1),limit="22" if frame=="5m" else "1")))
            return packet_from_receipts(item,receipts,boundary_ms=boundary_ms,decision_at=stamp(),
                scope="PUBLIC_SPOT_CONDITIONAL_RESEARCH",clock_status="OPERATIONAL_TIME_ACCEPTED")
        with ThreadPoolExecutor(max_workers=budget.policy.workers) as pool:
            queue = iter(eligible)
            pending = {}
            def submit():
                item = next(queue,None)
                if item is not None and not budget.state()["halt"]:
                    pending[pool.submit(fetch,item)] = item["symbol"]
            for _ in range(budget.policy.workers):
                submit()
            while pending:
                done,_ = wait(pending,return_when=FIRST_COMPLETED)
                for future in done:
                    symbol = pending.pop(future)
                    try:
                        packets[symbol] = future.result()
                    except (Hold,ValueError,KeyError,TypeError) as exc:
                        budget.stop(str(exc) if isinstance(exc,Hold) else "SOURCE_PACKET_INVALID")
                    if not budget.state()["halt"]:
                        submit()
        if budget.state()["halt"]:
            result["stop"] = budget.state()["halt"]
        if not client.guard() or not 0<=wall()-boundary_ms/1000<=budget.policy.freshness_seconds:
            raise Hold("FINAL_CLOCK_OR_FRESHNESS")
        decision = stamp()
        for item in eligible:
            symbol = item["symbol"]
            packet = packets.get(symbol)
            if packet is None:
                result["rows"].append(dict(symbol=symbol,state="MISSING_OR_UNKNOWN",directions=[]))
                continue
            packet = {**packet,"decision_at":decision}
            rows = evaluate(packet)
            result["rows"].append(dict(symbol=symbol,state="VALIDATED" if all(
                r["source_validated"] for r in rows) else "DATA_INVALID",directions=rows,
                input_sha256=digest(canonical(packet))))
        result["decision_at"] = decision
        result["decision_clock"]=client.clock_receipt()
        result["validated"] = sum(row["state"]=="VALIDATED" for row in result["rows"])
        result["missing"] = len(eligible)-result["validated"]
        result["coverage"] = ("MARKET_COVERAGE_VERIFIED" if
            result["validated"]==len(eligible) and result["stop"] is None else "MARKET_COVERAGE_PARTIAL")
    except (Hold,ValueError,KeyError,TypeError) as exc:
        reason = str(exc) if isinstance(exc,Hold) else "SOURCE_SCHEMA_INVALID"
        budget.stop(reason)
        result.update(stop=reason,coverage="BLOCKED" if not packets else "MARKET_COVERAGE_PARTIAL")
    recorded = {row["symbol"] for row in result["rows"]}
    for item in eligible:
        if item["symbol"] not in recorded:
            result["rows"].append(dict(symbol=item["symbol"],state="UNKNOWN_OR_FINAL_GATE_HOLD",directions=[]))
    result["validated"] = sum(row["state"]=="VALIDATED" for row in result["rows"])
    result["missing"] = len(eligible)-result["validated"]
    result["expected_symbols"] = [row["symbol"] for row in eligible]
    result["received_symbols"] = sorted(packets)
    result["budget"] = budget.state()
    with closing(budget.open()) as db:
        audited=[json.loads(row[0]) for row in db.execute("SELECT receipt FROM requests WHERE receipt IS NOT NULL")]
    latency=sorted((r["received_mono_ns"]-r["started_mono_ns"])/1e9 for r in audited
                   if "received_mono_ns" in r and "started_mono_ns" in r)
    result["metrics"]=dict(requests_measured=len(latency),
        known_transport_attempts=sum(row.get("http_attempted",False) for row in audited),
        unresolved_requests=result["budget"]["active"],
        mean_request_seconds=sum(latency)/len(latency) if latency else None,
        p95_request_seconds=latency[math.ceil(.95*len(latency))-1] if latency else None,
        capture_seconds=budget.mono()-result["budget"]["started"])
    atomic(result_path,canonical(result))
    atomic(pin_path,(digest(canonical(result))+"\n").encode())
    return result
