"""Order018: prospective-only V2. V1 and all frozen studies remain unchanged.

The new 1.5s ceiling is not a transport/notification latency allowance or trust
grant. Admission still requires independent source/counter/drift evidence.
"""
import hashlib
import math
from decimal import Decimal, localcontext
from .evidence_journal import canonical_bytes
from .prospective_causality import finite, receipt, digest

VERSION = 'PROSPECTIVE_RECEIPT_CAUSALITY_V2'
CLOCK_UNCERTAINTY_LIMIT_SECONDS = 1.5


def utc_gate(witness, *, wall, mono, epoch, reviewed_proof_hashes=frozenset()):
    def result(status, reason, bound=None):
        return dict(status=status, reason=reason, bound_seconds=bound,
                    clock_uncertainty_bound_seconds=bound, version=VERSION,
                    acceptance_limit_seconds=CLOCK_UNCERTAINTY_LIMIT_SECONDS)
    if not isinstance(witness, dict) or not witness:
        return result('HOLD', 'INDEPENDENT_UTC_ATTESTATION_MISSING')
    w = witness
    if (w.get('origin') != 'EXTERNAL_INDEPENDENT_ATTESTATION' or
            w.get('proof_sha256') not in reviewed_proof_hashes or w.get('synthetic') is not False):
        return result('HOLD', 'INDEPENDENT_PROOF_NOT_ADMITTED')
    try:
        actual = hashlib.sha256(canonical_bytes({k: v for k, v in w.items() if k != 'proof_sha256'})).hexdigest()
    except (ValueError, TypeError):
        return result('FAIL', 'INVALID_ATTESTATION_DOCUMENT')
    if actual != w['proof_sha256']:
        return result('FAIL', 'ADMITTED_UTC_DOCUMENT_CHANGED')
    def sha(value):
        return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)
    if (w.get('causality_version') != VERSION or w.get('counter_calibrated') is not True or
            w.get('maximum_future_drift_proved') is not True or
            not sha(w.get('counter_calibration_proof_sha256')) or not sha(w.get('drift_proof_sha256')) or
            not finite(w.get('max_drift_ppm'))):
        return result('HOLD', 'COUNTER_CALIBRATION_OR_MAXIMUM_DRIFT_UNPROVED')
    names = ('reference_wall', 'reference_mono_ns', 'valid_until_mono_ns', 'absolute_error_seconds')
    if any(not finite(w.get(k)) for k in names) or not finite(wall) or not finite(mono):
        return result('FAIL', 'CLOCK_FIELDS_NONFINITE')
    if w.get('epoch') != epoch or not w['reference_mono_ns'] <= mono <= w['valid_until_mono_ns']:
        return result('HOLD', 'CLOCK_EPOCH_OR_CALIBRATION_EXPIRED')
    if w['absolute_error_seconds'] < 0 or w['max_drift_ppm'] < 0:
        return result('FAIL', 'NEGATIVE_CLOCK_BOUND')
    budget = w.get('error_budget_seconds', {})
    components = ('source', 'transfer_and_timestamping', 'local_counter_calibration')
    if not isinstance(budget, dict) or any(not finite(budget.get(k)) or budget[k] < 0 for k in components):
        return result('HOLD', 'ABSOLUTE_ERROR_BUDGET_NOT_QUALIFIED')
    with localcontext() as context:
        context.prec = 50
        d = lambda x: Decimal(str(x))
        if sum(d(budget[k]) for k in components) > d(w['absolute_error_seconds']):
            return result('FAIL', 'ABSOLUTE_ERROR_UNDERSTATES_COMPONENT_BUDGET')
        age = (d(mono)-d(w['reference_mono_ns']))/Decimal(10**9)
        residual = abs(d(wall)-d(w['reference_wall'])-age)
        bound = d(w['absolute_error_seconds'])+age*d(w['max_drift_ppm'])/Decimal(10**6)+residual
        if bound >= Decimal('1.5'):
            return result('HOLD', 'CLOCK_BOUND_AT_LEAST_1P5_SECONDS', float(bound))
        return result('UTC_BOUND_VERIFIED', 'INDEPENDENT_PIN_AND_TOTAL_BOUND_CHECKED', float(bound))


def timing_diagnostics(*, received_mono_ns, decision_mono_ns, alert_sent_mono_ns=None):
    """Diagnostic latencies only: never used as the UTC acceptance threshold."""
    if not finite(received_mono_ns) or not finite(decision_mono_ns) or decision_mono_ns < received_mono_ns:
        raise ValueError('RECEIPT_AFTER_DECISION')
    if alert_sent_mono_ns is not None and (not finite(alert_sent_mono_ns) or alert_sent_mono_ns < decision_mono_ns):
        raise ValueError('ALERT_BEFORE_DECISION')
    return dict(receipt_to_decision_seconds=(decision_mono_ns-received_mono_ns)/1e9,
                decision_to_alert_seconds=None if alert_sent_mono_ns is None else (alert_sent_mono_ns-decision_mono_ns)/1e9,
                source_to_receipt_delay_seconds=None,
                source_delay_reason='ORIGINAL_PUBLISHER_TIME_NOT_PROVED',
                latency_is_not_clock_uncertainty=True)


# Structural anti-leak guards forked unchanged from frozen V1; UTC gate is V2.
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
            else 'FAIL'if reasons or clock['status']=='FAIL' else 'HOLD')
    if not future:reasons.append('ARCHIVE_OR_SYNTHETIC_NOT_NEW_FUTURE_DATA')
    return dict(version=VERSION,status=status,receipt_evidence=received,utc_evidence=clock,
        publisher_original_publication='MISSING',historical_publisher_pit='HOLD',reasons=reasons,
        decision_input_digests=list(used_digests),last_chain_digest=previous,application_only=True)

def forward_gate(*,owner_scope=None,causality=None,durable_storage=False,recovery_gap=False,
                 network_available=True,protocol_pinned=False):
    reasons=[]
    if not owner_scope or owner_scope.get('causality_version')!=VERSION:reasons.append('OWNER_BOUNDED_CAPTURE_SCOPE_NOT_APPROVED')
    if not causality or causality.get('version')!=VERSION or causality.get('status')!='PROSPECTIVE_CAUSALITY_PASS_CANDIDATE':reasons.append('CAUSALITY_OR_UTC_HOLD')
    if not durable_storage:reasons.append('DURABLE_CLAIM_RECEIPT_NOT_READY')
    if recovery_gap:reasons.append('RECOVERY_GAP_REQUIRES_RECALIBRATION_AND_NEW_ANCHOR')
    if not network_available:reasons.append('NETWORK_UNAVAILABLE')
    if not protocol_pinned:reasons.append('FROZEN_PROTOCOL_REQUIRED')
    return dict(status='NOT_ARMED'if reasons else 'READY_FOR_SEPARATE_OWNER_ACTIVATION',
                reasons=reasons,live_capture_events=0,collector_started=False)
