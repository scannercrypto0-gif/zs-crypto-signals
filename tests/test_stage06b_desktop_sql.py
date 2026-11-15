"""Stage06B new offline import/staging tests; no network or real SQL execution."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from test_e2e51 import fixture
from zs_smart_gate.e2e51 import analyze
from zs_smart_gate.stage05_contracts import canonical, digest, make_document, ContractError
from zs_smart_gate.stage06b_desktop_sql import (
    MANIFEST, build_sql_staging, apply_sql_server
)

TIME = "1794736800"


def bound(manifest):
    manifest["manifest_sha256"] = digest(canonical(manifest))
    return manifest


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.row = None

    def execute(self, statement, *params):
        if statement.startswith("SET XACT_ABORT"):
            return self
        table = statement.split("dbo.")[1].split()[0]
        if statement.startswith("SELECT"):
            fields = statement.split("SELECT ", 1)[1].split(" FROM", 1)[0].split(",")
            pk = tuple(params)
            entry = self.conn.rows.get((table, pk))
            self.row = tuple(entry[f] for f in fields) if entry else None
        elif statement.startswith("INSERT"):
            fields = statement.split("(", 1)[1].split(")", 1)[0].split(",")
            self.conn.rows[(table, tuple(params[:self.conn.pk_lengths[table]]))] = dict(zip(fields, params))
            self.row = None
        else:
            raise AssertionError("Unexpected SQL")
        return self

    def fetchone(self):
        return self.row

    def close(self):
        pass


class FakeConnection:
    autocommit = False
    pk_lengths = {"zs06b_candidates": 1, "zs06b_signals": 1,
                  "zs06b_candidate_decisions": 2, "zs06b_indicator_values": 2,
                  "zs06b_messages": 3, "zs06b_attachments": 3}

    def __init__(self):
        self.rows = {}
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class DesktopSQLTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source, clock = fixture()
        self.event = analyze(source, clock, synthetic=False)
        self.archive = make_document(self.event)

    def source(self, role="ANALYTICS_C", bot=2002, chat=101, exportid=700,
               msgid=42, *, with_attachment=True):
        name = "files/" + self.archive["manifest"]["file_name"]
        root = self.root / (role + str(msgid) + str(chat))
        root.mkdir(exist_ok=True)
        file = root / name
        files = []
        if with_attachment:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(self.archive["document"])
            files.append({"path": name, "sha256": digest(self.archive["document"]),
                          "size_bytes": len(self.archive["document"])})
        message = {
            "id": msgid, "type": "message", "date_unixtime": TIME,
            "text": self.archive["caption"] if role == "ANALYTICS_C" else "BOT SIGNAL STATUS",
        }
        if with_attachment:
            message["file"] = name
        export = {"id": exportid, "name": "offline synthetic fixture",
                  "type": "personal_chat", "messages": [message]}
        raw = canonical(export)
        manifest = bound({"schema": MANIFEST, "role": role,
                          "bot_family": "ANALYTICS" if role == "ANALYTICS_C" else "SIGNALS",
                          "bot_id": bot, "chat_id": chat, "export_chat_id": exportid,
                          "export_sha256": digest(raw), "attachments": files})
        return {"manifest": manifest, "raw_export": raw, "root": root}

    def test_verified_archive_to_normalized_candidate_and_delivery(self):
        staged = build_sql_staging([self.source()])
        self.assertEqual(len(staged["messages"]), 1)
        self.assertEqual(len(staged["candidates"]), 1)
        self.assertEqual(len(staged["attachments"]), 1)
        self.assertEqual(staged["candidates"][0]["candidate_id"], self.event["candidate_id"])
        self.assertIsNone(staged["messages"][0]["signal_id"])
        self.assertEqual(staged["batch_sha256"],
                         digest(canonical({k:v for k,v in staged.items() if k!="batch_sha256"})))
        self.assertFalse(staged["sql_executed"])

    def test_multiple_roles_distinct_bots_and_deterministic_replay(self):
        batch = [self.source(), self.source("SIGNALS_A", 1001, 101, 701, 21, with_attachment=False),
                 self.source("SIGNALS_B", 1001, 202, 702, 22, with_attachment=False)]
        a = build_sql_staging(batch)
        b = build_sql_staging(list(reversed(batch)))
        self.assertEqual(a, b)
        self.assertEqual(len(a["messages"]), 3)
        self.assertEqual(a["signals"], [])

    def test_missing_attachment_rejected(self):
        s = self.source()
        (s["root"] / s["manifest"]["attachments"][0]["path"]).unlink()
        with self.assertRaises(ContractError):
            build_sql_staging([s])

    def test_modified_attachment_rejected(self):
        s = self.source()
        (s["root"] / s["manifest"]["attachments"][0]["path"]).write_bytes(b"tampered")
        with self.assertRaises(ContractError):
            build_sql_staging([s])

    def test_path_traversal_rejected_even_if_manifest_hash_recomputed(self):
        s = self.source()
        s["manifest"]["attachments"][0]["path"] = "../outside.json"
        s["manifest"]["manifest_sha256"] = digest(canonical(
            {k:v for k,v in s["manifest"].items() if k!="manifest_sha256"}))
        with self.assertRaises(ContractError):
            build_sql_staging([s])

    def test_manifest_sha_conflict(self):
        s = self.source()
        s["manifest"]["chat_id"] += 1
        with self.assertRaises(ContractError):
            build_sql_staging([s])

    def test_export_hash_conflict(self):
        s = self.source()
        s["raw_export"] += b" "
        with self.assertRaises(ContractError):
            build_sql_staging([s])

    def test_export_declared_chat_identity_mismatch(self):
        s = self.source()
        s["manifest"]["export_chat_id"] += 1
        s["manifest"]["manifest_sha256"] = digest(canonical(
            {k:v for k,v in s["manifest"].items() if k!="manifest_sha256"}))
        with self.assertRaises(ContractError):
            build_sql_staging([s])

    def test_source_duplicate_rejected(self):
        s = self.source()
        with self.assertRaises(ContractError):
            build_sql_staging([s, s])

    def test_bot_families_cannot_share_bot_id(self):
        with self.assertRaises(ContractError):
            build_sql_staging([self.source(), self.source("SIGNALS_A", 2002, 101, 701, 21, with_attachment=False)])

    def test_analytics_document_forbidden_on_signals_channel(self):
        s = self.source("SIGNALS_A", 1001, 101, 701, 21, with_attachment=False)
        raw = __import__("json").loads(s["raw_export"])
        raw["messages"][0]["text"] = self.archive["caption"]
        s["raw_export"] = canonical(raw)
        s["manifest"]["export_sha256"] = digest(s["raw_export"])
        s["manifest"]["manifest_sha256"] = digest(canonical(
            {k:v for k,v in s["manifest"].items() if k!="manifest_sha256"}))
        with self.assertRaises(ContractError):
            build_sql_staging([s])

    def test_sql_staging_rejects_manipulated_packet(self):
        packet = build_sql_staging([self.source()])
        tampered = deepcopy(packet)
        tampered["messages"][0]["role"] = "OTHER"
        with self.assertRaises(ContractError):
            apply_sql_server(FakeConnection(), tampered)

    def test_mock_sql_parameterized_repeat_and_readback(self):
        packet = build_sql_staging([self.source()])
        conn = FakeConnection()
        a = apply_sql_server(conn, packet)
        b = apply_sql_server(conn, packet)
        self.assertEqual(a["rows_verified"], (
            len(packet["candidates"]) + len(packet["signals"]) +
            len(packet["candidate_decisions"]) + len(packet["indicator_values"]) +
            len(packet["messages"]) + len(packet["attachments"])))
        self.assertEqual(a["batch_sha256"], b["batch_sha256"])
        self.assertEqual(conn.commits, 2)
        self.assertEqual(conn.rollbacks, 0)

    def test_sql_existing_conflict_rolls_back(self):
        packet = build_sql_staging([self.source()])
        conn = FakeConnection()
        apply_sql_server(conn, packet)
        key = ("zs06b_candidates", (self.event["candidate_id"],))
        conn.rows[key]["event_sha256"] = "b"*64
        with self.assertRaises(ContractError):
            apply_sql_server(conn, packet)
        self.assertEqual(conn.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
