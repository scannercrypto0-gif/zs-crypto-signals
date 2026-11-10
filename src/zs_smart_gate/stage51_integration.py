"""Trace a single captured Spot snapshot across durable readback and 05C."""
from pathlib import Path

from .e2e51 import analyze, persist
from .pre05_offline_chain import LocalChainJournal
from .stage05_contracts import canonical, digest, safe_id
from .stage05_custody import VerifiedUpstream


def prepare(folder, *, session_id, receipts, decision_ms, reviewed_readback_sha):
    """No acquisition or network. A reviewed pin is required before admission."""
    safe_id(session_id, "SESSION_ID")
    event = analyze(receipts, decision_ms, synthetic=False)
    stored, _ = persist(Path(folder), receipts, event, expected_sha=reviewed_readback_sha)
    sha = digest(canonical(stored))
    journal = LocalChainJournal(Path(folder) / "journal.sqlite")
    identity, _ = journal.append_readback(stored)
    reopened = LocalChainJournal(journal.path)
    upstream = VerifiedUpstream(reopened, {identity: reviewed_readback_sha})
    source_ref = (identity, reviewed_readback_sha)
    verified = upstream.read(*source_ref)
    manifest = {
        "schema": "zs.stage51.integration.v1",
        "scope": "RECORDED_SOURCE_REPLAY_NOT_LIVE_E2E",
        "session_id": session_id,
        "source_sha256": verified["source_manifest_sha256"],
        "decision_sha256": digest(canonical(verified)),
        "candidate_id": verified["candidate_id"],
        "event_id": verified["detection_event_key"],
        "signal_id": verified["signal_id"],
        "stage04_readback_sha256": sha,
        "scanner": verified["scan_metadata"]["scanner"],
        "setup": verified["scan_metadata"]["setup"],
        "decision_at": verified["timestamps"]["decision_at"],
        "closed_at": verified["timestamps"]["decision_candle_close_at"],
        "archive_sha256": stored["archive_sha256"],
    }
    return upstream, source_ref, manifest
