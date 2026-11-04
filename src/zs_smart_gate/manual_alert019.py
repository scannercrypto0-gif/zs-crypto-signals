"""Manual research temporal evidence, not absolute UTC, OOS or publication proof.

No network/scheduler/sender. Profiles, epoch anchors and restored digest pins
are injected and empty by default. Raw x=true is a source claim, never a local
UTC metrology certificate. Unknown transit age cannot become known freshness.
"""
import hashlib
import json
import math
from decimal import Decimal
from .evidence_journal import canonical_bytes

VERSION = 'MANUAL_RESEARCH_ALERT_CAUSALITY_V1'
FRAMES = {'5m':300000,'30m':1800000,'4h':14400000,'1d':86400000,'1w':604800000}


def digest(value):
    return hashlib.sha256(canonical_bytes({k:v for k,v in value.items() if k!='digest'})).hexdigest()


def event(raw, *, study_id, source, symbol, frame, event_id, seq, epoch, previous,
          received_mono_ns, claim_mono_ns, wall_ms, profile_sha256,
          revision=0, supersedes=None, request_sent_mono_ns=None, wall_source='UNATTESTED_WALL_CLOCK'):
    value=dict(study_id=study_id,source=source,symbol=symbol,frame=frame,event_id=event_id,
        seq=seq,epoch=epoch,previous=previous,received_mono_ns=received_mono_ns,
        claim_mono_ns=claim_mono_ns,claim_id=f'{study_id}:{event_id}:{revision}',
        raw_hash=hashlib.sha256(raw).hexdigest(),raw_bytes=len(raw),
        wall_ms=wall_ms,wall_source=wall_source,wall_trust='UNATTESTED',
        profile_sha256=profile_sha256,revision=revision,supersedes=supersedes,
        request_sent_mono_ns=request_sent_mono_ns)
    value['digest']=digest(value)
    return value


def closed_source(raw, e, profile):
    """Supported source-finality route only: official UTC websocket kline x.

    No numeric close+Ns fallback. Lack of x=true or a complete profile is UNKNOWN.
    """
    if profile.get('kind')!='BINANCE_SPOT_UTC_KLINE_X' or profile.get('timezone')!='UTC':
        raise ValueError('FINALITY_UNKNOWN_NO_QUALIFIED_SOURCE_MARKER')
    p=json.loads(raw)
    if not isinstance(p,dict) or not isinstance(p.get('k'),dict):
        raise ValueError('FINALITY_UNKNOWN_REST_OR_NO_KLINE_MARKER')
    k=p['k'];frame=e['frame'];size=FRAMES[frame]
    if (e['event_id']!=f"{e['symbol']}:{frame}:{k.get('t')}" or
        p.get('e')!='kline' or p.get('s')!=e['symbol'] or k.get('s')!=e['symbol'] or
        k.get('i')!=frame or type(k.get('t')) is not int or type(k.get('T')) is not int or
        type(p.get('E')) is not int):raise ValueError('SOURCE_FRAME_OR_TIME_SCHEMA')
    offset=345600000 if frame=='1w' else 0
    if (k['t']-offset)%size or k['T']+1!=k['t']+size:
        raise ValueError('FRAME_BOUNDARY_MISMATCH')
    if k.get('x') is not True:raise ValueError('FINALITY_UNKNOWN_OPEN_OR_MISSING_MARKER')
    if p['E']<k['T']+1:raise ValueError('SOURCE_FINALITY_CONTRADICTS_EVENT_TIME')
    o,h,l,c,v,q=map(Decimal,(k['o'],k['h'],k['l'],k['c'],k['v'],k['q']))
    if not all(x.is_finite() for x in (o,h,l,c,v,q)) or not 0<l<=min(o,c)<=max(o,c)<=h or min(v,q)<0:
        raise ValueError('SOURCE_OHLCV_INVALID')
    return dict(frame=frame,open_ms=k['t'],close_ms=k['T']+1,source_event_ms=p['E'],
                open=o,high=h,low=l,close=c,volume=v,quote_volume=q,
                finality='SOURCE_EXPLICIT_X_TRUE_NOT_ABSOLUTE_UTC')


