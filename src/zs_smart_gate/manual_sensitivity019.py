"""Frozen deterministic counterfactuals, synthetic only; no OOS tuning/data I/O."""
import copy
import base64
import hashlib
import json
from .evidence_journal import canonical_bytes
from .manual_alert019 import event,digest,evaluate,FRAMES

BASE=1793577600000  # Monday 2026-11-02 00:00 UTC; calendar fixture, not field data.


def pack_fixture(f):
    value=copy.deepcopy(f)
    value['raw_by_hash']={k:base64.b64encode(v).decode() for k,v in value['raw_by_hash'].items()}
    for k in ('admitted_profiles','admitted_epoch_anchors','restored_digests'):value[k]=sorted(value[k])
    return dict(origin='SYNTHETIC_TRUST_DOUBLES_ONLY_NOT_FIELD_EVIDENCE',inputs=value)


def unpack_fixture(value):
    if value.get('origin')!='SYNTHETIC_TRUST_DOUBLES_ONLY_NOT_FIELD_EVIDENCE':
        raise ValueError('NOT_A019_SYNTHETIC_FIXTURE')
    f=copy.deepcopy(value['inputs'])
    f['raw_by_hash']={k:base64.b64decode(v,validate=True) for k,v in f['raw_by_hash'].items()}
    for k in ('admitted_profiles','admitted_epoch_anchors','restored_digests'):f[k]=set(f[k])
    return f


def fixture(symbol='BTCUSDT'):
    source='BINANCE_SPOT_PROFILE_TEST_DOUBLE'
    candle_profile=dict(kind='BINANCE_SPOT_UTC_KLINE_X',timezone='UTC',source=source,
        max_delivery_delay_ms=50,origin='SYNTHETIC_TRANSPORT_BOUND_NOT_FIELD_EVIDENCE')
    quote_profile=dict(kind='BINANCE_SPOT_CURRENT_BOOK_REST',source=source,
        origin='SYNTHETIC_REQUEST_BRACKET_NOT_FIELD_EVIDENCE')
    cp,qp=digest(candle_profile),digest(quote_profile)
    profiles={cp:candle_profile,qp:quote_profile};records=[]
    for i in range(48):
        start=BASE+i*300000;o=100+(i%6);c=o+.5
        records.append(dict(t=start,T=start+300000-1,i='5m',s=symbol,x=True,
                            o=str(o),h=str(o+1),l=str(o-1),c=str(c),v='10',q='1000'))
    for frame,children,count in [('30m',list(records),6),('4h',None,8)]:
        if children is None:children=[x for x in records if x['i']=='30m']
        for i in range(0,len(children),count):
            group=children[i:i+count]
            records.append(dict(t=group[0]['t'],T=group[-1]['T'],i=frame,s=symbol,x=True,
                o=group[0]['o'],h=str(max(float(x['h']) for x in group)),l=str(min(float(x['l']) for x in group)),
                c=group[-1]['c'],v=str(sum(int(x['v']) for x in group)),q=str(sum(int(x['q']) for x in group))))
    for frame in ('1d','1w'):
        records.append(dict(t=BASE-FRAMES[frame],T=BASE-1,i=frame,s=symbol,x=True,
                            o='90',h='120',l='80',c='100',v='10000',q='1000000'))
    events=[];raws={}
    for k in sorted(records,key=lambda k:(k['T'],k['i'])):
        raw=canonical_bytes(dict(e='kline',E=k['T']+2,s=symbol,k=k))
        mono=(k['T']+1-BASE)*1000000+10000000+len(events)*1000
        e=event(raw,study_id='manual019-synthetic',source=source,symbol=symbol,frame=k['i'],
            event_id=f"{symbol}:{k['i']}:{k['t']}",seq=len(events)+1,epoch='synthetic-epoch',
            previous=events[-1]['digest'] if events else 'a'*64,received_mono_ns=mono,
            claim_mono_ns=mono-1000000,wall_ms=BASE+mono/1e6,profile_sha256=cp)
        events.append(e);raws[e['raw_hash']]=raw
    mono=14400*10**9+500000000
    raw=canonical_bytes(dict(symbol=symbol,bidPrice='100',askPrice='100.1'))
    e=event(raw,study_id='manual019-synthetic',source=source,symbol=symbol,frame='liquidity',event_id='current-book',
        seq=len(events)+1,epoch='synthetic-epoch',previous=events[-1]['digest'],received_mono_ns=mono,
        claim_mono_ns=mono-100000000,request_sent_mono_ns=mono-50000000,wall_ms=BASE+mono/1e6,profile_sha256=qp)
    events.append(e);raws[e['raw_hash']]=raw
    health=[]
    for mono in [*range(0,14401*10**9,60*10**9),14401*10**9]:
        h=dict(mono_ns=mono,epoch='synthetic-epoch',state='ACTIVE',origin='SYNTHETIC_LIFECYCLE_DOUBLE')
        h['digest']=digest(h);health.append(h)
    return dict(events=events,raw_by_hash=raws,study_id='manual019-synthetic',epoch='synthetic-epoch',anchor='a'*64,
        decision_mono_ns=14401*10**9,decision_wall_ms=BASE+14401000,
        used_digests=[x['digest'] for x in events],profiles=profiles,admitted_profiles=set(profiles),
        admitted_epoch_anchors={'a'*64},restored_digests={x['digest'] for x in events}|{h['digest'] for h in health},health_records=health)


