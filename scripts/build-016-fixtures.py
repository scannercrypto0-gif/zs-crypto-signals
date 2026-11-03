"""Extract bounded ARCHIVE fixtures from verified GitHub custody; never new OOS."""
import argparse,csv,hashlib,io,json
from pathlib import Path
import zipfile
from zs_smart_gate.evidence_journal import canonical_bytes

START=1736121600000  # 2025-01-06 Monday UTC
END=1736726400000    # 2025-01-13 Monday UTC

def extract(custody_root,output):
    root=Path(custody_root);output=Path(output)
    index=json.loads((root/'inventory.json').read_bytes())
    output.mkdir(parents=True,exist_ok=False)
    metadata=[]
    for symbol in ['BTCUSDT','ETHUSDT']:
        name=symbol+'-5m-2025-01.zip'
        entries=[x for x in index['files']if x['path'].endswith('/'+name)and '/negative-root/'not in x['path']]
        hashes={x['sha256']for x in entries}
        if len(hashes)!=1:raise ValueError('UNIQUE_FROZEN_ARCHIVE_REQUIRED')
        sha=next(iter(hashes));raw=(root/'objects'/sha).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('ARCHIVE_CHANGED')
        rows=[]
        with zipfile.ZipFile(io.BytesIO(raw))as z:
            if len(z.namelist())!=1 or z.testzip()is not None:raise ValueError('ZIP_CRC')
            for row in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
                o,c=int(row[0]),int(row[6])
                # Binance Vision2025 microseconds -> REST-compatible milliseconds.
                if o>10**14:o//=1000;c//=1000
                if START<=o and c<END:
                    row[0],row[6]=o,c;rows.append(row)
        if len(rows)!=2016:raise ValueError('EXPECTED_COMPLETE_CALENDAR_WEEK')
        fixture=dict(symbol=symbol,rows=rows,received_ms=END+100,
             provenance=dict(mode='HISTORICAL_ARCHIVE_REPLAY_NOT_ORIGINAL_RECEIPT',source_archive_sha256=sha,
                source_evidence_commit='007925325914338536f76cd42962a776c82a4ee3',
                source_study='custody-010-014-015-raw',original_period='2025-01',
                synthetic_replay_receipt_clock=True,already_viewed_not_new_OOS=True))
        body=canonical_bytes(fixture);(output/(symbol+'.json')).write_bytes(body)
        metadata.append(dict(symbol=symbol,sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),
                             original_archive_sha256=sha,rows=2016))
    (output/'fixture-index.json').write_bytes(canonical_bytes(metadata))
    return metadata

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--custody-root',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(extract(a.custody_root,a.output)))
