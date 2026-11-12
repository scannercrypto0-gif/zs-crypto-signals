"""Stage04 Windows-journal scoped tests. No network, bots or production writes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from test_stage03_research_handoff import synthetic_handoff
from zs_smart_gate.stage04_windows_operational import (
    WindowsOperationalJournal, verify_backup, BACKUP_SCHEMA,
)
from zs_smart_gate.stage05_contracts import ContractError, canonical


def handoff_row():
    return synthetic_handoff()


class WindowsOperationalCustodyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.home = root / "runtime"
        self.home.mkdir()
        self.backups = root / "backups"
        self.backups.mkdir()
        self.restore = root / "recovered"
        self.restore.mkdir()
        self.db_path = self.home / "custody.db"
        self.store = WindowsOperationalJournal(self.db_path)
        self.key = "research/" + handoff_row()["event_id"]

    def _payload(self):
        return canonical(handoff_row())

    def test_atomic_append_idempotence_and_conflict(self):
        p=self._payload()
        self.assertTrue(self.store.create_if_absent(self.key,p))
        self.assertFalse(self.store.create_if_absent(self.key,p))
        self.assertEqual(self.store.read(self.key),p)
        self.assertEqual(self.store.verify_all(),(1,len(p)))
        modified=deepcopy(handoff_row())
        modified["source_manifest_sha256"]="a"*64
        # Tampered payload is never accepted even if submitted under existing ID.
        with self.assertRaises(ContractError):
            self.store.create_if_absent(self.key, canonical(modified))

    def test_existing_rows_prohibit_sql_update_and_delete(self):
        self.store.create_if_absent(self.key,self._payload())
        with sqlite3.connect(self.db_path) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE custody SET sha256='0' WHERE record_key=?",(self.key,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM custody WHERE record_key=?",(self.key,))
        self.assertIsNotNone(self.store.read(self.key))

    def test_online_snapshot_exact_backup_then_new_path_restore(self):
        p=self._payload()
        self.store.create_if_absent(self.key,p)
        backup=self.backups/"custody-backup.sqlite"
        receipt=self.store.make_backup(backup)
        self.assertEqual(receipt.record_count,1)
        self.assertEqual(receipt.byte_count,len(p))
        self.assertEqual(receipt.integrity,"SQLITE_AND_SHA_READBACK_PASS")
        self.assertFalse(receipt.production_recovery_approved)
        self.assertEqual(verify_backup(backup,receipt.backup_sha256),(1,len(p)))
        manifest=json.loads(Path(str(backup)+".manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"],BACKUP_SCHEMA)
        self.assertEqual(manifest["encrypted_media"],"UNVERIFIED")
        recovered=WindowsOperationalJournal.restore_to_new_path(
            backup,receipt.backup_sha256,self.restore/"restored.sqlite")
        self.assertEqual(recovered.read(self.key),p)
        self.assertEqual(recovered.verify_all(),(1,len(p)))

    def test_restore_never_overwrites_existing_or_bad_pin(self):
        self.store.create_if_absent(self.key,self._payload())
        backup=self.backups/"pinned.sqlite"
        rec=self.store.make_backup(backup)
        with self.assertRaises(ContractError):
            WindowsOperationalJournal.restore_to_new_path(
                backup,"0"*64,self.restore/"wrong.sqlite")
        with self.assertRaises(ContractError):
            WindowsOperationalJournal.restore_to_new_path(
                backup,rec.backup_sha256,self.db_path)
        with self.assertRaises(ContractError):
            self.store.make_backup(backup)

    def test_tampered_backup_bytes_detected_by_independent_pin(self):
        self.store.create_if_absent(self.key,self._payload())
        backup=self.backups/"pinned.sqlite"
        rec=self.store.make_backup(backup)
        with backup.open("ab") as f:
            f.write(b"CORRUPT_APPEND")
        with self.assertRaisesRegex(ContractError,"SHA_MISMATCH"):
            verify_backup(backup,rec.backup_sha256)
        with self.assertRaises(ContractError):
            WindowsOperationalJournal.restore_to_new_path(
                backup,rec.backup_sha256,self.restore/"no.sqlite")

    def test_bad_namespace_and_secret_field_fail_closed(self):
        with self.assertRaises(ContractError):
            self.store.create_if_absent("bot-token/secret",self._payload())
        with self.assertRaises(ContractError):
            self.store.create_if_absent(self.key,b'{"token":"NEVER"}')
        self.assertEqual(self.store.verify_all(),(0,0))