def rechain(f):
    previous=f['anchor'];f['events'].sort(key=lambda e:e['received_mono_ns'])
    for i,e in enumerate(f['events'],1):
        e.update(seq=i,previous=previous);e['digest']=digest(e);previous=e['digest']
    f['used_digests']=[e['digest'] for e in f['events']]
    # Fixture admission only, not a durable readback implementation.
    f['restored_digests']=set(f['used_digests'])|{h['digest'] for h in f['health_records']}


def change_raw(f,e,transform):
    value=json.loads(f['raw_by_hash'][e['raw_hash']]);transform(value)
    raw=canonical_bytes(value);e['raw_hash']=hashlib.sha256(raw).hexdigest();e['raw_bytes']=len(raw)
    f['raw_by_hash'][e['raw_hash']]=raw


def source_references(f):
    # Alternative finite protocol route, NOT new live requests. The same-source
    # time scale and observed request brackets replace a guessed WS transit SLA.
    for e in f['events']:
        if e['frame']=='liquidity':continue
        p=copy.deepcopy(f['profiles'][e['profile_sha256']]);p.pop('max_delivery_delay_ms',None)
        sha=digest(p);f['profiles'][sha]=p;f['admitted_profiles'].add(sha);e['profile_sha256']=sha
    source=f['events'][0]['source'];symbol=f['events'][0]['symbol']
    p=dict(kind='BINANCE_SPOT_TIME_REST',source=source,origin='SYNTHETIC_SAME_SOURCE_REFERENCE_NOT_UTC')
    sha=digest(p);f['profiles'][sha]=p;f['admitted_profiles'].add(sha)
    for i,(sent_ms,received_ms,t) in enumerate([(700,800,750),(850,900,875)]):
        raw=canonical_bytes(dict(serverTime=BASE+14400000+t))
        sent=14400*10**9+sent_ms*10**6;mono=14400*10**9+received_ms*10**6
        e=event(raw,study_id=f['study_id'],source=source,symbol=symbol,frame='time_reference',
            event_id=f'source-clock-reference-{i}',seq=0,epoch=f['epoch'],previous='pending',
            received_mono_ns=mono,claim_mono_ns=sent-1000000,request_sent_mono_ns=sent,
            wall_ms=BASE+mono/1e6,profile_sha256=sha)
        f['events'].append(e);f['raw_by_hash'][e['raw_hash']]=raw
    rechain(f)
    return f


