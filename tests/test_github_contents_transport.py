"""Offline HTTP-boundary tests: no real GitHub access or credentials."""
import base64
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from zs_smart_gate.github_evidence_backend import GitHubContentsTransport, GitHubStorageError


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return self.payload


def http_error(status):
    # Error bodies must never reach the application error text.
    return HTTPError("https://api.github.com/", status, "contains secret-token", {}, io.BytesIO(b"SECRET_RESPONSE_BODY"))


class GitHubContentsHTTPTests(unittest.TestCase):
    def setUp(self):
        self.transport = GitHubContentsTransport("owner/repo", "FAKE_TEST_TOKEN_DO_NOT_USE", timeout=3.25)

    def test_get_ref_url_path_headers_timeout_and_base64(self):
        raw = b"hello\x00world"
        payload = {"encoding": "base64", "content": base64.b64encode(raw).decode("ascii"),
                   "sha": "blob-sha"}
        def stub(req, *, timeout):
            self.assertEqual(timeout, 3.25)
            self.assertEqual(req.get_method(), "GET")
            parts = urlsplit(req.full_url)
            self.assertEqual(parts.scheme, "https")
            self.assertEqual(parts.netloc, "api.github.com")
            self.assertEqual(parts.path, "/repos/owner/repo/contents/studies/s%20one/claims/a%20b.json")
            self.assertEqual(parse_qs(parts.query), {"ref": ["evidence/test branch"]})
            self.assertEqual(req.get_header("Authorization"), "Bearer FAKE_TEST_TOKEN_DO_NOT_USE")
            self.assertEqual(req.get_header("X-github-api-version"), "2022-11-28")
            return FakeResponse(200, payload)
        with patch("zs_smart_gate.github_evidence_backend.urlopen", side_effect=stub) as mocked:
            self.assertEqual(self.transport.get_file("studies/s one/claims/a b.json", "evidence/test branch"),
                             (raw, "blob-sha"))
            mocked.assert_called_once()

    def test_put_create_update_payload_branch_and_sha(self):
        calls = []
        def stub(req, *, timeout):
            self.assertEqual(timeout, 3.25)
            self.assertEqual(req.get_method(), "PUT")
            self.assertEqual(urlsplit(req.full_url).path, "/repos/owner/repo/contents/studies/one/receipt%20a.json")
            self.assertEqual(req.get_header("Content-type"), "application/json")
            data = json.loads(req.data)
            calls.append(data)
            self.assertEqual(data["branch"], "evidence-only")
            self.assertEqual(base64.b64decode(data["content"], validate=True), b"synthetic")
            self.assertTrue(data["message"].startswith("evidence journal: "))
            return FakeResponse(201 if len(calls) == 1 else 200,
                                {"content": {"sha": "new-blob"}, "commit": {"sha": "new-commit"}})
        with patch("zs_smart_gate.github_evidence_backend.urlopen", side_effect=stub):
            self.assertTrue(self.transport.put_file("studies/one/receipt a.json", b"synthetic", "evidence-only",
                                                    None, "new"))
            self.assertTrue(self.transport.put_file("studies/one/receipt a.json", b"synthetic", "evidence-only",
                                                    "prior-sha", "update"))
        self.assertNotIn("sha", calls[0])
        self.assertEqual(calls[1]["sha"], "prior-sha")

    def test_get_404_missing_but_other_http_is_sanitized(self):
        with patch("zs_smart_gate.github_evidence_backend.urlopen", side_effect=http_error(404)):
            self.assertIsNone(self.transport.get_file("x", "branch"))
        for status in (403, 429, 500, 503):
            with self.subTest(status=status):
                with patch("zs_smart_gate.github_evidence_backend.urlopen", side_effect=http_error(status)):
                    with self.assertRaisesRegex(GitHubStorageError, "^GITHUB_READ_HTTP_" + str(status) + "$") as cm:
                        self.transport.get_file("x", "branch")
                    self.assertNotIn("SECRET", str(cm.exception))
                    self.assertNotIn("TOKEN", str(cm.exception))

    def test_put_conflict_and_rejected_http_are_fail_closed(self):
        for status in (409, 422):
            with self.subTest(status=status):
                with patch("zs_smart_gate.github_evidence_backend.urlopen", side_effect=http_error(status)):
                    self.assertFalse(self.transport.put_file("x", b"a", "branch", None, "test"))
        for status in (403, 429, 500, 502):
            with self.subTest(status=status):
                with patch("zs_smart_gate.github_evidence_backend.urlopen", side_effect=http_error(status)):
                    with self.assertRaisesRegex(GitHubStorageError, "^GITHUB_WRITE_HTTP_" + str(status) + "$") as cm:
                        self.transport.put_file("x", b"a", "branch", None, "test")
                    self.assertNotIn("SECRET", str(cm.exception))

    def test_explicit_timeout_and_urlerror_both_methods(self):
        for error in (TimeoutError("private timeout detail"), URLError("private network detail"),
                      OSError("private socket detail")):
            for method in ("get", "put"):
                with self.subTest(error=type(error).__name__, method=method):
                    with patch("zs_smart_gate.github_evidence_backend.urlopen", side_effect=error):
                        with self.assertRaisesRegex(GitHubStorageError, "^GITHUB_TRANSPORT_UNAVAILABLE$") as cm:
                            if method == "get":
                                self.transport.get_file("x", "branch")
                            else:
                                self.transport.put_file("x", b"a", "branch", None, "test")
                        self.assertNotIn("private", str(cm.exception))

    def test_get_malformed_response_fail_closed(self):
        malformed = [b"{", b"[]", b"{}", b'{"sha":"x","encoding":"base64","content":"!!!"}',
                     b'{"sha":"x","encoding":"utf-8","content":"YQ=="}',
                     b'{"sha":"","encoding":"base64","content":"YQ=="}',
                     b'{"sha":9,"encoding":"base64","content":"YQ=="}']
        for raw in malformed:
            with self.subTest(raw=raw):
                with patch("zs_smart_gate.github_evidence_backend.urlopen", return_value=FakeResponse(200, raw)):
                    with self.assertRaisesRegex(GitHubStorageError, "^GITHUB_READ_RESPONSE_INVALID$"):
                        self.transport.get_file("x", "branch")

    def test_put_malformed_success_response_fail_closed(self):
        bad = [b"{", b"[]", b"{}", b'{"content":{"sha":"x"}}',
               b'{"content":{"sha":""},"commit":{"sha":"y"}}']
        for raw in bad:
            with self.subTest(raw=raw):
                with patch("zs_smart_gate.github_evidence_backend.urlopen", return_value=FakeResponse(201, raw)):
                    with self.assertRaisesRegex(GitHubStorageError, "^GITHUB_WRITE_RESPONSE_INVALID$"):
                        self.transport.put_file("x", b"a", "branch", None, "test")

    def test_unexpected_success_status_is_rejected(self):
        for method in ("get", "put"):
            with self.subTest(method=method):
                with patch("zs_smart_gate.github_evidence_backend.urlopen", return_value=FakeResponse(202, {})):
                    with self.assertRaisesRegex(GitHubStorageError,
                                                "^GITHUB_READ_HTTP_202$" if method == "get" else "^GITHUB_WRITE_HTTP_202$"):
                        if method == "get":
                            self.transport.get_file("x", "branch")
                        else:
                            self.transport.put_file("x", b"a", "branch", None, "test")

    def test_constructor_rejects_bad_scope_and_timeout(self):
        for repo in ("owner", "owner/repo/extra", "owner/repo?x=1"):
            with self.assertRaisesRegex(ValueError, "INVALID_REPOSITORY"):
                GitHubContentsTransport(repo, "FAKE_TEST_TOKEN")
        for timeout in (0, -1, 16):
            with self.assertRaisesRegex(ValueError, "INVALID_TIMEOUT"):
                GitHubContentsTransport("owner/repo", "FAKE_TEST_TOKEN", timeout=timeout)


if __name__ == "__main__":
    unittest.main()
