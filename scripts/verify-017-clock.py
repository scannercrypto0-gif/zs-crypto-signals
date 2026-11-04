"""Offline independent check of published signed samples; no network/import I/O."""
import base64
import hashlib
import json
from pathlib import Path
import sys
from zs_smart_gate.clock017 import verify, local_interval, request


def check(path):
    records = json.loads(Path(path).read_text(encoding='utf-8'))
    results = []
    for row in records:
        raw = base64.b64decode(row['response_b64'], validate=True)
        if hashlib.sha256(raw).hexdigest() != row['response_sha256']:
            raise ValueError('RESPONSE_SHA_CHANGED')
        # Pin the reviewed source, never trust an arbitrary key in input JSON.
        key = base64.b64decode('0GD7c3yP8xEc4Zl2zeuN2SlLvDVVocjsPSL8/Rl/7zg=')
        nonce = base64.b64decode(row['nonce_b64'], validate=True)
        if base64.b64decode(row['request_b64'], validate=True) != request(nonce, key):
            raise ValueError('REQUEST_CHANGED')
        sample = verify(raw, nonce, key)
        interval = local_interval(sample, sent_wall=row['sent_wall'], received_wall=row['received_wall'],
                                  elapsed=(row['received_mono_ns']-row['sent_mono_ns'])/1e9)
        results.append(dict(index=row['index'], verification=sample, interval=interval,
                            rtt_seconds=(row['received_mono_ns']-row['sent_mono_ns'])/1e9))
    if len(results) != 2:
        raise ValueError('EXPECTED_TWO_SAMPLES')
    # Measurement of net rate over these two endpoints is descriptive only:
    # source uncertainties bound it very loosely; no worst-case future ppm.
    dt = (records[1]['received_mono_ns']-records[0]['received_mono_ns'])/1e9
    observed = (records[1]['received_wall']-records[0]['received_wall'])/dt-1
    return dict(status='HOLD', results=results, observed_wall_vs_mono_ppm=observed*1e6,
                maximum_future_drift_proved=False, forward_armed=False,
                historical_publisher_pit='HOLD')


if __name__ == '__main__':
    manifest = Path(sys.argv[1]).parent/'manifest.json'
    for name, sha in json.loads(manifest.read_text(encoding='utf-8')).items():
        if Path(name).name != name or hashlib.sha256((manifest.parent/name).read_bytes()).hexdigest() != sha:
            raise ValueError('EVIDENCE_MANIFEST_CHANGED')
    print(json.dumps(check(sys.argv[1]), sort_keys=True, indent=2))
