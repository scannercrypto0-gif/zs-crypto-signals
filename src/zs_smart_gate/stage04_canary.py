"""Manual, synthetic-only GitHub Actions Stage04 canary. NEVER imported by CI tests.

The user-facing workflow additionally requires PM-reviewed SHA and a positive
owner accounting check. Code never contacts Binance or any paid service.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .evidence_journal import SingleStudyJournal
from .github_evidence_backend import GitHubContentsTransport, GitHubEvidenceBackend
from .stage04_evidence_packet import (
    make_record, prepare_manifest, persist_packet, restore_from_remote,
)

MAX_CONTENTS_OPERATIONS = 64
CONFIRM = "ONE_SYNTHETIC_CANARY_PM_REVIEWED"
_SHA = re.compile(r"^[a-f0-9]{40}$")


class LimitedTransport:
    """One process: bounded HTTP operation accounting, no retries."""
    def __init__(self, backend: GitHubContentsTransport, count: dict):
        self.backend = backend
        self.count = count

    def _spend(self, kind: str):
        if self.count["GET"] + self.count["PUT"] >= MAX_CONTENTS_OPERATIONS:
            raise RuntimeError("API_OPERATION_BUDGET_EXCEEDED")
        self.count[kind] += 1

    def get_file(self, path: str, branch: str):
        self._spend("GET")
        return self.backend.get_file(path, branch)

    def put_file(self, path: str, body: bytes, branch: str,
                 sha: str | None, message: str) -> bool:
        self._spend("PUT")
        return self.backend.put_file(path, body, branch, sha, message)


def _branch_once(repository: str, token: str, branch: str, sha: str):
    # This is the *only* POST and creates an isolated branch; no PUT on main.
    url = "https://api.github.com/repos/" + repository + "/git/refs"
    body = json.dumps({"ref": "refs/heads/" + branch, "sha": sha}).encode()
    req = Request(url, data=body, method="POST", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "zs-stage04-synthetic-canary",
    })
    try:
        with urlopen(req, timeout=5) as response:
            if response.status != 201:
                raise RuntimeError("BRANCH_CREATION_REJECTED")
            result = json.loads(response.read(32_768))
            if result.get("ref") != "refs/heads/" + branch:
                raise RuntimeError("BRANCH_CREATION_RESPONSE_INVALID")
    except HTTPError as exc:
        # Do not read or print HTTP response bodies or auth headers.
        if exc.code in (409, 422):
            raise RuntimeError("BRANCH_ALREADY_EXISTS_OR_CONFLICT") from None
        raise RuntimeError("BRANCH_HTTP_" + str(exc.code)) from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError("BRANCH_NETWORK_BLOCKED") from None


def main() -> int:
    """One manual canary per approved SHA. STOP on any ambiguous failure."""
    result = {"stage": "ZS04_SYNTHETIC_CANARY", "status": "BLOCKED",
              "scientific_pit": "PIT_UNVERIFIED", "score": None,
              "signal_id": None, "market_http_attempts": 0}
    try:
        if (os.getenv("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.getenv("GITHUB_REF") != "refs/heads/main"
            or os.getenv("ZS_CANARY_CONFIRM") != CONFIRM
            or os.getenv("ZS_CANARY_FREE_QUOTA_CONFIRMED") != "YES"
            or os.getenv("ZS_CANARY_PM_REVIEW_CONFIRMED") != "YES"):
            raise RuntimeError("MANUAL_PM_COST_GATES_NOT_MET")
        sha = os.environ["GITHUB_SHA"]
        if not _SHA.fullmatch(sha) or os.getenv("ZS_CANARY_APPROVED_SHA") != sha:
            raise RuntimeError("PINNED_APPROVED_MAIN_SHA_REQUIRED")
        repository = os.environ["GITHUB_REPOSITORY"]
        token = os.environ["GITHUB_TOKEN"]
        if not token:
            raise RuntimeError("EPHEMERAL_WORKFLOW_TOKEN_REQUIRED")
        # Constructor validates repo; never persist token outside memory.
        transport = GitHubContentsTransport(repository, token, timeout=5)
        branch = "evidence-stage04-canary-" + sha[:16]
        study_id = "zs04-canary-" + sha[:16]
        result.update({"head_sha": sha, "branch": branch, "study_id": study_id})
        _branch_once(repository, token, branch, sha)  # NO RETRY.
        clock = datetime.now(timezone.utc).isoformat()
        records = {
            "source-001": make_record(
                study_id=study_id, event_id="source-001",
                record_type="source_snapshot", source_id="SYNTHETIC:NO_MARKET",
                received_at=clock, available_at=clock,
                payload={"synthetic": True, "market_source": "NONE",
                         "http_attempts": 0, "raw_fixture": {"close": "100"}},
            ),
            "candidate-001": make_record(
                study_id=study_id, event_id="candidate-001",
                record_type="research_candidate", source_id="SYNTHETIC:NO_MARKET",
                received_at=clock, available_at=clock,
                candidate_status="RESEARCH_CANDIDATE",
                payload={"synthetic": True, "market_source": "NONE",
                         "http_attempts": 0, "reason": "CANARY_ONLY"},
            ),
        }
        manifest = prepare_manifest(study_id, records, created_at=clock)
        counts = {"GET": 0, "PUT": 0}
        writer = LimitedTransport(transport, counts)
        backend = GitHubEvidenceBackend(
            study_id, branch=branch, transport=writer, enabled=True)
        journal = SingleStudyJournal(study_id, backend,
                                     lambda: datetime.now(timezone.utc))
        stored = persist_packet(journal, manifest, records)
        result.update({"write_status": stored.status,
                       "manifest_sha256": stored.manifest_sha256,
                       "records_written": stored.records_checked})
        if not stored.ok:
            raise RuntimeError("WRITE_READBACK_UNKNOWN_STOP_NO_RETRY")
        # Fresh transport instance (new GETs, no in-memory repository cache).
        remote = LimitedTransport(
            GitHubContentsTransport(repository, token, timeout=5), counts)
        restored = restore_from_remote(
            study_id=study_id, branch=branch, transport=remote,
            expected_manifest_sha256=stored.manifest_sha256)
        result.update({"restore_status": restored.status,
                       "restore_records_checked": restored.records_checked,
                       "github_contents_get": counts["GET"],
                       "github_contents_put": counts["PUT"],
                       "github_branch_posts": 1})
        if not restored.ok:
            raise RuntimeError("RESTORE_BLOCKED_OR_FAILED_STOP_NO_RETRY")
        result["status"] = "APPLICATION_WRITE_READBACK_RESTORE_VERIFIED"
    except Exception as exc:
        # Avoid displaying token, JWT, headers, URL query or server response.
        reason = str(exc)
        safe = reason if re.fullmatch(r"[A-Z0-9_]{4,100}", reason) else "CANARY_BLOCKED_REDACTED"
        result["reason_code"] = safe
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "APPLICATION_WRITE_READBACK_RESTORE_VERIFIED" else 2


if __name__ == "__main__":
    sys.exit(main())
