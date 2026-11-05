"""ORDER-022: offline, bounded historic price/volume research, never live market.

No network, no fake historical market snapshots or publisher receipts. Real
archives must be explicitly supplied; archive fingerprints bind the immutable
experiment manifest. A partial OHLCV pattern is NOT a Setup v1.1 qualified
DETECTED_SIGNAL because historical book/24h liquidity wasn't recorded.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import csv
import hashlib
import io
import json
import re
import sqlite3
import zipfile

from .setup021 import CONFIG_SHA256, VERSION, _predicate, canonical, digest

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
PROTOCOL_PATH = ROOT / "research" / "order022" / "protocol-v1.json"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
MONTHS = tuple(f"2025-{n:02}" for n in range(1, 7))
INTERVAL_MS = 300000
ONE_HOUR_BARS = 12
ZIP_CAP = 12 * 1024 * 1024
CSV_CAP = 32 * 1024 * 1024


class ResearchBlocked(ValueError):
    pass


@dataclass(frozen=True)
class Bar:
    start: int
    end: int  # exclusive UTC ms
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    base_volume: Decimal
    quote_volume: Decimal


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_protocol():
    raw = PROTOCOL_PATH.read_bytes()
    obj = json.loads(raw)
    if obj["version"] != "ORDER022_HISTORICAL_REPLAY_PROTOCOL_V1":
        raise ResearchBlocked("PROTOCOL_VERSION_UNKNOWN")
    if obj["setup_contract_sha256"] != CONFIG_SHA256 or obj["setup_version"] != VERSION:
        raise ResearchBlocked("FROZEN_SETUP_CONTRACT_MISMATCH")
    if obj["symbols"] != list(SYMBOLS) or obj["months"] != list(MONTHS):
        raise ResearchBlocked("UNAUTHORIZED_DATASET_SCOPE")
    return obj, sha_bytes(raw)


def filename(symbol, month):
    return f"{symbol}-5m-{month}.zip"


def _catalog(catalog_path):
    obj = json.loads(Path(catalog_path).read_bytes())
    if obj.get("schema") != "ORDER022_SOURCE_CATALOG_V1":
        raise ResearchBlocked("CATALOG_SCHEMA_UNKNOWN")
    origin = obj.get("source_kind")
    if origin not in ("REAL_ARCHIVE_PRIVATE", "SYNTHETIC_TEST"):
        raise ResearchBlocked("CATALOG_PROVENANCE_REQUIRED")
    paths = obj.get("files")
    if not isinstance(paths, list) or len(paths) != 12:
        raise ResearchBlocked("TWELVE_ARCHIVE_SOURCE_PINS_REQUIRED")
    result = {}
    for e in paths:
        key = (e.get("symbol"), e.get("month"))
        if key in result or key[0] not in SYMBOLS or key[1] not in MONTHS:
            raise ResearchBlocked("CATALOG_SCOPE_OR_DUPLICATE")
        if e.get("name") != filename(*key):
            raise ResearchBlocked("CATALOG_FILENAME_CHANGED")
        if not isinstance(e.get("sha256"), str) or not re.fullmatch("[0-9a-f]{64}", e["sha256"]):
            raise ResearchBlocked("CATALOG_SHA256_REQUIRED")
        if origin == "REAL_ARCHIVE_PRIVATE" and e.get("source") != "BINANCE_VISION_SPOT_PUBLIC_ARCHIVE":
            raise ResearchBlocked("REAL_ARCHIVE_SOURCE_ATTESTATION_REQUIRED")
        result[key] = e
    if set(result) != {(s, m) for s in SYMBOLS for m in MONTHS}:
        raise ResearchBlocked("CATALOG_COVERAGE_SCOPE_INCOMPLETE")
    return obj, result


def inventory(directory, catalog=None):
    """No network. Without a signed catalog, inventory cannot attest the source."""
    directory = Path(directory)
    entries = _catalog(catalog)[1] if catalog is not None else {}
    result = []
    for symbol in SYMBOLS:
        for month in MONTHS:
            name = filename(symbol, month)
            path = directory / name
            entry = entries.get((symbol, month))
            item = {"symbol": symbol, "month": month, "name": name,
                    "status": "MISSING", "bytes": None, "sha256": None,
                    "external_sha256_match": None, "provider_checksum_attested": False}
            if path.is_file():
                size = path.stat().st_size
                if size > ZIP_CAP:
                    item["status"] = "ZIP_SIZE_CAP_EXCEEDED"
                else:
                    h = file_sha(path)
                    item.update(bytes=size, sha256=h, status="PRESENT_UNVERIFIED_CATALOG" if not entry else
                                "SHA_VERIFIED" if h == entry["sha256"] else "SHA_MISMATCH",
                                external_sha256_match=(h == entry["sha256"]) if entry else None,
                                provider_checksum_attested=bool(entry.get("provider_checksum_attested", False)) if entry else False)
            result.append(item)
    return {"source": "LOCAL_PRIVATE_ARCHIVE_INSPECTION_NO_DOWNLOAD", "files": result,
            "status": "COMPLETE_PINNED" if all(x["status"] == "SHA_VERIFIED" for x in result)
                else "DATA_ABSENT_OR_UNVERIFIED", "market_requests": 0,
            "publisher_time_attested": False, "historical_pit": "HISTORICAL_REPLAY_PIT_UNVERIFIED"}


def freeze(data_dir, catalog_path, manifest_path):
    """Creates a one-time, file-SHA-bound immutable manifest. Never overwrites."""
    protocol, protocol_sha = read_protocol()
    source, indexed = _catalog(catalog_path)
    inv = inventory(data_dir, catalog_path)
    if inv["status"] != "COMPLETE_PINNED":
        raise ResearchBlocked("FROZEN_EXPERIMENT_REQUIRES_ALL_12_PINNED_ARCHIVES")
    binding = []
    coverage = []
    for symbol in SYMBOLS:
        for month in MONTHS:
            e = indexed[symbol, month]
            # Inspect only structural integrity and coverage BEFORE freezing,
            # not setup triggers or DEV/OOS outcomes.
            _, meta = read_month_zip(Path(data_dir) / e["name"], symbol, month)
            coverage.append(meta)
            binding.append(dict(symbol=symbol, month=month, name=e["name"],
                                sha256=e["sha256"], source=e.get("source"),
                                provider_checksum_attested=e.get("provider_checksum_attested") is True))
    frozen = {
        "schema": "ORDER022_FROZEN_EXPERIMENT_V1",
        "protocol_sha256": protocol_sha,
        "setup_contract_sha256": CONFIG_SHA256,
        "module_sha256": file_sha(HERE),
        "setup_module_sha256": file_sha(ROOT / "src" / "zs_smart_gate" / "setup021.py"),
        "source_kind": source["source_kind"],
        "archives": binding,
        "structural_coverage": coverage,
        "engine": "PRICE_VOLUME_PARTIAL_ONLY",
        "evaluation_exclusion": "NO_HISTORICAL_BOOK_24HR_OR_PUBLISHER_RECEIPT",
    }
    b = canonical(frozen)
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(b)
        stream.flush()
    return {"manifest_sha256": sha_bytes(b), "manifest_path": str(path),
            "frozen": True, "source_kind": source["source_kind"], "market_requests": 0}


def _load_frozen(manifest_path, data_dir):
    protocol, protocol_sha = read_protocol()
    raw = Path(manifest_path).read_bytes()
    m = json.loads(raw)
    if (m.get("schema") != "ORDER022_FROZEN_EXPERIMENT_V1" or
        m.get("protocol_sha256") != protocol_sha or
        m.get("setup_contract_sha256") != CONFIG_SHA256 or
        m.get("module_sha256") != file_sha(HERE) or
        m.get("setup_module_sha256") != file_sha(ROOT / "src" / "zs_smart_gate" / "setup021.py") or
        m.get("engine") != "PRICE_VOLUME_PARTIAL_ONLY"):
        raise ResearchBlocked("FROZEN_PROTOCOL_OR_CODE_CHANGED")
    expected = {(s, month) for s in SYMBOLS for month in MONTHS}
    entries = m.get("archives")
    if not isinstance(entries, list) or len(entries) != 12:
        raise ResearchBlocked("FROZEN_DATASET_ENTRY_COUNT")
    if {(x.get("symbol"), x.get("month")) for x in entries} != expected:
        raise ResearchBlocked("FROZEN_SOURCE_SCOPE_CHANGED")
    for e in entries:
        if e["name"] != filename(e["symbol"], e["month"]) or not re.fullmatch("[0-9a-f]{64}", e["sha256"]):
            raise ResearchBlocked("FROZEN_FILE_IDENTITY_CHANGED")
        p = Path(data_dir) / e["name"]
        if not p.is_file() or p.stat().st_size > ZIP_CAP or file_sha(p) != e["sha256"]:
            raise ResearchBlocked("FROZEN_SOURCE_BYTES_MISSING_OR_CHANGED")
    if m.get("source_kind") not in ("REAL_ARCHIVE_PRIVATE", "SYNTHETIC_TEST"):
        raise ResearchBlocked("FROZEN_PROVENANCE_CHANGED")
    return m, sha_bytes(raw), protocol


def _month_start_ms(month):
    return int(datetime.fromisoformat(month + "-01T00:00:00+00:00").timestamp() * 1000)


def read_month_zip(path, symbol, month):
    """Input is exactly the old 010-B provider-style 12-field microsecond CSV."""
    raw = Path(path).read_bytes()
    if len(raw) > ZIP_CAP:
        raise ResearchBlocked("ZIP_CAP_EXCEEDED")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if (len(members) != 1 or members[0].filename != filename(symbol, month)[:-4] + ".csv" or
            members[0].file_size > CSV_CAP):
            raise ResearchBlocked("ARCHIVE_MEMBER_OR_EXPANDED_SIZE_INVALID")
        data = archive.read(members[0])
        if len(data) > CSV_CAP:
            raise ResearchBlocked("EXPANDED_SIZE_EXCEEDED")
    text = data.decode("utf-8-sig")
    rows = []
    invalid = 0
    time_start = _month_start_ms(month)
    next_month = MONTHS[MONTHS.index(month)+1] if MONTHS.index(month)+1 < len(MONTHS) else "2025-07"
    limit = _month_start_ms(next_month)
    prev = None
    gaps = 0
    duplicates = 0
    for raw_fields in csv.reader(io.StringIO(text)):
        try:
            if len(raw_fields) != 12:
                raise ValueError("FIELD_COUNT")
            open_micro, close_micro = int(raw_fields[0]), int(raw_fields[6])
            if open_micro % 1000 or (close_micro+1) % 1000:
                raise ValueError("NON_MICROSECOND_ALIGNED")
            start, end = open_micro//1000, (close_micro+1)//1000
            if not(time_start <= start < limit) or start % INTERVAL_MS or end-start != INTERVAL_MS:
                raise ValueError("TIME_SCOPE")
            nums = [Decimal(raw_fields[i]) for i in (1,2,3,4,5,7)]
            if any(not x.is_finite() for x in nums):
                raise ValueError("NON_FINITE")
            o,h,l,c,base,quote = nums
            if not(0 < l <= min(o,c) <= max(o,c) <= h and min(base,quote) >= 0):
                raise ValueError("OHLCV")
            if prev is not None:
                if start <= prev:
                    duplicates += 1
                    raise ResearchBlocked("NON_MONOTONIC_OR_DUPLICATE_ARCHIVE")
                if start != prev+INTERVAL_MS:
                    gaps += (start-prev)//INTERVAL_MS-1
            prev = start
            rows.append(Bar(start,end,o,h,l,c,base,quote))
        except ResearchBlocked:
            raise
        except (ValueError, InvalidOperation, IndexError, OverflowError):
            invalid += 1
            # If the source row has no trusted timestamp its continuity is
            # unknown: reject this archive instead of stitching across it.
            raise ResearchBlocked("INVALID_ARCHIVE_ROW_CANNOT_REPAIR_SEQUENCE")
    return rows, dict(symbol=symbol,month=month,rows=len(rows),invalid_rows=invalid,
                      missing_5m_slots=gaps,duplicate_rows=duplicates,
                      first_open_ms=rows[0].start if rows else None,
                      last_close_ms=rows[-1].end if rows else None,
                      csv_sha256=sha_bytes(data))


def phase_for(start_ms, protocol):
    dev = protocol["partitions"]["DEV"]
    oos = protocol["partitions"]["OOS"]
    if dev["start_ms"] <= start_ms < dev["end_exclusive_ms"]:
        return "DEV"
    if oos["start_ms"] <= start_ms < oos["end_exclusive_ms"]:
        return "OOS"
    return None


def evaluate_rows(bars, symbol, protocol, source_kind):
    """No market snapshots: *never* claim to call/full-pass Setup.evaluate."""
    samples = {"DEV": Counter(), "OOS": Counter()}
    events = {"DEV": [], "OOS": []}
    blocks = {"DEV": -1, "OOS": -1}
    lookback = 22
    for idx in range(lookback-1, len(bars)):
        current = bars[idx]
        phase = phase_for(current.start, protocol)
        if phase is None:
            continue
        summary = samples[phase]
        summary["evaluated_closes"] += 1
        history = bars[idx-lookback+1:idx+1]
        if any(phase_for(x.start, protocol) != phase for x in history):
            summary["partition_warmup_rejected"] += 1
            continue
        if any(a.end != b.start for a,b in zip(history,history[1:])):
            summary["gap_crossing_rejected"] += 1
            continue
        summary["valid_22bar_price_windows"] += 1
        # Predeclared direction-only hourly reference, independent of setup
        # trigger or any future result; no execution/P&L interpretation.
        if current.start % (ONE_HOUR_BARS*INTERVAL_MS) == 0:
            if idx+ONE_HOUR_BARS < len(bars):
                end = bars[idx+ONE_HOUR_BARS]
                path = bars[idx:idx+ONE_HOUR_BARS+1]
                if (all(x.end == y.start for x,y in zip(path,path[1:]))
                        and phase_for(end.start,protocol)==phase):
                    summary["hourly_reference_observed"] += 1
                    if end.close > current.close:
                        summary["hourly_reference_close_up"] += 1
                    else:
                        summary["hourly_reference_close_not_up"] += 1
        try:
            previous = _predicate(history[:-1])
            now = _predicate(history[1:])
        except (ValueError, InvalidOperation, ArithmeticError):
            summary["invalid_baseline_or_predicate"] += 1
            continue
        if not now:
            summary["no_price_volume_trigger"] += 1
        elif previous:
            summary["no_false_to_true_transition"] += 1
        else:
            summary["partial_price_volume_patterns"] += 1
            # Predeclared one-hour censor after an admitted pattern avoids
            # counting overlapping outcomes as independent.
            if idx <= blocks[phase]:
                summary["outcome_overlap_suppressed"] += 1
                continue
            blocks[phase] = idx + ONE_HOUR_BARS-1
            event = {
                "label": "PARTIAL_PRICE_VOLUME_PATTERN_NOT_DETECTED_SIGNAL",
                "event_key": digest(dict(contract=CONFIG_SHA256, symbol=symbol, close_ms=current.end,
                    phase=phase, source="OFFLINE_ARCHIVE")),
                "symbol": symbol, "partition": phase, "closed_candle_ms": current.end,
                "future_price_label": "UNAVAILABLE",
                "future_close_delta_positive": None,
                "executable_ohlcv_return": "NOT_CALCULATED",
                "publisher_receipt": "HISTORICAL_REPLAY_PIT_UNVERIFIED",
                "core_spread_liquidity": "MISSING_HISTORICAL_BOOK_24H",
            }
            if idx + ONE_HOUR_BARS < len(bars):
                future = bars[idx+ONE_HOUR_BARS]
                segment = bars[idx:idx+ONE_HOUR_BARS+1]
                if (all(a.end == b.start for a,b in zip(segment,segment[1:])) and
                    phase_for(future.start,protocol)==phase):
                    event["future_price_label"] = ("CLOSE_UP_12_BARS" if future.close > current.close
                                                    else "CLOSE_NOT_UP_12_BARS")
                    event["future_close_delta_positive"] = future.close > current.close
                    summary["observed_price_only_horizon_12"] += 1
                else:
                    summary["outcome_crosses_gap_or_partition"] += 1
            else:
                summary["future_bars_unavailable"] += 1
            events[phase].append(event)
    return samples,events


class SQLiteHistoricalEvidence:
    """Small, append-only result journal, no quote snapshot or networking."""
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.conn() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, payload BLOB NOT NULL)")
    def conn(self):
        # sqlite3.Connection context doesn't close on Windows; wrap separately.
        class _Conn:
            def __init__(self,path):self.c=sqlite3.connect(str(path))
            def __enter__(self):
                self.c.execute("PRAGMA journal_mode=WAL")
                self.c.execute("PRAGMA synchronous=FULL")
                return self.c
            def __exit__(self,*exc):
                if exc[0]:self.c.rollback()
                else:self.c.commit()
                self.c.close()
        return _Conn(self.path)
    def put(self,key,value):
        raw=canonical(value)
        if len(raw)>400000:raise ResearchBlocked("REPORT_SIZE_CAP")
        hashed=sha_bytes(raw)
        with self.conn() as c:
            try:c.execute("INSERT INTO reports VALUES(?,?,?)",(key,hashed,raw))
            except sqlite3.IntegrityError:
                prev=c.execute("SELECT sha256,payload FROM reports WHERE id=?",(key,)).fetchone()
                if prev!=(hashed,raw):raise ResearchBlocked("IMMUTABLE_REPORT_CONFLICT")
        if self.get(key)!=value:raise ResearchBlocked("JOURNAL_READBACK_MISMATCH")
    def get(self,key):
        with self.conn() as c:
            row=c.execute("SELECT sha256,payload FROM reports WHERE id=?",(key,)).fetchone()
        if row is None or sha_bytes(row[1])!=row[0]:raise ResearchBlocked("JOURNAL_MISSING_OR_TAMPERED")
        return json.loads(row[1])
    def backup_check(self,destination):
        target=Path(destination)
        if target.exists() or target.resolve()==self.path.resolve():raise ResearchBlocked("BACKUP_DEST_MUST_BE_FRESH")
        target.parent.mkdir(parents=True,exist_ok=True)
        with self.conn() as src,closing(sqlite3.connect(str(target))) as dest:
            src.backup(dest)
        copy=SQLiteHistoricalEvidence(target)
        with copy.conn() as c:
            if c.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ResearchBlocked("BACKUP_INTEGRITY_FAILED")
        with self.conn() as c:
            ids=[r[0] for r in c.execute("SELECT id FROM reports ORDER BY id")]
        for i in ids:
            if self.get(i)!=copy.get(i):raise ResearchBlocked("BACKUP_READBACK_DIFFERENT")
        return {"restored_rows":len(ids),"status":"READBACK_RESTORED_OFFLINE",
                "rows_sha256":digest([self.get(i) for i in ids]),"owner_windows_proven":False}


def run(manifest_path,data_dir,db_path,backup_path):
    frozen, fsha, protocol=_load_frozen(manifest_path,data_dir)
    expected={e["name"]:e for e in frozen["archives"]}
    bars_by_symbol={s:[] for s in SYMBOLS}
    inventory=[]
    for symbol in SYMBOLS:
        for month in MONTHS:
            name=filename(symbol,month)
            rows,meta=read_month_zip(Path(data_dir)/name,symbol,month)
            meta.update(sha256=expected[name]["sha256"],provider_checksum_attested=expected[name]["provider_checksum_attested"])
            inventory.append(meta);bars_by_symbol[symbol].extend(rows)
    summaries={};event_digest={}
    for symbol in SYMBOLS:
        bars=bars_by_symbol[symbol]
        # No sorting: archive order must be trustworthy, and a gap remains a
        # gap rather than being silently filled by reconstruction.
        if any(a.start>=b.start for a,b in zip(bars,bars[1:])):
            raise ResearchBlocked("CROSS_MONTH_DUPLICATE_OR_ORDER")
        groups,events=evaluate_rows(bars,symbol,protocol,frozen["source_kind"])
        for phase in ("DEV","OOS"):
            counts=dict(sorted(groups[phase].items()))
            n=counts.get("observed_price_only_horizon_12",0)
            pos=sum(e["future_close_delta_positive"] is True for e in events[phase])
            neg=sum(e["future_close_delta_positive"] is False for e in events[phase])
            # Explicitly descriptive: price-only forward label, not a win rate.
            detail={"symbol":symbol,"partition":phase,"counts":counts,
                "partial_event_count":len(events[phase]),
                "future_price_up_12":pos,"future_price_not_up_12":neg,
                "outcome_label_availability":n,
                "full_setup_v1_1_qualifying_events":0,
                "full_setup_status":"UNKNOWN_NO_TIME_VALID_BOOK_TICKER_24H",
                "historical_pit":"HISTORICAL_REPLAY_PIT_UNVERIFIED",
                "statistical_conclusion":"INSUFFICIENT_EVIDENCE",
                "return_after_costs":"NOT_CALCULATED_NO_EXECUTABLE_BID_ASK"}
            summaries[symbol+":"+phase]=detail
            event_digest[symbol+":"+phase]=digest(events[phase])
    source_ok=all(x["provider_checksum_attested"] for x in inventory)
    payload={
        "order":"ORDER-022","status":("SYNTHETIC_TEST_ONLY" if frozen["source_kind"] == "SYNTHETIC_TEST" else "HISTORICAL_PRICE_ONLY_REPLAY_NOT_FULL_SETUP_QUALIFIED"),
        "source_kind":frozen["source_kind"],"manifest_sha256":fsha,
        "protocol_sha256":frozen["protocol_sha256"],
        "setup_contract_sha256":CONFIG_SHA256,
        "inventory":inventory,"partition_results":summaries,"event_list_sha256":event_digest,
        "provider_checksums_attested_by_catalog":source_ok,
        "source_provenance":"ARCHIVES_SUPPLIED_OFFLINE_NOT_INDEPENDENT_PUBLICATION_RECEIPTS",
        "historical_pit":"HISTORICAL_REPLAY_PIT_UNVERIFIED",
        "simulated_receipt_times":"NOT_USED",
        "model_tuning":"NONE",
        "market_requests":0,"trading":False,"telegram":False,
        "publishable":False,"score":None,"stage05":"FULL_HOLD",
    }
    db=SQLiteHistoricalEvidence(db_path)
    for key,v in summaries.items():db.put(key,v)
    restore=db.backup_check(backup_path)
    payload["journal_readback_and_restore"]=restore
    return payload
