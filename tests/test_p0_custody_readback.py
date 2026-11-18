"""P0: independent read-only checkout of a previously private-written synthetic fixture.

This suite runs under GitHub Actions with contents:read and no persisted token.
It is an integrity/restore canary, NOT WORM or a real-market PIT attestation.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

FIXTURE = Path(__file__).resolve().parents[1] / "research/order025/p0-readiness/synthetic-raw-v1.txt"
EXPECTED_SHA256 = "da71f78daf4ae57ff5b984353611c5e9ae17731eda2f009a17ee0dce5bb48165"
EXPECTED_LENGTH = 153
MARKER = b"origin=SYNTHETIC_ONLY\n"


def receipt(raw: bytes) -> tuple[int, str]:
    return len(raw), hashlib.sha256(raw).hexdigest()


def assert_verified(raw: bytes) -> None:
    if receipt(raw) != (EXPECTED_LENGTH, EXPECTED_SHA256):
        raise ValueError("SHA256_OR_SIZE_MISMATCH")
    if MARKER not in raw or b"market_requests=0\n" not in raw:
        raise ValueError("NOT_SYNTHETIC_SOURCE")
    if raw.count(b"payload=") != 1:
        raise ValueError("MISSING_OR_DUPLICATE_PAYLOAD")


class PrivateCustodyReadbackTest(unittest.TestCase):
    def test_raw_private_readback_and_fresh_restore(self):
        raw = FIXTURE.read_bytes()
        assert_verified(raw)
        with tempfile.TemporaryDirectory(prefix="zs03-p0-readback-") as d:
            restored = Path(d) / "clean-restore" / "raw.bin"
            restored.parent.mkdir(parents=True)
            restored.write_bytes(raw)
            self.assertEqual(restored.read_bytes(), raw)
            assert_verified(restored.read_bytes())
        print("SYNTHETIC_PRIVATE_CHECKOUT_READBACK_RESTORE_SHA256_VERIFIED", EXPECTED_SHA256)

    def test_mutation_fail_closed(self):
        raw = FIXTURE.read_bytes()
        with self.assertRaisesRegex(ValueError, "SHA256_OR_SIZE_MISMATCH"):
            assert_verified(raw[:-1] + b"x")

    def test_missing_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "SHA256_OR_SIZE_MISMATCH"):
            assert_verified(b"")

    def test_duplicate_fail_closed(self):
        raw = FIXTURE.read_bytes()
        with self.assertRaisesRegex(ValueError, "SHA256_OR_SIZE_MISMATCH"):
            assert_verified(raw + raw)

    def test_truncation_fail_closed(self):
        raw = FIXTURE.read_bytes()
        with self.assertRaisesRegex(ValueError, "SHA256_OR_SIZE_MISMATCH"):
            assert_verified(raw[:-1])


if __name__ == "__main__":
    unittest.main()
