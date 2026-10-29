"""Offline-injected prospective source integration. No scheduler/live entry point.

Reuse accepted 03B1 reconciliation. An approved GitHub backend and deployed
authorization mechanism remain required before wiring a real market transport.
"""
from datetime import datetime, timezone
from .binance_live import ALLOW_PATHS, LiveBlocked
from .stage03b1_live import probe_once
from .stage03a_contracts import Horizon
from .windows_prospective import admission, validate


def clock_sample(payload, metadata, os_dispersion, os_synced):
    from .windows_prospective import ClockEvidence
    t0=metadata['t0_local_ms']/1000
    t1=metadata['received_local_ms']/1000
    elapsed=metadata['latency_ms']/1000
    rtt=t1-t0
    if rtt<0 or elapsed<0 or abs(rtt-elapsed)>0.05:
        raise ValueError('LOCAL_CLOCK_MOVED')
    # Include timestamp quantization and wall/monotonic discrepancy.
    uncertainty=max(rtt,elapsed)/2+0.002+abs(rtt-elapsed)
    return ClockEvidence(datetime.fromtimestamp(t1,timezone.utc),
        payload['serverTime']/1000-(t0+t1)/2,rtt,uncertainty,os_dispersion,os_synced)


def fixture_symbol(manifest, group, symbol, *, getter, clock, proof, monotonic, budget):
    """Explicit fixture transport only; never called by installed Windows tick.

    Each physical attempt, including retries, rechecks live time and the shared
    8/24/96 budget. Receipt after deadline is discarded. No simulated record is PIT.
    """
    plan=validate(manifest)
    if symbol not in plan['symbols'] or admission(manifest,group,clock(),proof)!='ELIGIBLE':
        return {'status':'NOT_ATTEMPTED','http_attempts':0}
    started=monotonic();wall=clock();physical=0
    def bounded(path,params=None,*,on_attempt):
        nonlocal physical
        if path not in ALLOW_PATHS or (params and params.get('symbol',symbol)!=symbol):
            raise LiveBlocked('SCOPE')
        def attempt(actual):
            nonlocal physical
            current=clock();elapsed=monotonic()-started
            if actual!=path or not 0<=elapsed<60 or abs((current-wall).total_seconds()-elapsed)>0.05:
                raise LiveBlocked('DEADLINE_OR_CLOCK')
            try:budget.before_attempt(manifest,group,symbol,current,proof)
            except ValueError as exc:raise LiveBlocked(str(exc)) from exc
            physical+=1;on_attempt(actual)
        before=physical
        data,meta=getter(path,params,on_attempt=attempt)
        if physical==before:raise LiveBlocked('TRANSPORT_OMITTED_ATTEMPT_HOOK')
        if admission(manifest,group,clock(),proof)!='ELIGIBLE':raise LiveBlocked('LATE_RECEIPT')
        if path=='/api/v3/time':
            duration=1800 if group['frame']=='30m' else 14400
            if int(data['serverTime'])//(duration*1000)*duration!=int(datetime.fromisoformat(group['close']).timestamp()):
                raise LiveBlocked('FROZEN_ANCHOR_MISMATCH')
        return data,meta
    result=probe_once(horizon=Horizon.INTRADAY if group['frame']=='30m' else Horizon.SWING,
        symbol=symbol,getter=bounded,local_ms=lambda:clock().timestamp()*1000,monotonic=monotonic)
    if admission(manifest,group,clock(),proof)!='ELIGIBLE':
        result.update(status='NOT_ATTEMPTED',reason='LATE_RECEIPT',research_events=[])
    result.update(execution_kind='OFFLINE_INJECTED_FIXTURE_NOT_PIT',http_attempts=physical,
        live_permission='OFF',signal_id=None,score_status='SCORE_UNAVAILABLE',trade_plan_status='RESEARCH_ONLY')
    return result
