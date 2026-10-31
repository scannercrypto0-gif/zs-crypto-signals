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
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from zs_smart_gate.evidence_journal import SingleStudyJournal, canonical_bytes
from zs_smart_gate.github_evidence_backend import (
    GitHubEvidenceBackend, GitHubStorageError,
)
from zs_smart_gate.stage04_evidence_packet import (
    MAX_CONTENTS_BYTES, make_record, prepare_manifest, persist_packet,
    restore_from_remote, sha256_hex,
)
from zs_smart_gate.stage04_canary import (main as canary_main, _branch_once,
                                          LimitedTransport, MAX_CONTENTS_OPERATIONS,
                                          CONFIRM)

UTC = timezone.utc
NOW = datetime(2026, 10, 30, 20, tzinfo=UTC).isoformat()
STUDY = "zs04-test-001"
BRANCH = "evidence-zs04-test-001"


class FakeGitHub:
    """Shared mocked remote storage, two independent reader objects possible."""
    def __init__(self, backing=None, allowed_branch=BRANCH):
        self.files = {} if backing is None else backing
        self.allowed_branch = allowed_branch
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
            if branch != self.allowed_branch:
                raise AssertionError("UNEXPECTED_EVIDENCE_BRANCH")
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
            if branch != self.allowed_branch:
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
        with self.assertRaisesRegex(ValueError, "UNVERIFIED_PRODUCTION_OR_PIT_VALUE"):
            make_record(**base, payload={"analysis": {"score": 92}})
        with self.assertRaisesRegex(ValueError, "UNVERIFIED_PRODUCTION_OR_PIT_VALUE"):
            make_record(**base, payload={"analysis": {"signal_id": "fake-live"}})
        with self.assertRaisesRegex(ValueError, "NON_JSON_OR_NONFINITE_PAYLOAD"):
            make_record(**base, payload={"nan": float("nan")})
        with self.assertRaisesRegex(ValueError, "CONTENTS_RECORD_SIZE_LIMIT"):
            make_record(**base, payload={"sample": "x" * MAX_CONTENTS_BYTES})

    def test_rejects_unapproved_extra_fields_and_claim_after_receipt(self):
        manifest, records = packet()
        modified = {**records,
                    "raw-001": {**records["raw-001"], "extra": "not in schema"}}
        result = persist_packet(make_writer(FakeGitHub()), manifest, modified)
        self.assertEqual(result.status, "REJECTED_INVALID_PACKET")
        remote = FakeGitHub()
        saved = persist_packet(make_writer(remote), manifest, records)
        self.assertTrue(saved.ok)
        corrupt = dict(remote.files)
        claim = f"studies/{STUDY}/claims/raw-001.json"
        obj = json.loads(corrupt[claim])
        obj["claimed_at"] = "2099-01-01T00:00:00+00:00"
        corrupt[claim] = canonical_bytes(obj)
        restore = restore_from_remote(study_id=STUDY, branch=BRANCH,
            transport=FakeGitHub(corrupt),
            expected_manifest_sha256=saved.manifest_sha256)
        self.assertEqual(restore.status, "FAIL_CLAIM_AFTER_RECEIPT")

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



class MockRefResponse:
    """Fake REST response; never opens a network socket."""
    def __init__(self, status, payload):
        self.status = status
        self.payload = (payload if isinstance(payload, bytes)
                        else json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size=None):
        if size is not None and len(self.payload) > size:
            return self.payload[:size]
        return self.payload


