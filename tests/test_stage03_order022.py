"""ORDER-022 immutable real-archive workflow, tested with SYNTHETIC_TEST only.

These fixtures never count as actual historical market data or scientific OOS.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal
import csv
import hashlib
import io
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from zs_smart_gate.stage03_order022 import (
    Bar, MONTHS, SYMBOLS, ResearchBlocked, SQLiteHistoricalEvidence,
    canonical, digest, evaluate_rows, file_sha, filename, freeze,
    inventory, phase_for, read_month_zip, read_protocol, run,
)
from zs_smart_gate.setup021 import CONFIG_SHA256, VERSION


def stamp(day):
    return int(datetime.fromisoformat(day + "T00:00:00+00:00").timestamp() * 1000)


def synthetic_rows(month, *, breakout=True, break_at=25):
    date = "2025-04-02" if month == "2025-04" else month + "-01"
    start = stamp(date)
    result = []
    for i in range(40):
        op = start + i * 300000
        hit = i == break_at and breakout
        h,close,quote = ("112","111","1300") if hit else ("101","100","1000")
        result.append([
            str(op*1000),"100",h,"99",close,"10",
            str((op+300000)*1000-1),quote,"10","4","300","0",
        ])
    return result


def encoded_zip(symbol,month,rows):
    buff=io.BytesIO()
    with zipfile.ZipFile(buff, "w", compression=zipfile.ZIP_DEFLATED) as z:
        out=io.StringIO()
        csv.writer(out, lineterminator="\n").writerows(rows)
        z.writestr(filename(symbol,month)[:-4]+".csv",out.getvalue())
    return buff.getvalue()


def all_fixture_archives(directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    catalog={"schema":"ORDER022_SOURCE_CATALOG_V1","source_kind":"SYNTHETIC_TEST","files":[]}
    for symbol in SYMBOLS:
        for month in MONTHS:
            name=filename(symbol,month)
            payload=encoded_zip(symbol,month,synthetic_rows(month))
            (directory/name).write_bytes(payload)
            catalog["files"].append(dict(name=name,symbol=symbol,month=month,
                                        sha256=hashlib.sha256(payload).hexdigest(),
                                        source="SYNTHETIC_TEST_ONLY",
                                        provider_checksum_attested=False))
    return catalog


class InventoryFrozenPlanTests(unittest.TestCase):
    def test_setup_contract_and_purge_scope_pinned(self):
        proto,sha=read_protocol()
        self.assertEqual(proto["setup_version"], VERSION)
        self.assertEqual(proto["setup_contract_sha256"],CONFIG_SHA256)
        self.assertEqual(len(sha),64)
        self.assertEqual(proto["conditions"]["previous_high_bars"],20)
        self.assertEqual(proto["conditions"]["quote_volume_multiple"],"1.20")
        self.assertGreaterEqual(proto["partitions"]["OOS"]["start_ms"] -
                                proto["partitions"]["DEV"]["end_exclusive_ms"],2*86400*1000)

    def test_empty_inventory_is_explicitly_not_real_data(self):
        with tempfile.TemporaryDirectory() as d:
            inv=inventory(d)
            self.assertEqual(inv["status"],"DATA_ABSENT_OR_UNVERIFIED")
            self.assertEqual(sum(x["status"]=="MISSING" for x in inv["files"]),12)
            self.assertEqual(inv["market_requests"],0)
            self.assertFalse(inv["publisher_time_attested"])

    def test_no_freeze_without_all_expected_pinned_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            catalog=all_fixture_archives(root/"data")
            catalog_path=root/"catalog.json"
            catalog_path.write_bytes(canonical(catalog))
            (root/"data"/filename("ETHUSDT","2025-06")).unlink()
            with self.assertRaisesRegex(ResearchBlocked,"ALL_12"):
                freeze(root/"data",catalog_path,root/"frozen.json")
            self.assertFalse((root/"frozen.json").exists())

    def test_sha_mismatch_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); cat=all_fixture_archives(root/"data")
            f=root/"catalog.json";f.write_bytes(canonical(cat))
            p=root/"data"/filename("BTCUSDT","2025-02")
            p.write_bytes(p.read_bytes()+b"tamper")
            with self.assertRaisesRegex(ResearchBlocked,"ALL_12"):
                freeze(root/"data",f,root/"manifest.json")

    def test_schema_gap_monotonicity_and_zero_volume_guard(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            name=filename("BTCUSDT","2025-02")
            rows=synthetic_rows("2025-02")
            (root/name).write_bytes(encoded_zip("BTCUSDT","2025-02",rows))
            bars,audit=read_month_zip(root/name,"BTCUSDT","2025-02")
            self.assertEqual(len(bars),40)
            self.assertEqual(audit["missing_5m_slots"],0)
            rows[10][0]=rows[9][0]
            (root/name).write_bytes(encoded_zip("BTCUSDT","2025-02",rows))
            with self.assertRaisesRegex(ResearchBlocked,"DUPLICATE"):
                read_month_zip(root/name,"BTCUSDT","2025-02")
            rows=synthetic_rows("2025-02")
            rows[10][4]="NaN"
            (root/name).write_bytes(encoded_zip("BTCUSDT","2025-02",rows))
            with self.assertRaisesRegex(ResearchBlocked,"INVALID_ARCHIVE_ROW"):
                read_month_zip(root/name,"BTCUSDT","2025-02")

    def test_freeze_is_write_once_and_pins_data_code(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=all_fixture_archives(root/"data")
            p=root/"catalog.json";p.write_bytes(canonical(cat))
            manifest=root/"manifest.json"
            f=freeze(root/"data",p,manifest)
            self.assertTrue(f["frozen"])
            self.assertEqual(f["source_kind"],"SYNTHETIC_TEST")
            stored=json.loads(manifest.read_bytes())
            self.assertEqual(len(stored["structural_coverage"]),12)
            with self.assertRaises(FileExistsError):
                freeze(root/"data",p,manifest)
            p_archive=root/"data"/filename("BTCUSDT","2025-01")
            p_archive.write_bytes(p_archive.read_bytes()+b"x")
            with self.assertRaisesRegex(ResearchBlocked,"FROZEN_SOURCE_BYTES"):
                run(manifest,root/"data",root/"results.sqlite",root/"restore.sqlite")

    def test_catalog_cannot_elevate_synthetic_to_real_without_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=all_fixture_archives(root/"data")
            cat["source_kind"]="REAL_ARCHIVE_PRIVATE"
            p=root/"catalog.json";p.write_bytes(canonical(cat))
            with self.assertRaisesRegex(ResearchBlocked,"SOURCE_ATTESTATION_REQUIRED"):
                freeze(root/"data",p,root/"frozen.json")


class PriceOnlyCausalityTests(unittest.TestCase):
    def _bars(self,month="2025-02",breakout=True):
        raw=synthetic_rows(month,breakout=breakout)
        bars=[]
        for r in raw:
            start=int(r[0])//1000
            bars.append(Bar(start,start+300000,*(Decimal(r[k]) for k in (1,2,3,4,5,7))))
        return bars

    def test_price_only_cannot_pass_missing_historical_market_book(self):
        proto,_=read_protocol()
        s,e=evaluate_rows(self._bars(),"BTCUSDT",proto,"SYNTHETIC_TEST")
        self.assertGreater(s["DEV"]["partial_price_volume_patterns"],0)
        self.assertEqual(len(e["DEV"]),1)
        self.assertEqual(e["DEV"][0]["label"],"PARTIAL_PRICE_VOLUME_PATTERN_NOT_DETECTED_SIGNAL")
        self.assertEqual(e["DEV"][0]["core_spread_liquidity"],"MISSING_HISTORICAL_BOOK_24H")
        self.assertEqual(e["DEV"][0]["future_price_label"],"CLOSE_NOT_UP_12_BARS")
        self.assertNotIn("score",e["DEV"][0])

    def test_no_future_leak_in_trigger_count(self):
        proto,_=read_protocol()
        bars=self._bars()
        a,evt1=evaluate_rows(bars,"BTCUSDT",proto,"SYNTHETIC_TEST")
        modified=deepcopy(bars)
        target=modified[37]
        modified[37]=Bar(target.start,target.end,target.open,
                         Decimal("112"),target.low,Decimal("111.5"),
                         target.base_volume,target.quote_volume)
        b,evt2=evaluate_rows(modified,"BTCUSDT",proto,"SYNTHETIC_TEST")
        self.assertEqual(a["DEV"]["partial_price_volume_patterns"],
                         b["DEV"]["partial_price_volume_patterns"])
        self.assertEqual(evt1["DEV"][0]["event_key"],evt2["DEV"][0]["event_key"])
        self.assertNotEqual(evt1["DEV"][0]["future_price_label"],
                            evt2["DEV"][0]["future_price_label"])

    def test_cross_partition_future_not_leaked(self):
        proto,_=read_protocol()
        a=self._bars("2025-02")
        b=self._bars("2025-04")
        _,ev=evaluate_rows(a+b,"BTCUSDT",proto,"SYNTHETIC_TEST")
        self.assertEqual(len(ev["DEV"]),1)
        self.assertEqual(len(ev["OOS"]),1)
        self.assertNotEqual(ev["DEV"][0]["event_key"],ev["OOS"][0]["event_key"])

    def test_baseline_hourly_grid_independent_from_setup(self):
        proto,_=read_protocol()
        a,_=evaluate_rows(self._bars(breakout=True),"BTCUSDT",proto,"SYNTHETIC_TEST")
        b,_=evaluate_rows(self._bars(breakout=False),"BTCUSDT",proto,"SYNTHETIC_TEST")
        self.assertEqual(a["DEV"]["hourly_reference_observed"], b["DEV"]["hourly_reference_observed"])


class SyntheticIntegrationTests(unittest.TestCase):
    def test_full_synthetic_replay_retains_dev_oos_and_restore(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=all_fixture_archives(root/"data")
            p=root/"catalog.json";p.write_bytes(canonical(cat))
            manifest=root/"frozen.json"
            freeze(root/"data",p,manifest)
            result=run(manifest,root/"data",root/"result.sqlite",root/"restored.sqlite")
            self.assertEqual(result["status"],"SYNTHETIC_TEST_ONLY")
            self.assertEqual(result["source_kind"],"SYNTHETIC_TEST")
            self.assertEqual(len(result["inventory"]),12)
            self.assertEqual(len(result["partition_results"]),4)
            self.assertEqual(result["journal_readback_and_restore"]["restored_rows"],4)
            self.assertEqual(result["market_requests"],0)
            self.assertFalse(result["publishable"])
            self.assertTrue(all("INSUFFICIENT_EVIDENCE"==r["statistical_conclusion"]
                                for r in result["partition_results"].values()))
            self.assertTrue(all(r["full_setup_v1_1_qualifying_events"]==0
                                for r in result["partition_results"].values()))
            self.assertEqual(set(x.split(":")[1] for x in result["partition_results"]),{"DEV","OOS"})

    def test_evidence_journal_rejects_conflicts_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"archive.sqlite"
            journal=SQLiteHistoricalEvidence(path)
            journal.put("BTCUSDT:DEV",{"status":"NOT_QUALIFIED","count":1})
            journal.put("BTCUSDT:DEV",{"status":"NOT_QUALIFIED","count":1})
            with self.assertRaisesRegex(ResearchBlocked,"CONFLICT"):
                journal.put("BTCUSDT:DEV",{"status":"NOT_QUALIFIED","count":2})
            with journal.conn() as c:
                c.execute("UPDATE reports SET payload=? WHERE id=?",
                          (b'{"fake":true}',"BTCUSDT:DEV"))
            with self.assertRaisesRegex(ResearchBlocked,"TAMPERED"):
                journal.get("BTCUSDT:DEV")

    def test_no_socket_used_even_for_full_freeze_and_run(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=all_fixture_archives(root/"data")
            p=root/"catalog.json";p.write_bytes(canonical(cat))
            with patch("socket.socket",side_effect=AssertionError("NETWORK_FORBIDDEN")):
                freeze(root/"data",p,root/"frozen.json")
                report=run(root/"frozen.json",root/"data",root/"r.sqlite",root/"b.sqlite")
                self.assertEqual(report["market_requests"],0)


if __name__ == "__main__":
    unittest.main()
