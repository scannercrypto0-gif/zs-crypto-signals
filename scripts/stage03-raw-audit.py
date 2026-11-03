"""012 read-only local-byte audit, independent parser; no imports of research engine."""
import argparse
import calendar
from collections import defaultdict
import csv
from decimal import Decimal
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile


def hash_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def audit(root):
    frozen = root/'science-010B'/'reviewed-build'
    manifest = json.loads((frozen/'manifest.json').read_bytes())
    provider = json.loads((root/'science-010B'/'batch-B'/'report.json').read_bytes())
    index = {r['name']: r for r in json.loads((frozen/'dataset-index.json').read_bytes())}
    reported = {r['name']: r for r in provider['files']}
    bars = defaultdict(list)
    files = []
    for item in manifest['files']:
        p = frozen/'batch-B'/item['name']
        h = hash_file(p)
        if h != item['sha256'] or h != index[p.name]['sha256'] or h != reported[p.name]['sha256']:
            raise ValueError('ARCHIVE_IDENTITY_MISMATCH')
        seconds = {'5m': 300, '30m': 1800, '1h': 3600, '4h': 14400}[item['interval']]
        year, month = map(int, item['month'].split('-'))
        expected_rows = calendar.monthrange(year, month)[1]*86400//seconds
        start = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp())
        with zipfile.ZipFile(p) as z:
            infos = z.infolist()
            if len(infos) != 1 or infos[0].filename != p.name[:-4]+'.csv' or infos[0].file_size > 32_000_000:
                raise ValueError('ZIP_SCHEMA_OR_RESOURCE_LIMIT')
            n = 0
            with z.open(infos[0]) as stream:
                for row in csv.reader(io.TextIOWrapper(stream, encoding='utf8')):
                    if len(row) != 12 or int(row[0]) != (start+n*seconds)*1_000_000 or int(row[6]) != (start+(n+1)*seconds)*1_000_000-1:
                        raise ValueError('TIMESTAMP_UNITS_GAP_OR_BOUNDARY')
                    o, hi, lo, c, base, quote = [Decimal(row[i]) for i in [1, 2, 3, 4, 5, 7]]
                    if not all(v.is_finite() for v in [o, hi, lo, c, base, quote]) or not 0 < lo <= min(o, c) <= max(o, c) <= hi or min(base, quote) < 0:
                        raise ValueError('OHLCV_REJECTED')
                    bars[(item['symbol'], item['interval'])].append((start+n*seconds, o, hi, lo, c, base, quote))
                    n += 1
        if n != expected_rows or n != item['rows']:
            raise ValueError('MONTH_COVERAGE')
        files.append(dict(name=p.name, sha256=h, rows=n, integrity='LOCAL_MANIFEST_INDEX_ACQUISITION_RECORD_MATCH',
                          provider_checksum_body='NOT_RETAINED_IN_REVIEWED_BUILD'))
    mtf, contexts = {}, {}
    for symbol in ['BTCUSDT', 'ETHUSDT']:
        base = bars[(symbol, '5m')]
        for a, b in zip(base, base[1:]):
            if b[0]-a[0] != 300:
                raise ValueError('CROSS_MONTH_GAP')
        for frame, step in [('30m', 1800), ('1h', 3600), ('4h', 14400)]:
            parents = bars[(symbol, frame)]
            for i, parent in enumerate(parents):
                child = base[i*(step//300):(i+1)*(step//300)]
                merged = (child[0][0], child[0][1], max(v[2] for v in child), min(v[3] for v in child),
                          child[-1][4], sum(v[5] for v in child), sum(v[6] for v in child))
                if merged != parent:
                    raise ValueError('EXACT_PARENT_CHILD_MISMATCH')
            mtf[symbol+':'+frame] = len(parents)
        for name, duration, offset in [('DAILY', 86400, 0), ('ISO_MONDAY_WEEK', 604800, 345600)]:
            groups = defaultdict(list)
            for b in base:
                groups[(b[0]-offset)//duration*duration+offset].append(b)
            complete = [start for start, rows in groups.items() if rows[0][0] == start and len(rows)*300 == duration]
            contexts[symbol+':'+name] = dict(complete=len(complete), partial_discarded=len(groups)-len(complete),
                                           closed_before_decision_required=True)
    quotes = []
    for batch, symbol in [('science-010D', 'ETHUSDT'), ('science-010E', 'BTCUSDT')]:
        p = root/batch/(symbol+'.csv.gz')
        report = json.loads((root/batch/'report.json').read_bytes())
        if hash_file(p) != report['sha256']:
            raise ValueError('QUOTE_HASH_MISMATCH')
        n = fallback = 0
        previous = None
        with gzip.open(p, 'rt', newline='') as stream:
            for r in csv.DictReader(stream):
                t, local = int(r['timestamp']), int(r['local_timestamp'])
                bid, ask = Decimal(r['bid_price']), Decimal(r['ask_price'])
                if not bid.is_finite() or not ask.is_finite() or not 0 < bid <= ask or previous is not None and local < previous:
                    raise ValueError('QUOTE_SCHEMA_OR_ORDER')
                if t > local:
                    raise ValueError('SOURCE_CLOCK_DOMAIN_CONFLICT')
                previous = local
                fallback += t == local
                n += 1
        if n != report['rows']:
            raise ValueError('QUOTE_COUNT_MISMATCH')
        quotes.append(dict(symbol=symbol, rows=n, sha256=report['sha256'], gzip_crc='READ_TO_EOF_VERIFIED',
                           timestamp_equals_collector=fallback, publication='MISSING', independent_clock='MISSING',
                           full_period_liquidity='UNQUALIFIED'))
    expected = json.loads((frozen/'artifact-hashes.json').read_bytes())
    artifacts = {name: hash_file(frozen/name) == h for name, h in expected.items()}
    if not all(artifacts.values()):
        raise ValueError('FROZEN_ARTIFACT_CHANGED')
    replay = root/'science-012'/'frozen-replay'
    reproducibility = {name: hash_file(frozen/name) == hash_file(replay/name)
                       for name in ['dev-results.json', 'dev-models.json', 'oos-results.json']}
    if not all(reproducibility.values()):
        raise ValueError('FROZEN_REPLAY_DIFFERENT')
    return dict(status='EXECUTOR_REPRODUCED_NOT_INDEPENDENT_PM_VERIFIED', archive_count=len(files), files=files,
                rows=sum(x['rows'] for x in files), exact_mtf=mtf, complete_contexts=contexts, quotes=quotes,
                original_artifacts_unchanged=artifacts, replay_byte_matches=reproducibility,
                freeze_note='New replay freeze creation UTC differs; original freeze remains untouched; models/results match exactly.',
                invalidated_I4=json.loads((frozen/'method-errata.json').read_bytes())['invalidated_comparisons'],
                provider_limitation='Acquisition record reports checksum verification; original checksum response bodies not retained in reviewed-build. No new network verification claimed.',
                fresh_market_requests=0, full_V2='UNAVAILABLE', PIT='FAIL_HOLD')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root, output = Path(args.evidence).resolve(), Path(args.output).resolve()
    result = audit(root)
    with output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({k: result[k] for k in ['status', 'archive_count', 'rows', 'replay_byte_matches', 'fresh_market_requests']}))