class Stage04CanaryAuthorizedMockTests(unittest.TestCase):
    """Exercise the ACTUAL authorized code path with mocked GitHub REST only."""

    SHA = "a" * 40
    REPO = "scannercrypto0-gif/zs-crypto-signals"
    TOKEN = "FAKE_TEST_TOKEN_NEVER_A_CREDENTIAL"

    def env(self):
        return {
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": "refs/heads/main",
            "ZS_CANARY_CONFIRM": CONFIRM,
            "ZS_CANARY_FREE_QUOTA_CONFIRMED": "YES",
            "ZS_CANARY_PM_REVIEW_CONFIRMED": "YES",
            "GITHUB_SHA": self.SHA,
            "ZS_CANARY_APPROVED_SHA": self.SHA,
            "GITHUB_REPOSITORY": self.REPO,
            "GITHUB_TOKEN": self.TOKEN,
        }

    def test_branch_once_sends_one_post_and_requires_ref_and_base_sha(self):
        branch = "evidence-stage04-canary-" + self.SHA[:16]
        calls = []
        def fake_post(req, *, timeout):
            calls.append(req)
            self.assertEqual(req.get_method(), "POST")
            self.assertEqual(urlsplit(req.full_url).scheme, "https")
            self.assertEqual(urlsplit(req.full_url).netloc, "api.github.com")
            self.assertEqual(urlsplit(req.full_url).path,
                             "/repos/" + self.REPO + "/git/refs")
            self.assertEqual(timeout, 5)
            self.assertEqual(json.loads(req.data),
                             {"ref": "refs/heads/" + branch, "sha": self.SHA})
            self.assertEqual(req.get_header("Authorization"), "Bearer " + self.TOKEN)
            return MockRefResponse(201, {
                "ref": "refs/heads/" + branch,
                "object": {"type": "commit", "sha": self.SHA}})
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("REAL_NETWORK_FORBIDDEN")), \
             patch("zs_smart_gate.stage04_canary.urlopen", side_effect=fake_post):
            self.assertIsNone(_branch_once(self.REPO, self.TOKEN, branch, self.SHA))
        self.assertEqual(len(calls), 1)

    def test_branch_once_rejects_success_shape_status_and_sha_mismatch(self):
        branch = "evidence-stage04-canary-" + self.SHA[:16]
        cases = (
            (200, {"ref": "refs/heads/" + branch, "object": {"sha": self.SHA}},
             "BRANCH_CREATION_REJECTED"),
            (202, {"ref": "refs/heads/" + branch, "object": {"sha": self.SHA}},
             "BRANCH_CREATION_REJECTED"),
            (201, {"ref": "refs/heads/other", "object": {"sha": self.SHA}},
             "BRANCH_CREATION_RESPONSE_INVALID"),
            (201, {"ref": "refs/heads/" + branch, "object": {"sha": "b" * 40}},
             "BRANCH_CREATION_RESPONSE_INVALID"),
            (201, {"ref": "refs/heads/" + branch},
             "BRANCH_CREATION_RESPONSE_INVALID"),
            (201, [], "BRANCH_CREATION_RESPONSE_INVALID"),
            (201, b"broken-json-with-FAKE_SECRET", "BRANCH_CREATION_RESPONSE_INVALID"),
        )
        for status, payload, expected in cases:
            with self.subTest(status=status, payload=type(payload).__name__):
                called = []
                def fake_post(req, *, timeout):
                    called.append(req.get_method())
                    return MockRefResponse(status, payload)
                with patch("zs_smart_gate.stage04_canary.urlopen",
                           side_effect=fake_post):
                    with self.assertRaisesRegex(RuntimeError, "^" + expected + "$") as exc:
                        _branch_once(self.REPO, self.TOKEN, branch, self.SHA)
                self.assertEqual(called, ["POST"])
                self.assertNotIn(self.TOKEN, str(exc.exception))
                self.assertNotIn("FAKE_SECRET", str(exc.exception))

    def test_branch_once_http_denial_conflict_and_network_timeout_no_retry(self):
        branch = "evidence-stage04-canary-" + self.SHA[:16]
        for status, expected in (
            (403, "BRANCH_HTTP_403"),
            (409, "BRANCH_ALREADY_EXISTS_OR_CONFLICT"),
            (422, "BRANCH_ALREADY_EXISTS_OR_CONFLICT"),
        ):
            with self.subTest(status=status):
                calls = []
                def fake_post(req, *, timeout):
                    calls.append(req.get_method())
                    raise HTTPError(req.full_url, status, "FAKE_SECRET",
                                    {}, io.BytesIO(b"FAKE_SECRET_RESPONSE"))
                with patch("zs_smart_gate.stage04_canary.urlopen",
                           side_effect=fake_post):
                    with self.assertRaisesRegex(RuntimeError, "^" + expected + "$") as exc:
                        _branch_once(self.REPO, self.TOKEN, branch, self.SHA)
                self.assertEqual(calls, ["POST"])
                self.assertNotIn("FAKE_SECRET", str(exc.exception))
        for exception in (
            TimeoutError("FAKE_SECRET_TIMEOUT"),
            URLError("FAKE_SECRET_NETWORK"),
            OSError("FAKE_SECRET_OS"),
        ):
            with self.subTest(type=type(exception).__name__):
                calls = []
                def failed_post(req, *, timeout):
                    calls.append(req.get_method())
                    raise exception
                with patch("zs_smart_gate.stage04_canary.urlopen",
                           side_effect=failed_post):
                    with self.assertRaisesRegex(RuntimeError,
                                                "^BRANCH_NETWORK_BLOCKED$") as exc:
                        _branch_once(self.REPO, self.TOKEN, branch, self.SHA)
                self.assertEqual(calls, ["POST"])
                self.assertNotIn("FAKE_SECRET", str(exc.exception))

    def run_authorized_fixture(self, *, max_operations=None, branch_status=201):
        """Call canary_main itself; fake 1 POST and 2 independent Contents clients."""
        branch = "evidence-stage04-canary-" + self.SHA[:16]
        shared_files = {}
        instances = []
        post_attempts = []

        def fake_factory(repository, token, *, timeout):
            self.assertEqual(repository, self.REPO)
            self.assertEqual(token, self.TOKEN)
            self.assertEqual(timeout, 5)
            fake = FakeGitHub(backing=shared_files, allowed_branch=branch)
            instances.append(fake)
            return fake

        def fake_post(req, *, timeout):
            self.assertEqual(req.get_method(), "POST")
            self.assertEqual(timeout, 5)
            self.assertEqual(json.loads(req.data),
                             {"ref": "refs/heads/" + branch, "sha": self.SHA})
            post_attempts.append(req.get_method())
            if branch_status != 201:
                raise HTTPError(req.full_url, branch_status, "FAKE_SECRET",
                                {}, io.BytesIO(b"FAKE_SECRET_RESPONSE"))
            return MockRefResponse(201, {
                "ref": "refs/heads/" + branch, "object": {"sha": self.SHA}})

        limited = (contextlib.nullcontext() if max_operations is None else
                   patch("zs_smart_gate.stage04_canary.MAX_CONTENTS_OPERATIONS",
                         max_operations))
        output = io.StringIO()
        with patch.dict("os.environ", self.env(), clear=True), limited, \
             patch("urllib.request.urlopen",
                   side_effect=AssertionError("UNPATCHED_NETWORK_FORBIDDEN")), \
             patch("zs_smart_gate.stage04_canary.urlopen", side_effect=fake_post), \
             patch("zs_smart_gate.stage04_canary.GitHubContentsTransport",
                   side_effect=fake_factory), \
             contextlib.redirect_stdout(output):
            exit_code = canary_main()
        text = output.getvalue()
        self.assertNotIn(self.TOKEN, text)
        self.assertNotIn("FAKE_SECRET", text)
        return exit_code, json.loads(text), post_attempts, instances, shared_files

    def test_authorized_main_one_branch_full_write_readback_fresh_restore(self):
        code, row, posts, clients, files = self.run_authorized_fixture()
        self.assertEqual(code, 0, row)
        self.assertEqual(row["status"],
                         "APPLICATION_WRITE_READBACK_RESTORE_VERIFIED")
        self.assertEqual(posts, ["POST"])
        self.assertEqual(len(clients), 2)  # independently constructed transport
        self.assertIsNot(clients[0], clients[1])
        self.assertEqual(row["head_sha"], self.SHA)
        self.assertEqual(row["write_status"],
                         "WRITE_READBACK_VERIFIED_APPLICATION_ONLY")
        self.assertEqual(row["restore_status"],
                         "RESTORE_VERIFIED_APPLICATION_ONLY")
        self.assertEqual(row["records_written"], 3)
        self.assertEqual(row["restore_records_checked"], 6)
        self.assertEqual(row["github_contents_get"], 35)
        self.assertEqual(row["github_contents_put"], 12)
        self.assertEqual(row["github_branch_posts"], 1)
        self.assertEqual(len(files), 7)
        self.assertEqual(len([c for c in clients[0].calls if c[0] == "PUT"]), 12)
        self.assertEqual(len([c for c in clients[1].calls if c[0] == "GET"]), 8)
        self.assertLessEqual(row["github_contents_get"] + row["github_contents_put"],
                             MAX_CONTENTS_OPERATIONS)
        self.assertTrue(all(c[2] == row["branch"] for client in clients
                            for c in client.calls))
        self.assertTrue(all(path.startswith("studies/" + row["study_id"] + "/")
                            for path in files))
        self.assertEqual(row["scientific_pit"], "PIT_UNVERIFIED")
        self.assertEqual(row["market_http_attempts"], 0)
        self.assertIsNone(row["score"])
        self.assertIsNone(row["signal_id"])
        manifest = json.loads(files[
            "studies/" + row["study_id"] + "/receipts/manifest.json"])["payload"]
        self.assertEqual(manifest["pit_status"], "PIT_UNVERIFIED")
        self.assertFalse(manifest["server_enforced_worm"])
        self.assertEqual(row["manifest_sha256"], sha256_hex(canonical_bytes(manifest)))
        raw = json.loads(files[
            "studies/" + row["study_id"] + "/receipts/source-001.json"])["payload"]
        self.assertTrue(raw["payload"]["synthetic"])
        self.assertEqual(raw["payload"]["market_source"], "NONE")

    def test_authorized_main_branch_403_or_422_blocks_before_any_write(self):
        for status, reason in (
            (403, "BRANCH_HTTP_403"),
            (422, "BRANCH_ALREADY_EXISTS_OR_CONFLICT"),
        ):
            with self.subTest(status=status):
                code, row, posts, clients, files = self.run_authorized_fixture(
                    branch_status=status)
                self.assertEqual(code, 2)
                self.assertEqual(row["status"], "BLOCKED")
                self.assertEqual(row["reason_code"], reason)
                self.assertEqual(posts, ["POST"])
                self.assertEqual(len(clients), 1)  # ctor only; no GET/PUT
                self.assertEqual(clients[0].calls, [])
                self.assertEqual(files, {})
                self.assertEqual(row["market_http_attempts"], 0)

    def test_authorized_main_stops_at_operation_ceiling_without_retry(self):
        code, row, posts, clients, files = self.run_authorized_fixture(
            max_operations=8)
        self.assertEqual(code, 2)
        self.assertEqual(row["status"], "BLOCKED")
        self.assertEqual(row["reason_code"], "WRITE_READBACK_UNKNOWN_STOP_NO_RETRY")
        self.assertEqual(row["write_status"], "UNKNOWN_PARTIAL_OR_CONFLICT")
        self.assertEqual(posts, ["POST"])
        self.assertEqual(len(clients), 1)
        self.assertEqual(len(clients[0].calls), 8)
        self.assertEqual(row["market_http_attempts"], 0)
        self.assertTrue(files)  # ambiguous partial data, NEVER claim restoration
        self.assertNotIn("restore_status", row)

    def test_operation_budget_rejects_65th_request_before_transport(self):
        branch = "evidence-stage04-canary-" + self.SHA[:16]
        fake = FakeGitHub(allowed_branch=branch)
        counts = {"GET": 0, "PUT": 0}
        limited = LimitedTransport(fake, counts)
        for _ in range(MAX_CONTENTS_OPERATIONS):
            self.assertIsNone(limited.get_file("studies/x/claims/a.json", branch))
        self.assertEqual(counts, {"GET": MAX_CONTENTS_OPERATIONS, "PUT": 0})
        with self.assertRaisesRegex(RuntimeError, "^API_OPERATION_BUDGET_EXCEEDED$"):
            limited.put_file("studies/x/claims/a.json", b"not-written",
                             branch, None, "never")
        self.assertEqual(len(fake.calls), MAX_CONTENTS_OPERATIONS)
        self.assertEqual(counts["PUT"], 0)

    def test_sha_gate_prevents_post_even_with_other_approvals(self):
        env = self.env()
        env["ZS_CANARY_APPROVED_SHA"] = "b" * 40
        output = io.StringIO()
        with patch.dict("os.environ", env, clear=True), \
             patch("zs_smart_gate.stage04_canary.urlopen",
                   side_effect=AssertionError("NO_BRANCH_POST_ALLOWED")), \
             patch("zs_smart_gate.stage04_canary.GitHubContentsTransport",
                   side_effect=AssertionError("NO_CONTENTS_CLIENT_ALLOWED")), \
             contextlib.redirect_stdout(output):
            code = canary_main()
        row = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(row["status"], "BLOCKED")
        self.assertEqual(row["reason_code"], "PINNED_APPROVED_MAIN_SHA_REQUIRED")
        self.assertNotIn(self.TOKEN, output.getvalue())



if __name__ == "__main__":
    unittest.main()