def evaluate(events, raw_by_hash, *, study_id, epoch, anchor, decision_mono_ns, decision_wall_ms,
             used_digests, profiles=None, admitted_profiles=frozenset(),
             admitted_epoch_anchors=frozenset(), restored_digests=frozenset(), lifecycle=(), health_records=()):
    profiles=profiles or {};reasons=[];details=[];latest={};available={};seen_claims=set()
    previous=anchor;last_mono=-1;last_wall=None
    if anchor not in admitted_epoch_anchors:reasons.append('NEW_EPOCH_ANCHOR_NOT_ADMITTED')
    if lifecycle:reasons.append('LIFECYCLE_GAP_RESTART_SLEEP_OR_JUMP_REQUIRES_NEW_EPOCH')
    if type(decision_mono_ns) is not int or decision_mono_ns<0:reasons.append('DECISION_MONOTONIC_INVALID')
    # Positive, restored lifecycle coverage, not just absence of a bad flag.
    # Future authorized ingestion must record OS/connection notifications and
    # watchdog heartbeats. These are application evidence, not UTC calibration.
    try:
        if not health_records or not events:raise ValueError('LIFECYCLE_COVERAGE_UNKNOWN')
        if (health_records[0]['mono_ns']>min(e['claim_mono_ns'] for e in events) or
            health_records[-1]['mono_ns']!=decision_mono_ns):raise ValueError('LIFECYCLE_COVERAGE_INCOMPLETE_OR_POST_DECISION')
        last_health=-1
        for h in health_records:
            if (h['digest']!=digest(h) or h['digest'] not in restored_digests or h['epoch']!=epoch or
                h['state']!='ACTIVE' or type(h['mono_ns']) is not int or h['mono_ns']<=last_health or
                (last_health>=0 and h['mono_ns']-last_health>60*10**9)):
                raise ValueError('LIFECYCLE_GAP_OR_UNVERIFIED_STATE')
            last_health=h['mono_ns']
    except (KeyError,TypeError,ValueError) as exc:reasons.append(str(exc))
    for seq,e in enumerate(events,1):
        row=dict(event_id=e.get('event_id'),frame=e.get('frame'),source_closed_confirmed='UNKNOWN',
                 received_before_decision=False,data_fresh='UNKNOWN',study_id=e.get('study_id'),
                 source=e.get('source'),raw_hash=e.get('raw_hash'),receipt_digest=e.get('digest'),
                 revision=e.get('revision'),selected_for_decision=False)
        try:
            if (type(e['seq']) is not int or e['symbol'] not in ('BTCUSDT','ETHUSDT') or
                type(e['wall_ms']) not in (int,float) or not math.isfinite(e['wall_ms']) or
                e['digest']!=digest(e) or e['previous']!=previous or e['seq']!=seq or
                e['study_id']!=study_id or e['epoch']!=epoch):raise ValueError('CHAIN_SEQUENCE_STUDY_OR_EPOCH_MISMATCH')
            mono=e['received_mono_ns'];claim=e['claim_mono_ns']
            if type(mono) is not int or type(claim) is not int or not 0<=claim<mono or mono<=last_mono:
                raise ValueError('CLAIM_OR_RECEIPT_MONOTONIC_ORDER_INVALID')
            if mono>decision_mono_ns:raise ValueError('INPUT_RECEIVED_AFTER_DECISION')
            row['received_before_decision']=True
            if e['claim_id'] in seen_claims:raise ValueError('DUPLICATE_CLAIM')
            seen_claims.add(e['claim_id'])
            if e['claim_id']!=f"{study_id}:{e['event_id']}:{e['revision']}":raise ValueError('CLAIM_IDENTITY_CHANGED')
            if last_wall is not None and abs((e['wall_ms']-last_wall)/1000-(mono-last_mono)/1e9)>=1:
                raise ValueError('WALL_JUMP_REANCHOR_REQUIRED')
            raw=raw_by_hash[e['raw_hash']]
            if len(raw)!=e['raw_bytes'] or hashlib.sha256(raw).hexdigest()!=e['raw_hash']:
                raise ValueError('RAW_HASH_OR_SIZE_CHANGED')
            if e['digest'] not in restored_digests:raise ValueError('DURABLE_READBACK_NOT_VERIFIED')
            profile=profiles.get(e['profile_sha256'],{})
            if (e['profile_sha256'] not in admitted_profiles or digest(profile)!=e['profile_sha256'] or
                profile.get('source')!=e['source']):raise ValueError('SOURCE_PROFILE_NOT_ADMITTED')
            key=(e['source'],e['symbol'],e['frame'],e['event_id'])
            prior=latest.get(key)
            if type(e['revision']) is not int or e['revision']<0:raise ValueError('REVISION_INVALID')
            if prior:
                if e['revision']!=prior['revision']+1 or e['supersedes']!=prior['digest']:
                    raise ValueError('DUPLICATE_OR_UNLINKED_CORRECTION')
                available.pop(prior['digest'],None)
            elif e['revision']!=0 or e['supersedes'] is not None:raise ValueError('CORRECTION_WITHOUT_ORIGINAL')
            local_age=(decision_mono_ns-mono)/1e9
            if e['frame']=='time_reference':
                p=json.loads(raw);sent=e['request_sent_mono_ns']
                if (profile.get('kind')!='BINANCE_SPOT_TIME_REST' or type(p.get('serverTime')) is not int or
                    type(sent) is not int or not claim<=sent<=mono or p['serverTime']<=0):
                    raise ValueError('SOURCE_REFERENCE_BRACKET_OR_SCHEMA_INVALID')
                age=(decision_mono_ns-sent)/1e9
                row.update(source_closed_confirmed='NOT_A_CANDLE',data_fresh=age<=10,
                           freshness_scope='SHORT_SAME_SOURCE_REFERENCE_NOT_ABSOLUTE_UTC',age_bound_seconds=age)
                value=dict(frame='time_reference',source_time_ms=p['serverTime'],sent=sent,received=mono)
            elif e['frame']=='liquidity':
                p=json.loads(raw)
                if profile.get('kind')!='BINANCE_SPOT_CURRENT_BOOK_REST' or p['symbol']!=e['symbol']:
                    raise ValueError('LIQUIDITY_SOURCE_UNKNOWN')
                sent=e['request_sent_mono_ns']
                if type(sent) is not int or not claim<=sent<=mono:raise ValueError('CURRENT_SNAPSHOT_REQUEST_BRACKET_MISSING')
                bid,ask=Decimal(p['bidPrice']),Decimal(p['askPrice'])
                if not bid.is_finite() or not ask.is_finite() or not 0<bid<=ask:raise ValueError('LIQUIDITY_INVALID')
                age=(decision_mono_ns-sent)/1e9
                row.update(source_closed_confirmed='NOT_A_CANDLE',data_fresh=age<=10,
                           freshness_scope='CURRENT_SNAPSHOT_REQUEST_BRACKET',age_bound_seconds=age)
                value=dict(frame='liquidity',spread_bps=str(10000*(ask-bid)/((ask+bid)/2)))
            else:
                value=closed_source(raw,e,profile);row['source_closed_confirmed']=True
                row['declared_close_ms']=value['close_ms'];row['finality_evidence']=value['finality']
                # Transit bound is source/transport-profile evidence, never UTC.
                delay=profile.get('max_delivery_delay_ms')
                if type(delay) is not int or delay<0:
                    row['freshness_reason']='SOURCE_TRANSIT_BOUND_UNKNOWN'
                else:
                    # Publication lag is in one source time scale. The bound
                    # covers transport before receipt; local age covers after it.
                    age=(value['source_event_ms']-value['close_ms']+delay)/1000+local_age
                    limit=600 if e['frame']=='5m' else FRAMES[e['frame']]/1000
                    row.update(data_fresh=age<=limit,age_bound_seconds=age,
                               freshness_scope='ADMITTED_SOURCE_DELIVERY_BOUND_PLUS_LOCAL_AGE')
            row['eligible']=row['data_fresh'] is True
            latest[key]=e;available[e['digest']]=(e,value,row)
            previous=e['digest'];last_mono=mono;last_wall=e['wall_ms']
        except (KeyError,ValueError,TypeError,ArithmeticError) as exc:
            row.update(eligible=False,reason=str(exc));reasons.append(str(exc))
        details.append(row)
    if not events:reasons.append('NO_RECEIPTS')
    if events and type(decision_mono_ns) is int:
        if abs((decision_wall_ms-events[-1]['wall_ms'])/1000-(decision_mono_ns-events[-1]['received_mono_ns'])/1e9)>=1:
            reasons.append('DECISION_WALL_JUMP_REANCHOR_REQUIRED')
    if not used_digests or len(set(used_digests))!=len(used_digests):reasons.append('EMPTY_OR_DUPLICATE_INPUT_SET')
    if any(x not in available for x in used_digests):reasons.append('FUTURE_UNKNOWN_OR_SUPERSEDED_INPUT')
    chosen=[available[x] for x in used_digests if x in available]
    for _,_,r in chosen:r['selected_for_decision']=True
    refs=sorted([(e,v,r) for e,v,r in chosen if e['frame']=='time_reference'],key=lambda t:t[1]['received'])
    if refs:
        valid_refs=len(refs)>=2 and all(r['data_fresh'] is True for _,_,r in refs)
        for (_,a,_),(_,b,_) in zip(refs,refs[1:]):
            delta=b['source_time_ms']-a['source_time_ms']
            if not (b['sent']-a['received'])/1e6-2<=delta<=(b['received']-a['sent'])/1e6+2:
                valid_refs=False
        if not valid_refs:reasons.append('SOURCE_REFERENCE_STALE_INCONSISTENT_OR_INCOMPLETE')
        else:
            re,reference,_=refs[-1]
            for e,v,r in chosen:
                if e['frame'] not in FRAMES:continue
                if e['source']!=re['source'] or (reference['sent']>=e['received_mono_ns'] and reference['source_time_ms']+2<v['source_event_ms']):
                    reasons.append('SOURCE_CLOCK_REFERENCE_CONTRADICTS_FINALITY_EVENT');continue
                # Full observed request bracket + two milliseconds for two
                # integer-millisecond timestamps. Nominal monotonic seconds;
                # same-source short-horizon evidence, NOT calibrated UTC.
                age=(reference['source_time_ms']-v['close_ms'])/1000+(decision_mono_ns-reference['sent'])/1e9+.002
                r.update(data_fresh=0<=age<=(600 if e['frame']=='5m' else FRAMES[e['frame']]/1000),
                         age_bound_seconds=age,freshness_scope='TWO_COHERENT_SAME_SOURCE_SHORT_REFERENCE_BRACKETS')
                r['eligible']=r['data_fresh'] is True
    symbols={e['symbol'] for e,_,_ in chosen}
    if len(symbols)!=1:reasons.append('SYMBOL_SET_INVALID')
    frames={f:sorted([v for e,v,row in chosen if e['frame']==f],key=lambda x:x.get('open_ms',0)) for f in (*FRAMES,'liquidity')}
    if any(not frames[f] for f in frames):reasons.append('REQUIRED_FRAME_CONTEXT_OR_LIQUIDITY_MISSING')
    current_rows=[]
    for frame in frames:
        candidates=[(e,v,r) for e,v,r in chosen if e['frame']==frame]
        for _,_,r in candidates:
            r['freshness_role']='HISTORICAL_CLOSED_INPUT';r['eligible']=True
        if candidates:
            _,_,r=max(candidates,key=lambda t:t[1].get('open_ms',t[0]['received_mono_ns']))
            r['freshness_role']='LATEST_DECISION_CONTEXT';current_rows.append(r)
            r['eligible']=r['data_fresh'] is True
            if r['data_fresh'] is not True:reasons.append('INPUT_STALE_OR_FRESHNESS_UNKNOWN')
    for parent,child,count in [('30m','5m',6),('4h','30m',8)]:
        for p in frames[parent]:
            children=[c for c in frames[child] if p['open_ms']<=c['open_ms'] and c['close_ms']<=p['close_ms']]
            if (len(children)!=count or children[0]['open_ms']!=p['open_ms'] or children[-1]['close_ms']!=p['close_ms'] or
                any(a['close_ms']!=b['open_ms'] for a,b in zip(children,children[1:])) or
                (children[0]['open'],max(x['high'] for x in children),min(x['low'] for x in children),children[-1]['close'],sum(x['volume'] for x in children),sum(x['quote_volume'] for x in children))!=
                (p['open'],p['high'],p['low'],p['close'],p['volume'],p['quote_volume'])):
                reasons.append('MISSING_DELAYED_OR_INCONSISTENT_PARENT_CHILD_CONTEXT')
    indicators=None
    if not reasons:
        bars=frames['5m'];last=bars[-1]
        pivots=[b['close_ms'] for a,b,c in zip(bars,bars[1:],bars[2:]) if b['high']>max(a['high'],c['high'])]
        indicators=dict(last_close=str(last['close']),return_from_first=str(last['close']/bars[0]['open']-1),
            close_location=str((last['close']-last['low'])/(last['high']-last['low'])) if last['high']>last['low'] else None,
            confirmed_pivot_closes_ms=pivots,unconfirmed_latest_pivot_used=False,
            spread_bps=frames['liquidity'][-1]['spread_bps'])
    return dict(version=VERSION,study_id=study_id,status='HOLD' if reasons else 'RESEARCH_CAUSAL_ORDER_PASS_CANDIDATE',
        reasons=sorted(set(reasons)),source_closed_confirmed=all(r['source_closed_confirmed'] in (True,'NOT_A_CANDLE') for r in details) if details else False,
        received_before_decision=all(r['received_before_decision'] for r in details) if details else False,
        data_fresh=('UNKNOWN' if len(current_rows)!=len(frames) or any(r['data_fresh']=='UNKNOWN' for r in current_rows)
                    else all(r['data_fresh'] is True for r in current_rows)),
        clock_quality='RELATIVE_MONOTONIC_SAME_EPOCH_ONLY_UNATTESTED_UTC',ABSOLUTE_UTC_PIT='HOLD',
        historical_publisher_pit='HOLD',publishable=False,score=None,OOS_QUALIFIED=False,
        forward='NOT_ARMED',inputs=details,indicators=indicators,application_only=True)
