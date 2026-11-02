"""Order 012 research-only evidence contracts. No network, scheduler or signals.

Approvals are external review inputs, not attestations created by this module.
Hash chains detect alteration; they are neither signatures nor WORM storage.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import math
import os
import re


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


@dataclass(frozen=True)
class Approval:
    kind: str
    artifact_sha256: str
    authority: str
    independent_review_ref: str
    reviewed: bool = False


@dataclass(frozen=True)
class TimingEvidence:
    event_close: float
    publication_at: float | None
    source_available_at: float | None
    received_at: float
    decision_at: float
    clock_measured_at: float | None
    uncertainty_seconds: float | None
    source: str
    raw_sha256: str
    publication_sha256: str | None = None
    availability_sha256: str | None = None
    clock_sha256: str | None = None
    asset: str = ''
    frame: str = ''
    clock_drift_ppm: float | None = None


def assess_pit(evidence, approvals=()):
    """Check the supplied review contract; cannot independently verify an authority."""
    if not isinstance(evidence, TimingEvidence):
        return 'INVALID_EVIDENCE_TYPE'
    e = evidence
    if not e.source or not e.asset or e.frame not in ('30m', '4h') or not sha(e.raw_sha256):
        return 'SOURCE_IDENTITY_MISSING'
    values = (e.event_close, e.publication_at, e.source_available_at,
              e.received_at, e.decision_at)
    if any(v is None for v in values):
        return 'PUBLICATION_OR_AVAILABILITY_MISSING'
    if not all(finite(v) for v in values):
        return 'INVALID_TIME'
    if list(values) != sorted(values):
        return 'NONCAUSAL_TIMELINE'
    if not finite(e.clock_measured_at) or not finite(e.uncertainty_seconds):
        return 'CLOCK_BOUND_MISSING'
    if not 0 <= e.uncertainty_seconds < 1:
        return 'CLOCK_UNCERTAINTY_REJECTED'
    if not e.clock_measured_at <= e.received_at or not 0 <= e.decision_at-e.clock_measured_at <= 30:
        return 'CLOCK_SAMPLE_STALE_OR_FUTURE'
    if not finite(e.clock_drift_ppm) or e.clock_drift_ppm < 0:
        return 'CLOCK_DRIFT_BOUND_MISSING'
    if e.uncertainty_seconds+(e.decision_at-e.clock_measured_at)*e.clock_drift_ppm/1_000_000 >= 1:
        return 'CLOCK_PROJECTED_UNCERTAINTY_REJECTED'
    # A local observation/exchange server-time label is never an independent proof.
    for kind, ref in [('PUBLICATION', e.publication_sha256),
                      ('AVAILABILITY', e.availability_sha256), ('CLOCK', e.clock_sha256)]:
        if not sha(ref):
            return kind+'_PROOF_MISSING'
        matching = [a for a in approvals if isinstance(a, Approval) and a.kind == kind
                    and a.artifact_sha256 == ref and a.reviewed is True
                    and a.independent_review_ref and a.authority
                    and a.authority.upper() not in ('LOCAL', 'BINANCE', e.source.upper())]
        if not matching:
            return kind+'_INDEPENDENT_REVIEW_MISSING'
    return 'PIT_CONTRACT_CHECKED_EXTERNAL_REVIEW_REQUIRED'


def journal_records(path, max_bytes=4_000_000, require_closed=True):
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise ValueError('JOURNAL_SIZE_LIMIT')
    previous = '0'*64
    records = []
    with path.open('rb') as stream:
        for line in stream:
            if not line.endswith(b'\n'):
                raise ValueError('TRUNCATED_JOURNAL')
            item = json.loads(line)
            r = item['record']
            if (r.get('sequence') != len(records) or r.get('previous') != previous
                    or item.get('sha256') != digest(r)):
                raise ValueError('JOURNAL_INTEGRITY_ERROR')
            if records and records[-1]['kind'] == 'FOOTER':
                raise ValueError('RECORD_AFTER_FOOTER')
            previous = item['sha256']
            records.append(r)
    if not records or records[0]['kind'] != 'HEADER':
        raise ValueError('JOURNAL_HEADER_MISSING')
    if require_closed and records[-1]['kind'] != 'FOOTER':
        raise ValueError('UNCLOSED_JOURNAL')
    return records


class EvidenceJournal:
    """Exclusive creation, durable append, bounded size, no silent recovery rewrite."""
    def __init__(self, path, identity, max_bytes=4_000_000):
        if type(max_bytes) is not int or max_bytes < 1024:
            raise ValueError('INVALID_JOURNAL_LIMIT')
        self.path = Path(path)
        self.limit = max_bytes
        self.stream = self.path.open('xb')
        self.sequence, self.previous = 0, '0'*64
        self.append('HEADER', {'version': '012-EVIDENCE-1', 'identity': identity})

    def append(self, kind, payload):
        if self.stream.closed or (self.sequence and kind == 'HEADER'):
            raise ValueError('JOURNAL_STATE')
        record = dict(sequence=self.sequence, previous=self.previous, kind=kind, payload=payload)
        h = digest(record)
        raw = canonical(dict(record=record, sha256=h))+b'\n'
        if self.stream.tell()+len(raw) > self.limit:
            raise ValueError('JOURNAL_SIZE_LIMIT')
        self.stream.write(raw)
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.sequence += 1
        self.previous = h

    def close(self):
        if not self.stream.closed:
            try:
                self.append('FOOTER', {'closed': True})
            finally:
                self.stream.close()

    def __enter__(self):
        return self

    def __exit__(self, typ, value, tb):
        if typ is None:
            self.close()
        else:
            self.stream.close()  # A failed session must remain visibly unclosed.


class AttemptClaims:
    """A claim is permanent even if the process dies before recording completion."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def claim(self, manifest_sha256, event_id):
        if not sha(manifest_sha256) or not isinstance(event_id, str) or not event_id:
            raise ValueError('INVALID_CLAIM_IDENTITY')
        path = self.root/(digest([manifest_sha256, event_id])+'.claim')
        try:
            with path.open('xb') as stream:
                stream.write(canonical(dict(manifest=manifest_sha256, event=event_id,
                                            state='CLAIMED_OUTCOME_UNCERTAIN_UNTIL_RECEIPT')))
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            return False
        return True


