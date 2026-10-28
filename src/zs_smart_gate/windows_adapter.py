"""Prepared adapter into accepted 03B1/03A/core; injected offline tests only.

No public transport is wired or activated. A future reviewed transport must meet
deadline and physical-attempt hooks; this module is not LIVE authorization.
"""
from datetime import datetime, timezone
from typing import Protocol

from .binance_live import LiveBlocked, ALLOW_PATHS
from .stage03b1_live import probe_once
from .stage03a_contracts import Horizon
from .windows_runner import admission, ELIGIBLE

CUTOFF = datetime(2026, 10, 29, 13, tzinfo=timezone.utc)


class GitHubEvidence(Protocol):
    """Owner-gated interface; no backend or credential is implemented."""
    def readback(self, event_id: str) -> dict | None: ...
    def append_once(self, event_id: str, checksum: str, payload: bytes) -> str: ...


def live_gate(now, *, pm_accepted=False, timer_verified=False, clock_verified=False,
              evidence_approved=False):
    if now < CUTOFF:
        return 'LIVE_GATE_BLOCKED: FROZEN_03B3_ACTIVE'
    for name, passed in [('PM_PINNED_CODE', pm_accepted), ('LOCAL_TIMER', timer_verified),
                         ('INDEPENDENT_EXCHANGE_CLOCK', clock_verified),
                         ('GITHUB_EVIDENCE_POLICY', evidence_approved)]:
        if not passed:
            return 'LIVE_GATE_BLOCKED: ' + name
    return 'LIVE_GATE_BLOCKED: NO_APPROVED_TRANSPORT_IMPLEMENTED'


def research_fixture(event, scope, proof, *, getter, clock, monotonic):
    """Reuse accepted candidate/reconcile path with an explicit fixture getter.

One BTCUSDT parent per batch; 30m uses 5m history, 4h uses accepted
1h children plus 5m history. Never relabel this as the frozen 03B3 study.
"""
    now, start = clock(), monotonic()
    if event.symbol != 'BTCUSDT' or event.horizon not in ('30m', '4h'):
        raise ValueError('UNAPPROVED_SCOPE')
    if admission(event, scope, now, proof) != ELIGIBLE:
        return {'status': 'BLOCKED', 'reason': 'ADMISSION', 'http_attempts': 0}
    physical = 0

    def bounded_get(path, params=None, *, on_attempt=None):
        if path not in ALLOW_PATHS:
            raise LiveBlocked('UNAPPROVED_ENDPOINT')
        if params and params.get('symbol', event.symbol) != event.symbol:
            raise LiveBlocked('UNAPPROVED_SYMBOL')
        def attempt(actual_path):
            nonlocal physical
            if actual_path != path or physical >= min(scope.max_attempts, 8):
                raise LiveBlocked('PHYSICAL_ATTEMPT_BUDGET')
            current = clock()
            elapsed = monotonic() - start
            if (admission(event, scope, current, proof) != ELIGIBLE
                    or not 0 <= elapsed < scope.budget_seconds
                    or abs((current-now).total_seconds()-elapsed) > 1):
                raise LiveBlocked('DEADLINE_OR_CLOCK')
            physical += 1
            on_attempt(actual_path)
        before = physical
        payload, meta = getter(path, params, on_attempt=attempt)
        if physical == before:
            raise LiveBlocked('TRANSPORT_OMITTED_ATTEMPT_HOOK')
        if path == '/api/v3/time':
            seconds = 1800 if event.horizon == '30m' else 14400
            if int(payload['serverTime']) // (seconds*1000) * seconds != int(event.close.timestamp()):
                raise LiveBlocked('FROZEN_EVENT_ANCHOR_MISMATCH')
        return payload, meta

    result = probe_once(horizon=Horizon.INTRADAY if event.horizon == '30m' else Horizon.SWING,
                        symbol=event.symbol, getter=bounded_get,
                        local_ms=lambda: clock().timestamp()*1000, monotonic=monotonic)
    if admission(event, scope, clock(), proof) != ELIGIBLE or monotonic()-start >= scope.budget_seconds:
        result.update(status='BLOCKED', reason='RECEIPT_OR_DECISION_DEADLINE', research_events=[])
    result.update(stage='WINDOWS_RUNTIME_SMOKE_FIXTURE', fixture_attempts=physical,
                  signal_id=None, score_status='SCORE_UNAVAILABLE', trade_plan_status='RESEARCH_ONLY',
                  live_permission='OFF', durable_evidence='PENDING_OWNER_DECISION')
    return result
