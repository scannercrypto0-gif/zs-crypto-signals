from datetime import datetime, timedelta, timezone
import hashlib
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from zs_smart_gate.evidence_journal import (
    BoundedSpool, SingleStudyJournal, canonical_bytes, MAX_STUDY_BYTES,
)

UTC = timezone.utc
NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)


class MemoryBackend:
    """Thread-safe offline fake; never performs network or filesystem I/O."""
    def __init__(self):
        self.data = {}
        self.reservations = {}
        self.lock = threading.Lock()
        self.offline = False
        self.corrupt_readback = False

    def read(self, key):
        with self.lock:
            if self.offline:
                raise OSError("offline")
            value = self.data.get(key)
            if value is not None and self.corrupt_readback:
                return value + b"corrupt"
            return value

    def create_if_absent(self, key, value):
        with self.lock:
            if self.offline:
                raise OSError("offline")
            if key in self.data:
                return False
            self.data[key] = bytes(value)
            return True

    def reserve_capacity(self, study_id, reservation_id, size, limit):
        with self.lock:
            if self.offline:
                raise OSError("offline")
            existing = self.reservations.get((study_id, reservation_id))
            if existing is not None:
                return existing == size
            used = sum(n for (sid, _), n in self.reservations.items() if sid == study_id)
            if used + size > limit:
                return False
            self.reservations[(study_id, reservation_id)] = size
            return True


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.backend = MemoryBackend()
        self.journal = SingleStudyJournal("study-test-001", self.backend, lambda: NOW)

    def test_claim_receipt_checksum_and_readback(self):
        self.assertTrue(self.journal.claim_before_attempts("study-test-001", "event-1"))
        payload = {"source": "fixture", "http_attempts": 0, "status": "OFFLINE_TEST"}
        digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
        self.assertTrue(self.journal.append_and_readback("event-1", payload, digest))
        self.assertFalse(self.journal.append_and_readback("event-1", payload, digest))
        receipt = self.backend.data["studies/study-test-001/receipts/event-1.json"]
        self.assertIn(digest.encode(), receipt)

    def test_duplicate_claim_and_cross_study_denied(self):
        self.assertTrue(self.journal.claim_before_attempts("study-test-001", "event-2"))
        self.assertFalse(self.journal.claim_before_attempts("study-test-001", "event-2"))
        self.assertFalse(self.journal.claim_before_attempts("other-study", "event-3"))
        self.assertFalse(self.journal.claim_before_attempts("study-test-001", "../escape"))

    def test_concurrent_duplicate_claim_has_one_winner(self):
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(
                lambda _: self.journal.claim_before_attempts("study-test-001", "same-event"),
                range(24),
            ))
        self.assertEqual(sum(results), 1)

    def test_claim_failure_or_unverified_readback_fails_closed(self):
        self.backend.offline = True
        self.assertFalse(self.journal.claim_before_attempts("study-test-001", "offline"))
        self.backend.offline = False
        self.backend.corrupt_readback = True
        self.assertFalse(self.journal.claim_before_attempts("study-test-001", "corrupt"))
        self.assertFalse(self.journal.append_and_readback("missing-claim", {}, hashlib.sha256(b"{}").hexdigest()))

    def test_bad_payload_checksum_is_rejected(self):
        self.assertTrue(self.journal.claim_before_attempts("study-test-001", "event-4"))
        self.assertFalse(self.journal.append_and_readback("event-4", {"x": 1}, "0" * 64))

    def test_study_capacity_is_bounded(self):
        self.backend.reservations[("study-test-001", "pre-filled")] = MAX_STUDY_BYTES
        self.assertFalse(self.journal.claim_before_attempts("study-test-001", "over-cap"))

    def test_spool_size_duplicate_and_24h_expiry(self):
        spool = BoundedSpool(max_bytes=5, ttl=timedelta(hours=24))
        self.assertTrue(spool.put("a", b"123", now=NOW))
        self.assertFalse(spool.put("a", b"1", now=NOW))
        self.assertFalse(spool.put("b", b"456", now=NOW))
        self.assertEqual(spool.get_for_replay("a", now=NOW + timedelta(hours=23)), b"123")
        self.assertIsNone(spool.get_for_replay("a", now=NOW + timedelta(hours=24, seconds=1)))
        self.assertEqual(spool.size_bytes, 0)

    def test_spool_rejects_naive_timestamps(self):
        with self.assertRaises(ValueError):
            BoundedSpool().put("event", b"x", now=datetime(2026, 10, 29))


if __name__ == "__main__":
    unittest.main()
