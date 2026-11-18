"""End-to-end synthetic owner receipt creation and restored-raw verification, offline."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/p0-owner-anchor.py"
RAW = ROOT / "research/order025/p0-readiness/synthetic-raw-v1.txt"
MANIFEST = ROOT / "research/order025/p0-readiness/owner-custody-and-field-manifest-draft.md"
CODE_SHA = "e7175be06aaf89154842db3c48733b5f53666b77"
EVENT = "ZS03-P0-SYNTHETIC-READBACK-0001"
spec = importlib.util.spec_from_file_location("p0_owner_anchor", SCRIPT)
anchor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(anchor)


def sample(raw: bytes | None = None, manifest: bytes | None = None):
    return anchor.make_receipt(
        RAW.read_bytes() if raw is None else raw,
        MANIFEST.read_bytes() if manifest is None else manifest,
        study_id="ZS03-P0-UTC-CUSTODY-FIELD-READINESS-001",
        event_id=EVENT, code_sha=CODE_SHA,
        repository="scannercrypto0-gif/zs-crypto-signals",
        raw_path="research/order025/p0-readiness/synthetic-raw-v1.txt",
        manifest_path="research/order025/p0-readiness/owner-custody-and-field-manifest-draft.md",
        creator="SYNTHETIC_CI_WRITER",
        generated_at_utc="2026-11-07T08:00:00Z")


def check(raw: bytes, envelope: dict, manifest: bytes | None = None,
          receipt_sha: str | None = None):
    data = anchor.receipt_bytes(envelope)
    return anchor.verify(
        raw, MANIFEST.read_bytes() if manifest is None else manifest, data,
        expected_owner_file_sha256=receipt_sha or hashlib.sha256(data).hexdigest(),
        expected_code_sha=CODE_SHA, expected_event_id=EVENT)


class SyntheticOwnerHandoff(unittest.TestCase):
    def test_new_receipt_restored_raw_and_manifest_match(self):
        data = RAW.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "read-only-restore" / "raw.txt"
            copy.parent.mkdir()
            copy.write_bytes(data)
            r = check(copy.read_bytes(), sample())
        self.assertEqual(r["status"], "SYNTHETIC_RECEIPT_AND_RESTORED_RAW_MATCH_ONLY")
        self.assertEqual(r["raw_size_bytes"], 153)
        self.assertEqual(r["raw_sha256"],
                         "da71f78daf4ae57ff5b984353611c5e9ae17731eda2f009a17ee0dce5bb48165")
        self.assertEqual(r["custody_gate"], "OWNER_CUSTODY_ACK_PENDING")
        self.assertFalse(r["outside_writer_control_proven"])
        self.assertFalse(r["owner_receipt_time_proven"])

    def test_raw_mutation_blocked(self):
        raw = RAW.read_bytes()
        with self.assertRaisesRegex(anchor.AnchorBlocked, "MISMATCH"):
            check(raw.replace(b"raw-receipt-test", b"raw-RECEIPT-test"), sample())

    def test_raw_truncated_blocked(self):
        with self.assertRaisesRegex(anchor.AnchorBlocked, "SYNTHETIC|MISMATCH"):
            check(RAW.read_bytes()[:-1], sample())

    def test_owner_file_sha_mismatch_blocked(self):
        with self.assertRaisesRegex(anchor.AnchorBlocked, "OWNER_RECEIPT_FILE_MISMATCH"):
            check(RAW.read_bytes(), sample(), receipt_sha="0" * 64)

    def test_receipt_body_changed_even_if_file_digest_recalculated_blocked(self):
        envelope = sample()
        envelope["receipt"]["event_id"] = "FORGED-EVENT-ID"
        with self.assertRaisesRegex(anchor.AnchorBlocked, "RECEIPT_BODY_MISMATCH"):
            check(RAW.read_bytes(), envelope)

    def test_manifest_mutation_blocked(self):
        with self.assertRaisesRegex(anchor.AnchorBlocked, "MANIFEST_SHA_MISMATCH"):
            check(RAW.read_bytes(), sample(), manifest=b"substituted-manifest")

    def test_wrong_event_blocked(self):
        envelope = sample()
        envelope["receipt"]["event_id"] = "WRONG-EVENT"
        envelope["receipt_body_sha256"] = anchor.sha256(anchor.canonical(envelope["receipt"]))
        with self.assertRaisesRegex(anchor.AnchorBlocked, "EVENT_ID_MISMATCH"):
            check(RAW.read_bytes(), envelope)

    def test_unpinned_code_sha_blocked(self):
        envelope = sample()
        envelope["receipt"]["code_sha"] = "a" * 40
        envelope["receipt_body_sha256"] = anchor.sha256(anchor.canonical(envelope["receipt"]))
        with self.assertRaisesRegex(anchor.AnchorBlocked, "CODE_SHA_MISMATCH"):
            check(RAW.read_bytes(), envelope)

    def test_fake_owner_ack_blocked(self):
        envelope = sample()
        envelope["receipt"]["external_owner_custody"] = "EXTERNAL_ANCHOR_PASS"
        envelope["receipt_body_sha256"] = anchor.sha256(anchor.canonical(envelope["receipt"]))
        with self.assertRaisesRegex(anchor.AnchorBlocked, "RECEIPT_CUSTODY_CLAIM_INVALID"):
            check(RAW.read_bytes(), envelope)

    def test_duplicate_receipt_key_blocked(self):
        with self.assertRaisesRegex(anchor.AnchorBlocked, "DUPLICATE_RECEIPT_JSON_KEY"):
            anchor.parse_receipt(b'{"receipt":{},"receipt":{},"receipt_body_sha256":""}')

    def test_non_utc_time_blocked(self):
        with self.assertRaisesRegex(anchor.AnchorBlocked, "EXPLICIT_UTC"):
            anchor.make_receipt(
                RAW.read_bytes(), MANIFEST.read_bytes(),
                study_id="ZS03-P0-UTC-CUSTODY-FIELD-READINESS-001",
                event_id=EVENT, code_sha=CODE_SHA,
                repository="scannercrypto0-gif/zs-crypto-signals",
                raw_path="research/order025/p0-readiness/synthetic-raw-v1.txt",
                manifest_path="research/order025/p0-readiness/owner-custody-and-field-manifest-draft.md",
                creator="SYNTHETIC_CI_WRITER",
                generated_at_utc="2026-11-07T08:00:00+03:00")

    def test_non_synthetic_raw_blocked(self):
        with self.assertRaisesRegex(anchor.AnchorBlocked, "SYNTHETIC_SOURCE"):
            sample(raw=b"actual-market-data-unauthorized")

    def test_cli_emit_and_verify_restored_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / "owner-receipt.json"
            restored = Path(tmp) / "restored-raw.txt"
            restored.write_bytes(RAW.read_bytes())
            emit = subprocess.run([
                sys.executable, str(SCRIPT), "emit", "--raw", str(RAW),
                "--manifest", str(MANIFEST),
                "--study-id", "ZS03-P0-UTC-CUSTODY-FIELD-READINESS-001",
                "--event-id", EVENT, "--code-sha", CODE_SHA,
                "--repository", "scannercrypto0-gif/zs-crypto-signals",
                "--raw-path", "research/order025/p0-readiness/synthetic-raw-v1.txt",
                "--manifest-path", "research/order025/p0-readiness/owner-custody-and-field-manifest-draft.md",
                "--creator", "SYNTHETIC_CI_WRITER", "--output", str(receipt)],
                text=True, capture_output=True, timeout=15)
            self.assertEqual(emit.returncode, 0, emit.stderr)
            saved = receipt.read_bytes()
            returned = subprocess.run([
                sys.executable, str(SCRIPT), "verify",
                "--raw", str(restored),
                "--manifest", str(MANIFEST), "--receipt", str(receipt),
                "--expected-owner-file-sha256", hashlib.sha256(saved).hexdigest(),
                "--expected-code-sha", CODE_SHA, "--expected-event-id", EVENT],
                text=True, capture_output=True, timeout=15)
            self.assertEqual(returned.returncode, 0, returned.stderr)
            self.assertEqual(json.loads(returned.stdout)["custody_gate"],
                             "OWNER_CUSTODY_ACK_PENDING")
            # No overwrite of a prior receipt: preserves the evidence filename.
            again = subprocess.run([
                sys.executable, str(SCRIPT), "emit", "--raw", str(RAW),
                "--manifest", str(MANIFEST),
                "--study-id", "ZS03-P0-UTC-CUSTODY-FIELD-READINESS-001",
                "--event-id", EVENT, "--code-sha", CODE_SHA,
                "--repository", "scannercrypto0-gif/zs-crypto-signals",
                "--raw-path", "research/order025/p0-readiness/synthetic-raw-v1.txt",
                "--manifest-path", "research/order025/p0-readiness/owner-custody-and-field-manifest-draft.md",
                "--creator", "SYNTHETIC_CI_WRITER", "--output", str(receipt)],
                text=True, capture_output=True, timeout=15)
            self.assertEqual(again.returncode, 2)
            self.assertEqual(receipt.read_bytes(), saved)


if __name__ == "__main__":
    unittest.main()