def scenarios():
    cases={'ideal_wall':fixture()}
    for offset in (-5,-3,-1.5,1.5,3,5):
        f=fixture();f['decision_wall_ms']+=offset*1000
        for e in f['events']:e['wall_ms']+=offset*1000
        rechain(f);cases[f'constant_wall_offset_{offset:+g}s']=f
    for kind in ('open_candle','missing_finality','arrival_before_source_close','rest_no_finality',
                 'late_30m','late_4h','late_daily','late_weekly','future_by_one_nanosecond','stale_liquidity','stale_5m',
                 'stale_30m','stale_4h','stale_daily','stale_weekly','missing_daily','missing_weekly','unknown_delivery_bound','wall_jump','disconnect',
                 'restart','sleep','duplicate','unlinked_correction','linked_correction','raw_tamper',
                 'unconfirmed_latest_pivot','missing_child','missing_readback','unadmitted_profile'):
        f=fixture();events=f['events'];last5=next(e for e in reversed(events) if e['frame']=='5m')
        if kind in ('open_candle','missing_finality','arrival_before_source_close','rest_no_finality'):
            def mutate(p):
                if kind=='open_candle':p['k']['x']=False
                elif kind=='missing_finality':p['k'].pop('x')
                elif kind=='arrival_before_source_close':p['E']=p['k']['T']-1
                else:p.clear();p.update(rest_klines_have_no_final_flag=True)
            change_raw(f,last5,mutate)
        elif kind in ('late_30m','late_4h','late_daily','late_weekly','future_by_one_nanosecond'):
            frame={'late_30m':'30m','late_4h':'4h','late_daily':'1d','late_weekly':'1w','future_by_one_nanosecond':'liquidity'}[kind]
            e=next(e for e in reversed(events) if e['frame']==frame)
            e['received_mono_ns']=f['decision_mono_ns']+1;e['wall_ms']=BASE+e['received_mono_ns']/1e6
        elif kind=='stale_liquidity':
            events[-1]['request_sent_mono_ns']-=11*10**9;events[-1]['claim_mono_ns']-=12*10**9
        elif kind=='stale_5m':
            f['decision_mono_ns']+=601*10**9;f['decision_wall_ms']+=601000
            for m in range(f['health_records'][-1]['mono_ns']+60*10**9,f['decision_mono_ns'],60*10**9):
                h=dict(mono_ns=m,epoch='synthetic-epoch',state='ACTIVE',origin='SYNTHETIC_LIFECYCLE_DOUBLE');h['digest']=digest(h);f['health_records'].append(h)
            h=dict(mono_ns=f['decision_mono_ns'],epoch='synthetic-epoch',state='ACTIVE',origin='SYNTHETIC_LIFECYCLE_DOUBLE');h['digest']=digest(h);f['health_records'].append(h)
            e=events[-1]
            for key in ('received_mono_ns','request_sent_mono_ns','claim_mono_ns'):e[key]+=601*10**9
            e['wall_ms']+=601000
        elif kind in ('stale_30m','stale_4h','stale_daily','stale_weekly','unknown_delivery_bound'):
            frame={'stale_30m':'30m','stale_4h':'4h','stale_daily':'1d','stale_weekly':'1w','unknown_delivery_bound':'5m'}[kind]
            for e in events:
                if e['frame']!=frame:continue
                p=copy.deepcopy(f['profiles'][e['profile_sha256']])
                if kind=='unknown_delivery_bound':p.pop('max_delivery_delay_ms')
                else:p['max_delivery_delay_ms']=FRAMES[frame]+1
                sha=digest(p);f['profiles'][sha]=p;f['admitted_profiles'].add(sha);e['profile_sha256']=sha
        elif kind=='wall_jump':events[-1]['wall_ms']+=3000
        elif kind in ('disconnect','restart','sleep'):f['lifecycle']=[kind]
        elif kind in ('duplicate','unlinked_correction','linked_correction'):
            original=events[-1];e=copy.deepcopy(original);e['received_mono_ns']+=1000000;e['wall_ms']+=1
            if kind!='duplicate':
                e['revision']=1;e['claim_id']=f"{e['study_id']}:{e['event_id']}:1";e['claim_mono_ns']=original['received_mono_ns']+1
                e['request_sent_mono_ns']=e['claim_mono_ns']+1
                e['supersedes']=original['digest'] if kind=='linked_correction' else 'f'*64
                change_raw(f,e,lambda p:p.update(correction='APPEND_ONLY_SYNTHETIC'))
            events.append(e)
        elif kind=='raw_tamper':f['raw_by_hash'][last5['raw_hash']]=b'changed without correction'
        elif kind=='unconfirmed_latest_pivot':
            change_raw(f,last5,lambda p:p['k'].update(h='120'))
            for e in events:
                if e['frame'] in ('30m','4h') and json.loads(f['raw_by_hash'][e['raw_hash']])['k']['T']==BASE+14400000-1:
                    change_raw(f,e,lambda p:p['k'].update(h='120'))
        elif kind=='missing_child':events.remove(last5)
        elif kind in ('missing_daily','missing_weekly'):
            frame='1d' if kind=='missing_daily' else '1w'
            f['events'][:]=[e for e in events if e['frame']!=frame]
        rechain(f)
        if kind=='linked_correction':f['used_digests'].remove(events[-2]['digest'])
        if kind=='missing_readback':f['restored_digests']=set()
        if kind=='unadmitted_profile':f['admitted_profiles']=set()
        cases[kind]=f
    for kind in ('source_reference_no_utc','source_reference_clock_step','source_reference_stale',
                 'source_reference_future','source_reference_incomplete'):
        f=source_references(fixture())
        refs=[e for e in f['events'] if e['frame']=='time_reference']
        if kind=='source_reference_clock_step':change_raw(f,refs[-1],lambda p:p.update(serverTime=p['serverTime']+3000))
        elif kind=='source_reference_stale':
            for e in refs:
                for key in ('received_mono_ns','claim_mono_ns','request_sent_mono_ns'):e[key]-=11*10**9
                e['wall_ms']-=11000;change_raw(f,e,lambda p:p.update(serverTime=p['serverTime']-11000))
        elif kind=='source_reference_future':
            refs[-1]['received_mono_ns']=f['decision_mono_ns']+1;refs[-1]['wall_ms']=BASE+refs[-1]['received_mono_ns']/1e6
        elif kind=='source_reference_incomplete':f['events'].remove(refs[0])
        rechain(f);cases[kind]=f
    return cases


