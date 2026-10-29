from datetime import datetime, timezone
import hashlib
import json
import unittest
from zs_smart_gate.evidence_journal import SingleStudyJournal, canonical_bytes
from zs_smart_gate.github_evidence_backend import GitHubEvidenceBackend, GitHubStorageError, verify_snapshot

NOW = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)

class MockContentsTransport:
    """In-memory repository simulator: no network or filesystem I/O."""
    def __init__(self):
        self.files, self.calls = {}, []
        self.fail_status = None
        self.drop_readback = False
        self.corrupt_readback = False
        self.conflict_next_put = False

    def get_file(self, path, branch):
        self.calls.append(("GET", path, branch))
        if self.fail_status:
            raise GitHubStorageError("GITHUB_READ_HTTP_" + str(self.fail_status))
        if path not in self.files:
            return None
        body = self.files[path]
        if self.drop_readback and "/claims/" in path:
            return None
        if self.corrupt_readback:
            body = body + b"tampered"
        return body, "mock-sha-" + hashlib.sha256(body).hexdigest()

    def put_file(self, path, body, branch, sha, message):
        self.calls.append(("PUT", path, branch, sha, message))
        if self.fail_status:
            raise GitHubStorageError("GITHUB_WRITE_HTTP_" + str(self.fail_status))
        if self.conflict_next_put:
            self.conflict_next_put = False
            return False
        if sha is None and path in self.files:
            return False
        if sha is not None:
            current = self.get_file(path, branch)
            if current is None or current[1] != sha:
                return False
        self.files[path] = bytes(body)
        return True

class GitHubBackendTests(unittest.TestCase):
    def setUp(self):
        self.transport = MockContentsTransport()
        self.backend = GitHubEvidenceBackend("study-mock-001", branch="evidence-study-mock-001",
                                             transport=self.transport, enabled=True)
        self.journal = SingleStudyJournal("study-mock-001", self.backend, lambda: NOW)

    def test_disabled_by_default_and_main_branch_rejected(self):
        disabled = GitHubEvidenceBackend("study-mock-001", branch="evidence-study-mock-001", transport=self.transport)
        with self.assertRaisesRegex(GitHubStorageError, "BACKEND_DISABLED"):
            disabled.read("studies/study-mock-001/claims/event-1.json")
        with self.assertRaisesRegex(ValueError, "DEDICATED_NON_MAIN_BRANCH_REQUIRED"):
            GitHubEvidenceBackend("study-mock-001", branch="main", transport=self.transport, enabled=True)

    def test_claim_receipt_and_capacity_index(self):
        self.assertTrue(self.journal.claim_before_attempts("study-mock-001", "event-1"))
        payload = {"fixture": True, "http_attempts": 0}
        digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
        self.assertTrue(self.journal.append_and_readback("event-1", payload, digest))
        index = json.loads(self.transport.files["studies/study-mock-001/_journal_index.json"])
        self.assertEqual(index["schema"], "zs-evidence-capacity-v1")
        self.assertIn("claim-event-1", index["reservations"])
        self.assertIn("receipt-event-1", index["reservations"])
        self.assertFalse(self.journal.claim_before_attempts("study-mock-001", "event-1"))

    def test_duplicate_reservation_and_study_cap(self):
        self.assertTrue(self.backend.reserve_capacity("study-mock-001", "same", 1, 10 * 1024 * 1024))
        self.assertTrue(self.backend.reserve_capacity("study-mock-001", "same", 1, 10 * 1024 * 1024))
        self.assertFalse(self.backend.reserve_capacity("study-mock-001", "same", 2, 10 * 1024 * 1024))
        self.assertFalse(self.backend.reserve_capacity("study-mock-001", "too-big", 10 * 1024 * 1024 + 1, 10 * 1024 * 1024))

    def test_conflict_timeout_403_429_and_readback_fail_closed(self):
        self.transport.conflict_next_put = True
        self.assertFalse(self.backend.reserve_capacity("study-mock-001", "race", 4, 10 * 1024 * 1024))
        for status in (403, 429, 500):
            self.transport.fail_status = status
            self.assertFalse(self.journal.claim_before_attempts("study-mock-001", "event-" + str(status)))
            self.transport.fail_status = None
        self.transport.drop_readback = True
        self.assertFalse(self.journal.claim_before_attempts("study-mock-001", "missing-readback"))
        self.transport.drop_readback = False
        self.transport.corrupt_readback = True
        self.assertFalse(self.journal.claim_before_attempts("study-mock-001", "bad-readback"))

    def test_restore_from_clean_snapshot_and_detect_tamper_or_missing(self):
        self.assertTrue(self.journal.claim_before_attempts("study-mock-001", "restore-event"))
        payload = {"fixture": "offline", "http_attempts": 0}
        digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
        self.assertTrue(self.journal.append_and_readback("restore-event", payload, digest))
        # A fresh clone is simulated by copying committed bytes into a new mapping.
        snapshot = {k: bytes(v) for k, v in self.transport.files.items() if k.endswith("_journal_index.json") or "/claims/" in k or "/receipts/" in k}
        report = verify_snapshot("study-mock-001", snapshot)
        self.assertTrue(report.ok, report.status)
        self.assertEqual(report.records_checked, 2)
        receipt = "studies/study-mock-001/receipts/restore-event.json"
        tampered = dict(snapshot)
        tampered[receipt] += b"tampered"
        self.assertEqual(verify_snapshot("study-mock-001", tampered).status, "INVALID_JSON")
        missing = {k: v for k, v in snapshot.items() if "/receipts/" not in k}
        self.assertEqual(verify_snapshot("study-mock-001", missing).status, "CLAIM_WITHOUT_RECEIPT")
        no_index = {k: v for k, v in snapshot.items() if not k.endswith("_journal_index.json")}
        self.assertEqual(verify_snapshot("study-mock-001", no_index).status, "CAPACITY_INDEX_MISSING")

    def test_invalid_paths_and_payload_checksum(self):
        with self.assertRaisesRegex(ValueError, "INVALID_RECORD_PATH"):
            self.backend.read("studies/other-study/claims/event.json")
        record = {"schema": "zs-evidence-receipt-v1", "study_id": "study-mock-001",
                  "event_id": "event-x", "recorded_at": NOW.isoformat(),
                  "payload_sha256": "0" * 64, "payload": {"x": 1}}
        path = "studies/study-mock-001/receipts/event-x.json"
        self.assertEqual(verify_snapshot("study-mock-001", {path: canonical_bytes(record)}).status,
                         "PAYLOAD_CHECKSUM_MISMATCH")

if __name__ == "__main__":
    unittest.main()
