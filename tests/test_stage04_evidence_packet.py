"""Stage04 offline contract tests; no real GitHub write, token or network."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import contextlib
import io
import json
import threading
import unittest
from unittest.mock import patch

from zs_smart_gate.evidence_journal import SingleStudyJournal, canonical_bytes
from zs_smart_gate.github_evidence_backend import (
    GitHubEvidenceBackend, GitHubStorageError,
)
from zs_smart_gate.stage04_evidence_packet import (
    MAX_CONTENTS_BYTES, make_record, prepare_manifest, persist_packet,
    restore_from_remote, sha256_hex,
)
from zs_smart_gate.stage04_canary import main as canary_main

UTC = timezone.utc
NOW = datetime(2026, 10, 30, 20, tzinfo=UTC).isoformat()
STUDY = "zs04-test-001"
BRANCH = "evidence-zs04-test-001"


class FakeGitHub:
    """Shared mocked remote storage, two independent reader objects possible."""
    def __init__(self, backing=None):
        self.files = {} if backing is None else backing
        self.lock = threading.Lock()
        self.calls = []
        self.fail_get = None
        self.fail_put = None
        self.corrupt_get = None
        self.conflict_once = False
        self.commit_then_lose_response = False

    def get_file(self, path, branch):
        with self.lock:
            self.calls.append(("GET", path, branch))
            if self.fail_get:
                raise GitHubStorageError("GITHUB_READ_HTTP_" + str(self.fail_get))
            value = self.files.get(path)
            if value is None:
                return None
            if self.corrupt_get == path:
                value += b"damaged"
            return value, "git-blob-" + sha256_hex(value)

    def put_file(self, path, body, branch, sha, message):
        with self.lock:
            self.calls.append(("PUT", path, branch))
            if self.fail_put:
                raise GitHubStorageError("GITHUB_WRITE_HTTP_" + str(self.fail_put))
            if branch != BRANCH:
                raise AssertionError("NO_MAIN_WRITE")
            if self.conflict_once:
                self.conflict_once = False
                return False
            old = self.files.get(path)
            if sha is None and old is not None:
                return False
            if sha is not None:
                if old is None or sha != "git-blob-" + sha256_hex(old):
                    return False
            self.files[path] = bytes(body)
            if self.commit_then_lose_response:
                self.commit_then_lose_response = False
                raise GitHubStorageError("GITHUB_TRANSPORT_UNAVAILABLE")
            return True


def packet(study=STUDY):
    records = {
        "raw-001": make_record(
            study_id=study, event_id="raw-001", record_type="source_snapshot",
            source_id="SYNTHETIC:OFFLINE", received_at=NOW, available_at=NOW,
            payload={"synthetic": True, "ohlcv": {"close": "100"},
                     "market_source": "NONE", "http_attempts": 0}),
        "candidate-001": make_record(
            study_id=study, event_id="candidate-001",
            record_type="research_candidate", source_id="SYNTHETIC:OFFLINE",
            received_at=NOW, available_at=NOW, candidate_status="RESEARCH_CANDIDATE",
            payload={"synthetic": True, "reason": "RESEARCH_ONLY"}),
    }
    manifest = prepare_manifest(study, records, created_at=NOW)
    return manifest, records


def make_writer(remote, study=STUDY):
    backend = GitHubEvidenceBackend(
        study, branch=BRANCH, transport=remote, enabled=True)
    return SingleStudyJournal(study, backend, lambda: datetime(2026, 10, 30, 20, tzinfo=UTC))


class Stage04EvidencePacketTests(unittest.TestCase):
    def test_manifest_claim_receipt_hash_and_independent_remote_restore(self):
        manifest, records = packet()
        self.assertEqual(manifest["retention_action"], "REVIEW_ONLY_NO_AUTOMATIC_DELETE")
        self.assertEqual(manifest["pit_status"], "PIT_UNVERIFIED")
        self.assertFalse(manifest["server_enforced_worm"])
        remote = FakeGitHub()
        result = persist_packet(make_writer(remote), manifest, records)
        self.assertTrue(result.ok, result.status)
        self.assertEqual(result.records_checked, 3)
        self.assertEqual(result.manifest_sha256, sha256_hex(canonical_bytes(manifest)))
        # Fresh clone / new process: a separate object holding copied exact bytes.
        clone = FakeGitHub({k: bytes(v) for k, v in remote.files.items()})
        restore = restore_from_remote(study_id=STUDY, branch=BRANCH, transport=clone,
                                     expected_manifest_sha256=result.manifest_sha256)
        self.assertTrue(restore.ok, restore.status)
        self.assertEqual(restore.status, "RESTORE_VERIFIED_APPLICATION_ONLY")
        self.assertEqual(restore.records_checked, 6)
        self.assertEqual(len(remote.files), 7)
        self.assertTrue(all(x[2] == BRANCH for x in remote.calls))
        receipt = json.loads(remote.files[f"studies/{STUDY}/receipts/raw-001.json"])
        self.assertEqual(receipt["payload"]["source_publication_at"], None)
        self.assertEqual(receipt["payload"]["score"], None)
        self.assertFalse(receipt["payload"]["delivery_authorized"])

    def test_duplicate_is_unknown_no_overwrite_or_blind_retry(self):
        manifest, records = packet()
        remote = FakeGitHub()
        a = persist_packet(make_writer(remote), manifest, records)
        self.assertTrue(a.ok)
        before = dict(remote.files)
        b = persist_packet(make_writer(remote), manifest, records)
        self.assertFalse(b.ok)
        self.assertEqual(b.status, "UNKNOWN_PARTIAL_OR_CONFLICT")
        self.assertEqual(b.failed_event, "manifest")
        self.assertEqual(remote.files, before)

    def test_tampered_record_manifest_and_missing_remote_are_never_restored(self):
        manifest, records = packet()
        remote = FakeGitHub()
        written = persist_packet(make_writer(remote), manifest, records)
        self.assertTrue(written.ok)
        prefix = f"studies/{STUDY}/"
        for path, mutation, expected in (
            (prefix + "receipts/raw-001.json", b"tamper", "FAIL_"),
            (prefix + "_journal_index.json", b"tamper", "FAIL_"),
            (prefix + "claims/candidate-001.json", None, "BLOCKED_"),
        ):
            with self.subTest(path=path):
                damaged = dict(remote.files)
                if mutation is None:
                    del damaged[path]
                else:
                    damaged[path] += mutation
                report = restore_from_remote(study_id=STUDY, branch=BRANCH,
                    transport=FakeGitHub(damaged),
                    expected_manifest_sha256=written.manifest_sha256)
                self.assertFalse(report.ok)
                self.assertTrue(report.status.startswith(expected), report.status)

    def test_pinned_manifest_hash_not_replaced_from_untrusted_remote(self):
        manifest, records = packet()
        remote = FakeGitHub()
        result = persist_packet(make_writer(remote), manifest, records)
        self.assertTrue(result.ok)
        changed = dict(remote.files)
        path = f"studies/{STUDY}/receipts/manifest.json"
        outer = json.loads(changed[path])
        outer["payload"]["retention_review_at"] = NOW
        changed[path] = canonical_bytes(outer)
        restored = restore_from_remote(study_id=STUDY, branch=BRANCH,
            transport=FakeGitHub(changed), expected_manifest_sha256=result.manifest_sha256)
        self.assertFalse(restored.ok)
        self.assertTrue(restored.status.startswith("FAIL_"), restored.status)

    def test_unknown_partial_on_cas_conflict_and_commit_with_lost_response(self):
        manifest, records = packet()
        for kind in ("cas", "lost"):
            with self.subTest(kind=kind):
                remote = FakeGitHub()
                if kind == "cas":
                    remote.conflict_once = True
                else:
                    remote.commit_then_lose_response = True
                result = persist_packet(make_writer(remote), manifest, records)
                self.assertEqual(result.status, "UNKNOWN_PARTIAL_OR_CONFLICT")
                self.assertFalse(result.ok)
                self.assertEqual(result.failed_event, "manifest")
                self.assertEqual(len([c for c in remote.calls if c[0] == "PUT"]),
                                 1)

    def test_403_429_503_outage_fail_closed_without_leaking_remote_body(self):
        manifest, records = packet()
        for status in (403, 429, 500, 503):
            with self.subTest(code=status):
                remote = FakeGitHub()
                remote.fail_get = status
                result = persist_packet(make_writer(remote), manifest, records)
                self.assertFalse(result.ok)
                self.assertEqual(result.status, "UNKNOWN_PARTIAL_OR_CONFLICT")
                self.assertEqual(len(remote.files), 0)
                restored = restore_from_remote(study_id=STUDY, branch=BRANCH,
                    transport=remote, expected_manifest_sha256=sha256_hex(canonical_bytes(manifest)))
                self.assertEqual(restored.status, "BLOCKED_REMOTE_UNAVAILABLE")

    def test_orphan_reservation_and_claim_only_detected_independently(self):
        manifest, records = packet()
        remote = FakeGitHub()
        wrote = persist_packet(make_writer(remote), manifest, records)
        self.assertTrue(wrote.ok)
        broken = dict(remote.files)
        del broken[f"studies/{STUDY}/receipts/candidate-001.json"]
        recovered = restore_from_remote(study_id=STUDY, branch=BRANCH,
            transport=FakeGitHub(broken), expected_manifest_sha256=wrote.manifest_sha256)
        self.assertFalse(recovered.ok)
        self.assertEqual(recovered.status, "BLOCKED_RESTORE_FILE_MISSING")
        broken = dict(remote.files)
        index_path = f"studies/{STUDY}/_journal_index.json"
        index = json.loads(broken[index_path])
        index["reservations"]["orphan-001"] = 100
        broken[index_path] = canonical_bytes(index)
        recovered = restore_from_remote(study_id=STUDY, branch=BRANCH,
            transport=FakeGitHub(broken), expected_manifest_sha256=wrote.manifest_sha256)
        self.assertEqual(recovered.status, "FAIL_ORPHAN_CAPACITY_RESERVATION")

    def test_record_validation_rejects_future_or_fake_signal_and_secrets(self):
        base = dict(study_id=STUDY, event_id="event-1",
                    record_type="source_snapshot", source_id="SYNTHETIC:OFFLINE",
                    received_at=NOW, available_at=NOW)
        with self.assertRaisesRegex(ValueError, "RECEIPT_AFTER_AVAILABILITY"):
            make_record(**{**base, "available_at": (datetime(2026,10,30,19,tzinfo=UTC)).isoformat()},
                        payload={})
        with self.assertRaisesRegex(ValueError, "UTC_TIMESTAMP_REQUIRED"):
            make_record(**{**base, "received_at": "2026-10-30T20:00:00"}, payload={})
        with self.assertRaisesRegex(ValueError, "PRODUCTION_OR_UNKNOWN_STATE_FORBIDDEN"):
            make_record(**base, candidate_status="QUALIFIED_SIGNAL", payload={})
        with self.assertRaisesRegex(ValueError, "SENSITIVE_FIELD_REJECTED"):
            make_record(**base, payload={"nested": {"api_key": "TEST_SECRET_TOKEN"}})
        with self.assertRaisesRegex(ValueError, "NON_JSON_OR_NONFINITE_PAYLOAD"):
            make_record(**base, payload={"nan": float("nan")})
        with self.assertRaisesRegex(ValueError, "CONTENTS_RECORD_SIZE_LIMIT"):
            make_record(**base, payload={"sample": "x" * MAX_CONTENTS_BYTES})

    def test_manifest_validation_checks_integrity_and_cap_not_all_time(self):
        manifest, records = packet()
        bad = {**manifest, "entries": []}
        rejected = persist_packet(make_writer(FakeGitHub()), bad, records)
        self.assertEqual(rejected.status, "REJECTED_INVALID_PACKET")
        changed = {**records, "raw-001": {**records["raw-001"], "payload": {"different": True}}}
        rejected = persist_packet(make_writer(FakeGitHub()), manifest, changed)
        self.assertEqual(rejected.status, "REJECTED_INVALID_PACKET")
        self.assertEqual(manifest["max_study_bytes"], 10 * 1024 * 1024)
        self.assertEqual(manifest["retention_review_at"],
                         (datetime.fromisoformat(NOW) + timedelta(days=30)).isoformat())

    def test_no_network_or_token_writes_without_explicit_canary_gates(self):
        with patch("zs_smart_gate.stage04_canary.urlopen",
                   side_effect=AssertionError("NETWORK_MUST_NOT_START")), \
             patch.dict("os.environ", {"GITHUB_EVENT_NAME": "push",
                                       "GITHUB_TOKEN": "FAKE_SECRET_FOR_TEST"}, clear=True):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = canary_main()
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED")
        self.assertNotIn("FAKE_SECRET_FOR_TEST", output.getvalue())


if __name__ == "__main__":
    unittest.main()
