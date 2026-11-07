"""Synthetic offline negative tests for independently supplied owner digest."""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import unittest

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("owner_receipt", root / "scripts/p0-owner-receipt.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
raw = (root / "research/order025/p0-readiness/synthetic-raw-v1.txt").read_bytes()
digest = hashlib.sha256(raw).hexdigest()


class OwnerAnchorTests(unittest.TestCase):
    def test_synthetic_match_disclaims_real_external_custody(self):
        r = module.compare(raw, expected_sha256=digest, expected_size=len(raw))
        self.assertEqual(r["status"], "MATCHES_EXTERNALLY_SUPPLIED_DIGEST_ONLY")
        self.assertFalse(r["outside_writer_control_proven"])
        self.assertFalse(r["anchor_creation_time_proven"])
        self.assertEqual(r["market_pit"], "NOT_ATTESTED")

    def test_byte_mutation_rejected(self):
        with self.assertRaisesRegex(module.OwnerReceiptBlocked, "MISMATCH"):
            module.compare(b"x"+raw[1:], expected_sha256=digest,
                           expected_size=len(raw))

    def test_truncation_rejected(self):
        with self.assertRaisesRegex(module.OwnerReceiptBlocked, "MISMATCH"):
            module.compare(raw[:-1], expected_sha256=digest,
                           expected_size=len(raw))

    def test_forged_digest_rejected(self):
        with self.assertRaisesRegex(module.OwnerReceiptBlocked, "MISMATCH"):
            module.compare(raw, expected_sha256="f"*64, expected_size=len(raw))

    def test_invalid_digest_format_rejected(self):
        with self.assertRaisesRegex(module.OwnerReceiptBlocked, "INVALID"):
            module.compare(raw, expected_sha256="not-a-digest",
                           expected_size=len(raw))

    def test_invalid_size_rejected(self):
        with self.assertRaisesRegex(module.OwnerReceiptBlocked, "INVALID"):
            module.compare(raw, expected_sha256=digest, expected_size=-1)


if __name__ == "__main__":
    unittest.main()