class DepthSequence:
    """Bounded synthetic/offline sequence validator; no transport or extrapolation."""
    def __init__(self, symbol, max_age=2):
        if not symbol or not finite(max_age) or not 0 < max_age <= 2:
            raise ValueError('INVALID_DEPTH_CONFIG')
        self.symbol, self.max_age = symbol, max_age
        self.epoch, self.last, self.received, self.source_at = 0, None, None, None
        self.state = 'NEEDS_SNAPSHOT'
        self.bids, self.asks = {}, {}

    def invalidate(self, reason):
        self.state, self.last = reason, None

    @staticmethod
    def levels(rows):
        result = {}
        for p, q in rows:
            if not finite(p) or not finite(q) or p <= 0 or q < 0 or p in result:
                raise ValueError('INVALID_DEPTH_LEVEL')
            result[p] = q
        return result

    def seed(self, update, bids, asks, received):
        self.invalidate('NEEDS_SNAPSHOT')  # A rejected resync cannot retain old validity.
        if type(update) is not int or update < 1 or not finite(received):
            raise ValueError('INVALID_SEED')
        b, a = self.levels(bids), self.levels(asks)
        if not b or not a or any(q <= 0 for q in [*b.values(), *a.values()]) or max(b) >= min(a):
            raise ValueError('CROSSED_OR_EMPTY_BOOK')
        self.bids, self.asks = b, a
        self.epoch += 1
        self.last, self.received, self.source_at = update, received, None
        self.state = 'SNAPSHOT_ONLY'

    def apply(self, symbol, first, last, bids, asks, source_at, received, decision):
        try:
            if symbol != self.symbol or any(type(v) is not int or v < 1 for v in (first, last)) or first > last:
                raise ValueError('DEPTH_IDENTITY')
            if not all(finite(v) for v in (source_at, received, decision)) or not source_at <= received <= decision:
                raise ValueError('DEPTH_TIMELINE')
            if self.received is not None and received < self.received or self.source_at is not None and source_at < self.source_at:
                raise ValueError('DEPTH_TIME_REGRESSION')
            if decision-received > self.max_age:
                raise ValueError('DEPTH_STALE')
            if self.last is None:
                return 'NEEDS_SNAPSHOT'
            if last <= self.last:
                return 'DUPLICATE_IGNORED'
            if first > self.last+1:
                raise ValueError('DEPTH_SEQUENCE_GAP')
            new_b, new_a = self.bids.copy(), self.asks.copy()
            for target, changes in [(new_b, bids), (new_a, asks)]:
                for p, q in self.levels(changes).items():
                    if q == 0:
                        target.pop(p, None)
                    else:
                        target[p] = q
            if not new_b or not new_a or max(new_b) >= min(new_a):
                raise ValueError('CROSSED_OR_EMPTY_BOOK')
            self.bids, self.asks, self.last = new_b, new_a, last
            self.received, self.source_at, self.state = received, source_at, 'SYNCED'
            return self.state
        except (ValueError, TypeError):
            self.invalidate('INVALIDATED_NEEDS_SNAPSHOT')
            raise


