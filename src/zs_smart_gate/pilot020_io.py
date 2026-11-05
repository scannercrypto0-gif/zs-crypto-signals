"""Explicit one-shot native transports; import has zero network/credential I/O.

REST in killed-at-deadline subprocesses bounds DNS/TLS/body time. WS has no
reconnect and counts decrypted wire bytes before library frame assembly.
"""
import base64
import http.client
import json
import os
import subprocess
import ssl
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor,as_completed,TimeoutError as FutureTimeout
from .pilot020 import WS_URL


class WireCapSocket:
    def __init__(self,sock,budget):self.sock=sock;self.budget=budget
    def __getattr__(self,name):return getattr(self.sock,name)
    def recv(self,n,*args):
        left=2097152-self.budget.wire
        if left<=0:raise ValueError('WS_RAW_CAP_BEFORE_READ')
        raw=self.sock.recv(min(n,left),*args);self.budget.wire_received(len(raw));return raw


class WebSocketOnce:
    def __init__(self,budget):self.budget=budget;self.ws=None;self.fragment=b'';self.pongs=[]
    def connect(self):
        import websocket
        self.budget.connect()
        self.ws=websocket.create_connection(WS_URL,timeout=1,redirect_limit=0,
             enable_multithread=True,skip_utf8_validation=False,http_no_proxy=['data-stream.binance.vision'],
             sslopt={'cert_reqs':ssl.CERT_REQUIRED,'check_hostname':True})
        if self.ws.handshake_response.status!=101:
            self.ws.shutdown();raise ValueError('WS_REDIRECT_OR_UPGRADE_NOT_ACCEPTED')
        self.ws.sock=WireCapSocket(self.ws.sock,self.budget)
        original=self.ws.frame_buffer.recv_length
        def bounded_length():
            original()
            if self.ws.frame_buffer.has_mask() or self.ws.frame_buffer.length>8192-len(self.fragment):
                raise ValueError('WS_MASK_OR_STRICT_8K_MESSAGE_GUARD')
        self.ws.frame_buffer.recv_length=bounded_length
    def receive(self):
        import websocket
        try:
            frame=self.ws.recv_frame();opcode=frame.opcode
            mono=time.monotonic_ns();wall=time.time_ns()
            if opcode==websocket.ABNF.OPCODE_CLOSE:raise ValueError('WS_CLOSED_NO_RECONNECT')
            if opcode==websocket.ABNF.OPCODE_PING:
                now=time.monotonic();self.pongs=[t for t in self.pongs if now-t<1]
                if len(self.pongs)>=4:raise ValueError('PING_FLOOD_STOP_BEFORE_PROVIDER_LIMIT')
                self.pongs.append(now);self.ws.pong(frame.data)
                return None,mono,wall
            if opcode==websocket.ABNF.OPCODE_PONG:return None,mono,wall
            if opcode not in (websocket.ABNF.OPCODE_TEXT,websocket.ABNF.OPCODE_CONT):raise ValueError('WS_NON_TEXT_SCOPE')
            if (opcode==websocket.ABNF.OPCODE_TEXT and self.fragment) or (opcode==websocket.ABNF.OPCODE_CONT and not self.fragment):
                raise ValueError('INVALID_FRAGMENT_SEQUENCE')
            self.budget.data_frame()  # stricter cap also prevents fragment floods
            self.fragment+=frame.data
            if not frame.fin:return None,mono,wall
            raw=self.fragment;self.fragment=b'';self.budget.message()
            if not isinstance(raw,bytes):raw=raw.encode('utf-8')
            return raw,mono,wall
        except websocket.WebSocketTimeoutException:return None,time.monotonic_ns(),time.time_ns()
    def close(self):
        if self.ws is not None:self.ws.shutdown()
    def partial(self):
        pending=b''.join(self.ws.frame_buffer.recv_buffer) if self.ws is not None else b''
        return (self.fragment+pending)[:16384]


