"""Evaluate historical N01 separation using next closed bar continuation as a proxy."""
import argparse
import csv
from decimal import Decimal
from hashlib import sha256
import io
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from zs_smart_gate.setup021 import _predicate
from zs_smart_gate.stage03_r2_offline import Direction, close_parts

GRID = tuple(Decimal(i) / 100 for i in range(40, 96, 5))
STEP = 300_000_000


def read_file(root, checksums, frame, month, hashes):
    name = f"BTCUSDT-{frame}-2025-{month:02}.zip"
    path = root / name
    actual = sha256(path.read_bytes()).hexdigest()
    if actual != (checksums / (name + ".CHECKSUM")).read_text().split()[0].lower():
        raise ValueError("ARCHIVE_HASH_MISMATCH:" + name)
    hashes[name] = actual
    with ZipFile(path) as archive, archive.open(name.replace(".zip", ".csv")) as f:
        rows = csv.reader(io.TextIOWrapper(f, encoding="utf-8"))
        return [(int(row[0]), int(row[6]), *map(Decimal, (row[1],row[2],row[3],row[4],row[5],row[7])))
                for row in rows]


def observations(five, thirty):
    by_open = {row[0]: i for i, row in enumerate(five)}
    out, nonmatch = [], 0
    for row, following in zip(thirty, thirty[1:]):
        start, end, o,h,l,c,base,q = row
        i = by_open.get(start)
        if i is None or i < 16 or following[0] != end+1:
            continue
        window = five[i-16:i+6]
        if len(window) != 22 or any(bar[0] != start+(j-16)*STEP or bar[1] != bar[0]+STEP-1
                                     for j,bar in enumerate(window)):
            continue
        child = window[-6:]
        joined = (child[0][2],max(r[3] for r in child),min(r[4] for r in child),child[-1][5],
                  sum(r[6] for r in child),sum(r[7] for r in child))
        if joined != (o,h,l,c,base,q) or end != start+6*STEP-1:
            nonmatch += 1
            continue
        candles = [SimpleNamespace(open=r[2], high=r[3], close=r[5], quote_volume=r[7]) for r in window]
        if not _predicate(candles[1:]) or _predicate(candles[:-1]) or h == l:
            continue
        k,b,w = close_parts(SimpleNamespace(o=o,h=h,l=l,c=c),Direction.UP)
        out.append(((8*k+6*b+6*w)/20, following[5] > c))
    return out, nonmatch


def metric(rows, cutoff):
    tp = sum(n >= cutoff and label for n,label in rows)
    tn = sum(n < cutoff and not label for n,label in rows)
    pos = sum(label for _,label in rows)
    neg = len(rows)-pos
    return {"tp":tp,"tn":tn,"positive":pos,"negative":neg,
            "balanced_accuracy": round((tp/pos+tn/neg)/2,6) if pos and neg else None}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--checksums", type=Path, required=True)
    args=parser.parse_args()
    hashes, train, validation, months = {}, [], [], {}
    for month in range(1,7):
        five=read_file(args.archives,args.checksums,"5m",month,hashes)
        thirty=read_file(args.archives,args.checksums,"30m",month,hashes)
        rows, mismatches=observations(five,thirty)
        (train if month<=3 else validation).extend(rows)
        months[f"2025-{month:02}"]={"aligned_breakouts":len(rows),"reconciliation_mismatches":mismatches,
                                   "parent_rows":len(thirty)}
    ranked=[(c,metric(train,c)) for c in GRID]
    selected=max(ranked,key=lambda x: ((x[1]["balanced_accuracy"] or 0), -x[0]))[0]
    print(json.dumps({"reference":"next adjacent 30m close strictly higher; retrospective continuation proxy",
        "scope":"HISTORICAL_RESEARCH_NOT_PIT_OR_QUALIFICATION","training":"2025-01 through 2025-03",
        "validation":"2025-04 through 2025-06","grid":[str(x) for x in GRID],
        "exploratory_cutoff":str(selected),"train":metric(train,selected),
        "validation_metrics":metric(validation,selected),"months":months,"archive_sha256":hashes},
        sort_keys=True))


if __name__=="__main__":
    main()
