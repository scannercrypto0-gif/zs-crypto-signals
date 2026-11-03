"""PROSPECTIVE_RECEIPT_CAUSALITY_V1; no historical publication promotion.

Trusted UTC proofs are injected pins admitted by an independent reviewer. An
authenticated NTS exchange alone, synthetic fixture or caller assertion cannot
populate this registry. Hash chaining is application integrity, never WORM.
"""
from __future__ import annotations
import hashlib
import math
from .evidence_journal import canonical_bytes

VERSION='PROSPECTIVE_RECEIPT_CAUSALITY_V1'

def finite(x):
    return type(x)in(int,float)and math.isfinite(x)

def digest(event):
    return hashlib.sha256(canonical_bytes({k:v for k,v in event.items()if k!='digest'})).hexdigest()

def receipt(raw,*,source_event_id,seq,epoch,previous,received_wall,received_mono,
            closed_at,revision=0,supersedes=None,kind='DATA'):
    if not isinstance(raw,bytes)or not raw:raise ValueError('RAW_BYTES_REQUIRED')
    event=dict(source_event_id=source_event_id,seq=seq,epoch=epoch,previous=previous,
         collector_received_at=received_wall,collector_received_mono_ns=received_mono,
         closed_at=closed_at,revision=revision,supersedes=supersedes,kind=kind,
         raw_sha256=hashlib.sha256(raw).hexdigest(),raw_bytes=len(raw))
    event['digest']=digest(event)
    return event

def utc_gate(witness,*,wall,mono,epoch,reviewed_proof_hashes=frozenset()):
    """Traceable bound <1s at decision; return no implicit trust or local fallback."""
    if not witness:return dict(status='HOLD',reason='INDEPENDENT_UTC_ATTESTATION_MISSING',bound_seconds=None)
    w=witness
    if (w.get('origin')!='EXTERNAL_INDEPENDENT_ATTESTATION' or
        w.get('proof_sha256')not in reviewed_proof_hashes or w.get('synthetic')is not False):
        return dict(status='HOLD',reason='AUTHENTICATION_IS_NOT_ABSOLUTE_UTC_PROOF',bound_seconds=None)
    proof_body={k:v for k,v in w.items()if k!='proof_sha256'}
    try:
        proof_hash=hashlib.sha256(canonical_bytes(proof_body)).hexdigest()
    except (ValueError,TypeError):
        return dict(status='FAIL',reason='INVALID_ATTESTATION_DOCUMENT',bound_seconds=None)
    if proof_hash!=w['proof_sha256']:
        return dict(status='FAIL',reason='ADMITTED_UTC_DOCUMENT_CHANGED',bound_seconds=None)
    names=['reference_wall','reference_mono_ns','valid_until_mono_ns','absolute_error_seconds','max_drift_ppm']
    if any(not finite(w.get(k))for k in names)or not finite(wall)or not finite(mono):
        return dict(status='FAIL',reason='CLOCK_FIELDS_NONFINITE',bound_seconds=None)
    if w.get('epoch')!=epoch or not w['reference_mono_ns']<=mono<=w['valid_until_mono_ns']:
        return dict(status='HOLD',reason='CLOCK_EPOCH_OR_CALIBRATION_EXPIRED',bound_seconds=None)
    if w['absolute_error_seconds']<0 or w['max_drift_ppm']<0:
        return dict(status='FAIL',reason='NEGATIVE_CLOCK_BOUND',bound_seconds=None)
    age=(mono-w['reference_mono_ns'])/1e9
    residual=abs((wall-w['reference_wall'])-age)
    bound=w['absolute_error_seconds']+age*w['max_drift_ppm']/1e6+residual
    return dict(status='UTC_BOUND_VERIFIED'if bound<1 else 'HOLD',
        reason='INDEPENDENT_PIN_AND_BOUND_CHECKED'if bound<1 else 'CLOCK_BOUND_AT_LEAST_ONE_SECOND',bound_seconds=bound)