def comparison():
    cases=scenarios();results={name:evaluate(**f) for name,f in cases.items()};base=results['ideal_wall']
    rows=[]
    for name,r in results.items():
        rows.append(dict(case=name,status=r['status'],reasons=r['reasons'],
            input_eligibility_changed=(r['source_closed_confirmed'],r['received_before_decision'],r['data_fresh'])!=
                                      (base['source_closed_confirmed'],base['received_before_decision'],base['data_fresh']),
            decision_state_changed=r['status']!=base['status'],
            indicator_availability_changed=(r['indicators'] is None)!=(base['indicators'] is None),
            indicators_changed_when_defined=None if r['indicators'] is None else r['indicators']!=base['indicators'],
            indicators=r['indicators'],ABSOLUTE_UTC_PIT=r['ABSOLUTE_UTC_PIT'],publishable=r['publishable']))
    return dict(version='MANUAL019_SYNTHETIC_SENSITIVITY_01',synthetic_only=True,old_OOS_used=False,
        new_market_requests=0,new_clock_requests=0,margin_policy='SOURCE_X_TRUE_AND_SOURCE_EVENT_AT_OR_AFTER_CLOSE_NO_FIXED_5S',
        unknown_finality_policy='HOLD_NO_INDICATORS',cases=rows)