@dataclass(frozen=True)
class ForwardConfig:
    armed: bool = False
    manifest_sha256: str = ''
    accepted_code_sha: str = ''
    owner_scope_ref: str = ''
    rights_review_ref: str = ''
    max_packets: int = 8
    events: tuple = ()  # exact (asset, frame, event_close) identities, <=8 total


def forward_scope_digest(config):
    return digest(dict(code=config.accepted_code_sha, owner=config.owner_scope_ref,
                       rights=config.rights_review_ref, max_packets=config.max_packets,
                       events=config.events, transport='OFFLINE_ONLY_ZERO_HTTP'))


def offline_forward(config, evidence, approvals, packets, claims, journal):
    """Fixture ingestion only. There is deliberately no live transport implementation."""
    result = dict(status='NOT_ARMED', HTTP_requests=0, packets=0, live_transport=False)
    if config.armed is not True:
        return result
    if (not sha(config.manifest_sha256) or not re.fullmatch('[0-9a-f]{40}', config.accepted_code_sha)
            or not config.owner_scope_ref or not config.rights_review_ref
            or type(config.max_packets) is not int or not 1 <= config.max_packets <= 8
            or not 1 <= len(config.events) <= 8
            or config.manifest_sha256 != forward_scope_digest(config)):
        return dict(result, status='FROZEN_SCOPE_MISSING')
    status = assess_pit(evidence, approvals)
    if status != 'PIT_CONTRACT_CHECKED_EXTERNAL_REVIEW_REQUIRED':
        return dict(result, status=status)
    age = evidence.decision_at-evidence.event_close
    if not 60 <= age <= 600:
        return dict(result, status='LATE_OR_EARLY_ZERO_HTTP')
    if (evidence.asset, evidence.frame, evidence.event_close) not in config.events:
        return dict(result, status='OUTSIDE_FROZEN_EVENT_SCOPE')
    event = digest([evidence.source, evidence.asset, evidence.frame, evidence.event_close])
    if not claims.claim(config.manifest_sha256, event):
        return dict(result, status='DUPLICATE_OR_UNCERTAIN_ZERO_HTTP')
    # Never reinterpret fixture success as a live market observation.
    journal.append('CLAIM', {'manifest': config.manifest_sha256, 'event': event})
    iterator = iter(packets)
    for _ in range(config.max_packets):
        try:
            packet = next(iterator)
        except StopIteration:
            break
        journal.append('SYNTHETIC_OFFLINE_PACKET', {'raw_sha256': digest(packet), 'data': packet})
        result['packets'] += 1
    journal.append('OFFLINE_RECEIPT', {'event': event, 'packets': result['packets'], 'HTTP': 0})
    return dict(result, status='OFFLINE_SMOKE_ONLY_NOT_FORWARD_EVIDENCE')
