"""One-source rejection/analysis integration. No production signal path."""
from .e2e51 import analyze, capture, persist
from .pre05_offline_chain import LocalChainJournal
from .stage03_qv1_boundary import recorded_rejection_archive
from .stage05_contracts import ContractError, canonical, digest
from .stage05_custody import VerifiedUpstream


def run_chain(folder, *, session, get, decision_clock, archive, interactive, receipts, acquisition_clock=None):
    capture(receipts, get=get, **({"clock": acquisition_clock} if acquisition_clock else {}))
    decision_ms = decision_clock()
    event = analyze(receipts, decision_ms, synthetic=False)
    if event["qualification_status"] != "REJECTED" or event["signal_id"] is not None:
        raise ContractError("LIVE_QUALIFICATION_POLICY_UNAVAILABLE")
    stored, _ = persist(folder, receipts, event)
    journal = LocalChainJournal(folder / "journal.sqlite")
    identity, _ = journal.append_readback(stored)
    sha = digest(canonical(stored))
    upstream = VerifiedUpstream(LocalChainJournal(journal.path), {identity: sha})
    verified, report = recorded_rejection_archive(upstream, identity, sha)
    manifest = dict(session_id=session, source_sha256=verified["source_manifest_sha256"],
                    decision_sha256=digest(canonical(verified)), candidate_id=verified["candidate_id"],
                    event_id=verified["detection_event_key"], signal_id=None,
                    stage04_readback_sha256=sha, decision_at=verified["timestamps"]["decision_at"],
                    closed_at=verified["timestamps"]["decision_candle_close_at"],
                    stage05a="NO_QUALIFIED_SIGNAL_OBSERVED", stage05b="NOT_ATTEMPTED",
                    stage05c="NOT_ATTEMPTED", archive_sha256=report["manifest"]["sha256"])
    manifest["stage05b"] = archive(manifest, report)
    if manifest["stage05b"] != "API_ACCEPTED":
        return manifest
    manifest["stage05c"] = interactive(upstream, (identity, sha))
    return manifest