def assess(events,raw_by_hash,*,anchor,decision_wall,decision_mono,epoch,
           source_mode,used_digests,witness=None,reviewed_proof_hashes=frozenset()):
    reasons=[];previous=anchor;last_mono=-1;last_wall=-math.inf;seen={};available=set()
    if not events:reasons.append('NO_RECEIPTS')
    for seq,e in enumerate(events,1):
        try:
            mono,wall=e['collector_received_mono_ns'],e['collector_received_at']
            if type(e['seq'])is not int or not isinstance(e['source_event_id'],str)or not e['source_event_id'].strip():
                raise ValueError('INVALID_SOURCE_ID_OR_SEQUENCE_TYPE')
            if not all(finite(x)for x in (mono,wall,decision_mono,decision_wall,e['closed_at'])):
                raise ValueError('NONFINITE_EVENT_CLOCK')
            if e['seq']!=seq or e['previous']!=previous or e['digest']!=digest(e):
                raise ValueError('CHAIN_GAP_OR_TAMPER')
            if e['epoch']!=epoch:raise ValueError('RECONNECT_REQUIRES_NEW_ANCHORED_EPOCH')
            if mono<=last_mono or wall<last_wall:raise ValueError('CLOCK_JUMP_OR_SEQUENCE_REPLAY')
            if last_mono>=0 and abs((wall-last_wall)-(mono-last_mono)/1e9)>=1:
                raise ValueError('WALL_MONOTONIC_DIVERGENCE')
            if mono>decision_mono or wall>decision_wall:raise ValueError('INPUT_RECEIVED_AFTER_DECISION')
            if e['closed_at']>wall:raise ValueError('CANDLE_NOT_FINAL_AT_RECEIPT')
            raw=raw_by_hash.get(e['raw_sha256'])
            if raw is None or len(raw)!=e['raw_bytes']or hashlib.sha256(raw).hexdigest()!=e['raw_sha256']:
                raise ValueError('RAW_HASH_OR_SIZE_CONFLICT')
            identity=e['source_event_id'];revision=e['revision']
            if type(revision)is not int or revision<0:raise ValueError('INVALID_REVISION')
            prior=seen.get(identity)
            if prior is None and (revision!=0 or e['supersedes']is not None):
                raise ValueError('REVISION_WITHOUT_ORIGINAL')
            if prior is not None:
                if revision!=prior['revision']+1 or e['supersedes']!=prior['digest']:
                    raise ValueError('DUPLICATE_OR_UNLINKED_CORRECTION')
                available.discard(prior['digest'])
            if e['kind']!='DATA':raise ValueError('SOURCE_GAP_OR_RECOVERY_BARRIER')
            seen[identity]=e;available.add(e['digest'])
            previous=e['digest'];last_mono=mono;last_wall=wall
        except (KeyError,TypeError,ValueError)as exc:
            reasons.append(str(exc));break
    if not set(used_digests).issubset(available):reasons.append('UNKNOWN_FUTURE_OR_SUPERSEDED_INPUT_USED')
    if len(used_digests)!=len(set(used_digests)):reasons.append('DUPLICATED_DECISION_INPUT')
    if not used_digests:reasons.append('NO_CAUSAL_DECISION_INPUT')
    if not finite(decision_mono)or not finite(decision_wall):reasons.append('INVALID_DECISION_CLOCK')
    elif last_mono>=0 and (decision_mono<last_mono or decision_wall<last_wall or
          abs((decision_wall-last_wall)-(decision_mono-last_mono)/1e9)>=1):
        reasons.append('DECISION_CLOCK_JUMP')
    future=source_mode=='NEW_FUTURE_OBSERVATION'
    received=('RECEIVED_BEFORE_DECISION'if future else 'REPLAY_ORDER_ONLY_NOT_FIELD_RECEIPT')if not reasons else 'FAIL'
    clock=utc_gate(witness,wall=decision_wall,mono=decision_mono,epoch=epoch,
                   reviewed_proof_hashes=reviewed_proof_hashes)
    if clock['status']=='UTC_BOUND_VERIFIED'and not reasons:
        for e in events:
            at_receipt=utc_gate(witness,wall=e['collector_received_at'],mono=e['collector_received_mono_ns'],
                epoch=epoch,reviewed_proof_hashes=reviewed_proof_hashes)
            if at_receipt['status']!='UTC_BOUND_VERIFIED':
                clock=dict(status='HOLD',reason='RECEIPT_OUTSIDE_ATTESTED_CALIBRATION',bound_seconds=None);break
            if e['closed_at']+at_receipt['bound_seconds']>e['collector_received_at']:
                reasons.append('CANDLE_FINALITY_INSIDE_CLOCK_UNCERTAINTY');break
    status=('PROSPECTIVE_CAUSALITY_PASS_CANDIDATE'if not reasons and future and clock['status']=='UTC_BOUND_VERIFIED'
            else 'FAIL'if reasons else 'HOLD')
    if not future:reasons.append('ARCHIVE_OR_SYNTHETIC_NOT_NEW_FUTURE_DATA')
    return dict(version=VERSION,status=status,receipt_evidence=received,utc_evidence=clock,
        publisher_original_publication='MISSING',historical_publisher_pit='HOLD',reasons=reasons,
        decision_input_digests=list(used_digests),last_chain_digest=previous,application_only=True)

def forward_gate(*,owner_scope=None,causality=None,durable_storage=False,recovery_gap=False,
                 network_available=True,protocol_pinned=False):
    reasons=[]
    if not owner_scope:reasons.append('OWNER_BOUNDED_CAPTURE_SCOPE_NOT_APPROVED')
    if not causality or causality.get('status')!='PROSPECTIVE_CAUSALITY_PASS_CANDIDATE':reasons.append('CAUSALITY_OR_UTC_HOLD')
    if not durable_storage:reasons.append('DURABLE_CLAIM_RECEIPT_NOT_READY')
    if recovery_gap:reasons.append('RECOVERY_GAP_REQUIRES_RECALIBRATION_AND_NEW_ANCHOR')
    if not network_available:reasons.append('NETWORK_UNAVAILABLE')
    if not protocol_pinned:reasons.append('FROZEN_PROTOCOL_REQUIRED')
    return dict(status='NOT_ARMED'if reasons else 'READY_FOR_SEPARATE_OWNER_ACTIVATION',
                reasons=reasons,live_capture_events=0,collector_started=False)
