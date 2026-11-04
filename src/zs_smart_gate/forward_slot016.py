"""Dormant bounded future-slot executor, injected I/O only; no scheduler/network.

Approval and clock pins default empty. Nothing here authorizes activation.
Unique durable slot claims prevent automatic retries after partial capture.
"""
import base64
import hashlib
import json
import time
from .evidence_journal import canonical_bytes
from .prospective_causality import utc_gate

HOST='data-api.binance.vision'
PATHS=frozenset(('/api/v3/time','/api/v3/exchangeInfo','/api/v3/ticker/24hr','/api/v3/ticker/bookTicker','/api/v3/klines'))

def capture_slot(scope,plan,*,slot_index,wall,mono,epoch,witness=None,reviewed_clock_pins=frozenset(),
                 admitted_owner_scopes=frozenset(),journal=None,transport=None):
    result=dict(status='NOT_ARMED',attempts=0,response_bytes=0,continuous_collector_started=False,slot_capture_started=False,continuous_service=False,responses=[])
    pin=hashlib.sha256(canonical_bytes(scope)).hexdigest()
    if pin not in admitted_owner_scopes or not scope.get('explicit_owner_activation'):
        result['reason']='OWNER_SCOPE_NOT_INDEPENDENTLY_ADMITTED';return result
    if (scope.get('host')!=HOST or type(slot_index)is not int or not 0<=slot_index<scope.get('slots',0)or
        scope.get('slots',0)>14 or scope.get('max_GETs_per_slot',0)>10 or scope.get('max_weight_per_slot',0)>40):
        result['reason']='INVALID_BOUNDED_SCOPE';return result
    if not scope['start_at']+slot_index*7200<=wall<=scope['start_at']+slot_index*7200+120:
        result['reason']='MISSED_OR_FUTURE_SLOT_NO_BACKFILL';return result
    if wall>scope['end_at']or hashlib.sha256(canonical_bytes(plan)).hexdigest()!=scope.get('plan_sha256'):
        result['reason']='SCOPE_EXPIRED_OR_PLAN_CHANGED';return result
    if (not plan or len(plan)>scope['max_GETs_per_slot']or sum(x['weight']for x in plan)>scope['max_weight_per_slot']or
        any(x['path']not in PATHS for x in plan)):
        result['reason']='PLAN_EXCEEDS_SCOPED_PUBLIC_ENDPOINTS';return result
    for entry in plan:
        params=entry['params']
        weight={'/api/v3/time':1,'/api/v3/exchangeInfo':20,'/api/v3/klines':2,
                '/api/v3/ticker/24hr':2,'/api/v3/ticker/bookTicker':2 if'symbol'in params else 4}[entry['path']]
        if type(entry['weight'])is not int or entry['weight']!=weight:
            result['reason']='PROVIDER_WEIGHT_MISMATCH';return result
        if any(x not in('symbols','symbol','interval','limit')for x in params):
            result['reason']='UNAPPROVED_QUERY_FIELD';return result
        if params.get('symbol')not in(None,'BTCUSDT','ETHUSDT')or params.get('interval')not in(None,'5m','1d','1w'):
            result['reason']='UNAPPROVED_SYMBOL_OR_FRAME';return result
        if 'symbols'in params and json.loads(params['symbols'])!=['BTCUSDT','ETHUSDT']:
            result['reason']='UNAPPROVED_SYMBOL_SET';return result
        if entry['path']!='/api/v3/time'and not('symbol'in params or'symbols'in params):
            result['reason']='FULL_UNIVERSE_QUERY_FORBIDDEN';return result
        if entry['path']=='/api/v3/klines':
            try:
                if not 1<=int(params['limit'])<=200 or params['interval']not in('5m','1d','1w')or'symbol'not in params:raise ValueError
            except (ValueError,KeyError):
                result['reason']='KLINE_SCOPE_LIMIT';return result
    clock=utc_gate(witness,wall=wall,mono=mono,epoch=epoch,reviewed_proof_hashes=reviewed_clock_pins)
    if clock['status']!='UTC_BOUND_VERIFIED':result['reason']='CLOCK_HOLD';return result
    if journal is None or transport is None or journal.study_id!=scope['study_id']:
        result['reason']='DURABLE_JOURNAL_AND_BOUNDED_TRANSPORT_REQUIRED';return result
    event='slot-'+str(slot_index)
    if not journal.claim_before_attempts(journal.study_id,event):
        result['reason']='SLOT_ALREADY_CLAIMED_OR_DURABILITY_UNKNOWN';return result
    result.update(scope_sha256=pin,slot_index=slot_index,plan_sha256=scope['plan_sha256'])
    start_mono=time.monotonic_ns();start_wall=time.time_ns()
    for entry in plan:
        try:
            current=utc_gate(witness,wall=wall+(time.time_ns()-start_wall)/1e9,
                 mono=mono+(time.monotonic_ns()-start_mono),epoch=epoch,reviewed_proof_hashes=reviewed_clock_pins)
            if current['status']!='UTC_BOUND_VERIFIED':raise ValueError('CLOCK_EXPIRED_DURING_SLOT')
            result['attempts']+=1
            result['slot_capture_started']=True
            response=transport(HOST,entry['path'],entry['params'],timeout=5,max_bytes=65536)
            raw=response['body'];elapsed=response['elapsed_seconds']
            if response['status']!=200 or elapsed>=5 or len(raw)>=65536:
                raise ValueError('NETWORK_TIME_SIZE_OR_HTTP_FAILURE')
            result['response_bytes']+=len(raw)
            if result['response_bytes']>262144:raise ValueError('SLOT_TOTAL_BYTES_LIMIT')
            result['responses'].append(dict(path=entry['path'],params=entry['params'],
                raw_sha256=hashlib.sha256(raw).hexdigest(),body_base64=base64.b64encode(raw).decode()))
        except Exception as exc:
            result.update(status='STOPPED_NO_AUTOMATIC_RETRY',reason=type(exc).__name__);break
    else:
        final_clock=utc_gate(witness,wall=wall+(time.time_ns()-start_wall)/1e9,
            mono=mono+(time.monotonic_ns()-start_mono),epoch=epoch,reviewed_proof_hashes=reviewed_clock_pins)
        result['status']='BOUNDED_SLOT_CAPTURED_NOT_SCIENTIFICALLY_QUALIFIED'if final_clock['status']=='UTC_BOUND_VERIFIED'else'CLOCK_EXPIRED_NO_QUALIFICATION'
    body=canonical_bytes(result)
    if not journal.append_and_readback(event,result,hashlib.sha256(body).hexdigest()):
        result.update(status='UNKNOWN_RECEIPT_FAILURE_NO_RETRY',reason='CAPTURE_MAY_HAVE_OCCURRED_CLAIM_CONSUMED')
    return result
