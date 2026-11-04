"""Explicit finite Roughtime experiment: two datagrams, no retries or clock edits.

Run only under order017. No market endpoints or credentials. Full signed replies
are public protocol material; unlike NTS cookies they can be independently checked.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time
from zs_smart_gate.clock017 import request, verify, local_interval

KEY = '0GD7c3yP8xEc4Zl2zeuN2SlLvDVVocjsPSL8/Rl/7zg='


def run(output):
    root = Path(output)
    root.mkdir(exist_ok=False)
    key = base64.b64decode(KEY)
    records = []
    for i in range(2):
        nonce = os.urandom(32)
        raw_request = request(nonce, key)
        entry = dict(index=i, host='roughtime.cloudflare.com', port=2003,
                     key_b64=KEY, nonce_b64=base64.b64encode(nonce).decode(),
                     request_b64=base64.b64encode(raw_request).decode(),
                     forward_armed=False, system_changes=False)
        try:
            # Connected UDP validates reply peer; DNS occurs before measurement.
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(3)
                sock.connect(('roughtime.cloudflare.com', 2003))
                entry['peer'] = sock.getpeername()[0]
                wall, mono = time.time(), time.monotonic_ns()
                entry.update(sent_wall=wall, sent_mono_ns=mono)
                sock.send(raw_request)
                entry['datagrams_sent'] = 1
                response = sock.recv(4097)
                end_mono, end_wall = time.monotonic_ns(), time.time()
            entry.update(received_wall=end_wall, received_mono_ns=end_mono,
                         response_b64=base64.b64encode(response).decode(),
                         response_sha256=hashlib.sha256(response).hexdigest())
            result = verify(response, nonce, key)
            entry.update(verification=result, interval=local_interval(result,
                         sent_wall=wall, received_wall=end_wall, elapsed=(end_mono-mono)/1e9))
        except Exception as exc:
            entry.update(status='HOLD', error_type=type(exc).__name__, error=str(exc)[:120])
        records.append(entry)
        (root/'samples.json').write_text(json.dumps(records, sort_keys=True, indent=2)+'\n', encoding='utf-8')
        if i == 0:
            time.sleep(30)
    return records


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[1]), sort_keys=True))