def public_gets(entries,*,on_attempt):
    """All six preclaimed fixed requests start once; zero retries/redirects.

    Concurrent starts keep book age meaningful. A failed response stops the
    batch; already dispatched requests remain counted, never silently replaced.
    """
    processes=[];results=[];completed=set();unavailable=[]
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    try:
        for entry in entries:
            on_attempt(entry)
            p=subprocess.Popen([sys.executable,'-m','zs_smart_gate.pilot020_io','--public-get'],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=flags)
            p.stdin.write(json.dumps(entry).encode());p.stdin.close()
            processes.append((p,time.monotonic()))
        def collect(item):
            p,start=item
            remaining=5-(time.monotonic()-start)
            if remaining<=0:raise TimeoutError('REST_TOTAL_DEADLINE')
            p.stdin=None
            output,error=p.communicate(timeout=remaining)
            if p.returncode!=0:raise ValueError('REST_CHILD_FAILED_NO_RETRY')
            return json.loads(output)
        pool=ThreadPoolExecutor(max_workers=6)
        futures={pool.submit(collect,item):i for i,item in enumerate(processes)}
        try:
            for future in as_completed(futures,timeout=5):
                i=futures[future]
                try:value=future.result()
                except Exception:
                    unavailable.append(dict(index=i,reason='TIMEOUT_OR_CHILD_FAILURE'));break
                completed.add(i)
                if 'raw_base64' in value:results.append(value)
                else:unavailable.append(dict(index=i,reason=value.get('error','UNKNOWN_RESPONSE')))
                if value.get('status')!=200 or value.get('error'):break
        except FutureTimeout:unavailable.append(dict(reason='BATCH_DEADLINE'))
        finally:
            for p,start in processes:
                if p.poll() is None:p.kill()
            pool.shutdown(wait=True,cancel_futures=True)
            # Retain any other completed replies already received on failure.
            for future,i in futures.items():
                if i in completed or not future.done() or future.cancelled():continue
                try:
                    value=future.result()
                    if 'raw_base64' in value:results.append(value);completed.add(i)
                except Exception:pass
            for i in range(6):
                if i not in completed:unavailable.append(dict(index=i,reason='CANCELLED_OR_RESPONSE_UNKNOWN_NO_RETRY'))
        return dict(results=results,unavailable=unavailable)
    finally:
        for p,start in processes:
            if p.poll() is None:p.kill();p.wait()


def child():
    from .pilot020 import REST_PLAN
    entry=json.loads(sys.stdin.buffer.read(4096));path,params,weight=entry
    if not any(path==p and params==q and weight==w for p,q,w in REST_PLAN):
        raise ValueError('UNAPPROVED_REST_CHILD_DESTINATION')
    result=dict(path=path,params=params,weight=weight,attempted=True)
    started=time.monotonic_ns()
    try:
        conn=http.client.HTTPSConnection('data-api.binance.vision',443,timeout=4.5)
        target=path+('?' + urllib.parse.urlencode(params) if params else '')
        sent=time.monotonic_ns();conn.request('GET',target,headers={'User-Agent':'zs-bounded020','Connection':'close'})
        # Six concurrent32KiB reservations sum to192KiB, below the256KiB
        # aggregate cap even if every response is hostile. Stop at the exact
        # stricter boundary without reading a cap+1 byte.
        response=conn.getresponse();raw=response.read(32768)
        received=time.monotonic_ns()
        result.update(status=response.status,raw_base64=base64.b64encode(raw).decode(),sent_mono_ns=sent,
            received_mono_ns=received,elapsed_seconds=(received-started)/1e9)
        if len(raw)==32768:result['error']='NATIVE32K_GUARD_PARTIAL_OR_EXACT_CAP_STOP'
        conn.close()
    except Exception as exc:result.update(error=type(exc).__name__)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    if sys.argv[1:]!=['--public-get']:raise SystemExit('INTERNAL_CHILD_ONLY')
    child()
