"""B1 source acquisition: bounded concurrency, one inventory/boundary/decision."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import closing
from datetime import datetime, timezone
import json
import http.client
import ssl
import threading
import math
import os
from pathlib import Path
import time
from urllib.parse import urlencode,urlsplit

from .binance_live import BASE
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


_connections=threading.local()


def public_get(path, params, timeout, limit):
    """One TLS connection per worker; no redirect, proxy or application retry."""
    origin=urlsplit(BASE)
    if origin.scheme!="https" or origin.hostname!="data-api.binance.vision" or origin.port is not None:
        raise Hold("UNAPPROVED_SOURCE_ORIGIN")
    connection=getattr(_connections,"connection",None)
    if connection is None:
        connection=http.client.HTTPSConnection(origin.hostname,timeout=timeout,
                                               context=ssl.create_default_context())
        _connections.connection=connection
    connection.timeout=timeout
    if connection.sock is not None:
        connection.sock.settimeout(timeout)
    target="/api/v3/"+path+("?"+urlencode(params) if params else "")
    try:
        connection.request("GET",target,headers={"Accept":"application/json","Cache-Control":"no-cache"})
        response=connection.getresponse()
        raw=response.read(limit+1)
        status,headers=response.status,dict(response.getheaders())
        if len(raw)>limit or response.will_close:
            connection.close()
        return status,headers,raw
    except (http.client.HTTPException,TimeoutError,OSError):
        connection.close()
        raise Hold("TRANSPORT_UNKNOWN_NO_REISSUE") from None


class Client:
    def __init__(self, budget, *, get=public_get, guard=lambda: False, stamp=now, clock_receipt=lambda: None, capacity=lambda:2):
        self.budget, self.transport, self.guard, self.stamp = budget, get, guard, stamp
        self.clock_receipt=clock_receipt
        self.capacity=capacity

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
                self.budget.adopt_limits(payload['rateLimits'])
            except Hold as exc:
                reason=str(exc)
            except (ValueError,KeyError,TypeError):
                reason="UNVERIFIED_SERVER_RATE_LIMIT"
        receipt["rate_headers"]={k:v for k,v in headers.items() if k.lower().startswith("x-mbx-used-") or k.lower() in ("retry-after","date")}
        receipt["received_clock"]=self.clock_receipt()
        atomic(self.budget.root/(key+".receipt.json"),canonical(receipt))
        self.budget.finish(key,limit,receipt,reason=reason)
        return {**receipt,"payload":payload}


def discover(client):
    receipts = [client.get(path, {"showPermissionSets":"false"} if path=="exchangeInfo" else {})
                for path in ("exchangeInfo","ticker/24hr","ticker/bookTicker")]
    return receipts, inventory(receipts,client.stamp(),scope="ALL_BINANCE_SPOT_INVENTORY")


def scan(client, *, boundary_ms, wall=time.time, stamp=now, release=None):
    """Cohort freeze before candles, complete revalidation at a common decision."""
    budget = client.budget
    result = dict(transport_profile="REST_HTTPS_KEEPALIVE_THREAD_LOCAL_V1",version=budget.policy.version,policy_sha256=budget.policy.sha256,
                  head=release["head"] if release else None,tree=release["tree"] if release else None,
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
        discovery, snapshot = discover(client)
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
        # Use warm persistent-connection latency, not the initial TLS setup.
        warm=[(r['received_mono_ns']-r['started_mono_ns'])/1e9 for r in discovery[1:]
              if 'received_mono_ns' in r and 'started_mono_ns' in r]
        estimate=max(warm,default=1)
        remaining=min(budget.remaining(),budget.policy.freshness_seconds-(wall()-boundary_ms/1000))-15
        needed=max(2,math.ceil(4*len(eligible)*estimate/max(1,remaining)))
        chosen=min(client.capacity(),needed,budget.policy.max_bytes//(budget.policy.candle_body+1))
        budget.set_workers(chosen)
        result['worker_selection']=dict(chosen=chosen,needed=needed,warm_latency_seconds=estimate,
                                        available_causal_seconds=remaining)

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
        with ThreadPoolExecutor(max_workers=chosen) as pool:
            queue = iter(eligible)
            pending = {}
            def submit():
                item = next(queue,None)
                if item is not None and not budget.state()["halt"]:
                    pending[pool.submit(fetch,item)] = item["symbol"]
            for _ in range(chosen):
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
