"""Explicit one-shot order013 preregistered probe. No retries/system time changes."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import time
import urllib.request
from zs_smart_gate.stage03_source_clock import stamp, parse_ntp, validate_public_payload


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError('REDIRECT_FORBIDDEN')


def run(root):
    root.mkdir(exist_ok=False)
    result = dict(batch='013-SOURCE-CLOCK-1', ntp=[], market=[], bytes=0,
                  qualified_forward_observations=0, forward_armed=False)
    def save():
        (root/'report.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    for host in ('time.cloudflare.com', 'time.nist.gov'):
        rec = dict(host=host, status='ATTEMPTED', datagrams=0)
        result['ntp'].append(rec)
        try:
            address = socket.getaddrinfo(host, 123, socket.AF_INET, socket.SOCK_DGRAM)[0][4]
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(3)
                sock.connect(address)
                t1, m1 = time.time(), time.monotonic()
                tx = stamp(t1)
                request = b'\x23'+b'\0'*39+tx
                (root/(host+'.request')).write_bytes(request)
                sock.send(request)
                rec['datagrams'] = 1
                raw = sock.recv(513)
                t4, m4 = time.time(), time.monotonic()
            (root/(host+'.reply')).write_bytes(raw)
            rec.update(raw_sha256=hashlib.sha256(raw).hexdigest(), t1=t1, t4=t4,
                       monotonic_elapsed=m4-m1, analysis=parse_ntp(raw, tx, t1, t4, m4-m1), status='RECEIVED')
        except Exception as exc:
            rec.update(status='STOPPED_NO_RETRY', error_type=type(exc).__name__)
        save()
    opener = urllib.request.build_opener(NoRedirect())
    plan = [('time', None, '/api/v3/time', 1)]
    for symbol in ('BTCUSDT', 'ETHUSDT'):
        plan.extend([('bookTicker', symbol, '/api/v3/ticker/bookTicker?symbol='+symbol, 2),
                     ('24hr', symbol, '/api/v3/ticker/24hr?symbol='+symbol, 2),
                     ('klines', symbol, '/api/v3/klines?symbol='+symbol+'&interval=5m&limit=3', 2)])
    last, weight = 0, 0
    for endpoint, symbol, path, cost in plan:
        if weight+cost > 16:
            raise RuntimeError('WEIGHT_CAP')
        time.sleep(max(0, 1-(time.monotonic()-last)))
        rec = dict(endpoint=endpoint, symbol=symbol, status='ATTEMPTED', reserved_weight=cost)
        result['market'].append(rec)
        weight += cost
        try:
            last = time.monotonic()
            rec['requested_at'] = time.time()
            with opener.open('https://api.binance.com'+path, timeout=5) as response:
                rec['http'] = response.status
                if response.status != 200:
                    raise ValueError('HTTP_NOT_200')
                raw = response.read(65537)
            rec['received_at'] = time.time()
            if len(raw) > 65536 or result['bytes']+len(raw) > 262144:
                raise ValueError('RESPONSE_CAP')
            result['bytes'] += len(raw)
            (root/(str(len(result['market']))+'-'+endpoint+'.raw')).write_bytes(raw)
            rec.update(status='RECEIVED', raw_sha256=hashlib.sha256(raw).hexdigest(),
                       validation=validate_public_payload(endpoint, json.loads(raw), symbol))
        except Exception as exc:
            rec.update(status='STOPPED_NO_RETRY', error_type=type(exc).__name__)
            save()
            break
        save()
    result['weight_reserved'] = weight
    save()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-published-probe', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not args.run_published_probe:
        raise SystemExit('NOT_ARMED_ZERO_LIVE_CAPTURE')
    root = Path(args.output).resolve()
    run(root)
