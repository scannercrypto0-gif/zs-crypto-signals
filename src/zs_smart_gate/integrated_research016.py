"""016 source -> validated frames -> descriptive research -> blocked decision.

No numeric V2 score, qualification, orders, hidden local source or network.
All normalized values below are explicitly unapproved experiment features.
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import hashlib
from .core import Candle,MarketSnapshot,build_candidate,validate_candles,spread_bps,decimal
from .mtf_contracts import CandleWindow,ReconciliationTolerance,reconcile
from .research_metrics import describe
from .stage03a_contracts import Direction,V2_GROUPS,Horizon
from .prospective_causality import receipt,assess
from .evidence_journal import canonical_bytes

def at(ms):return datetime.fromtimestamp(ms/1000,tz=timezone.utc)

def parse_rows(rows,received_ms):
    candles=[];previous=None
    for r in rows:
        if len(r)!=12:raise ValueError('KLINE_SCHEMA')
        start,end=int(r[0]),int(r[6])+1
        if start%300000 or end!=start+300000:raise ValueError('KLINE_TIME_SEMANTICS')
        if end>received_ms:raise ValueError('CANDLE_NOT_FINAL')
        if previous is not None and start!=previous:raise ValueError('KLINE_GAP_OR_DUPLICATE')
        candles.append(Candle(at(start),at(end),at(received_ms),at(received_ms),
            decimal(r[1]),decimal(r[2]),decimal(r[3]),decimal(r[4]),decimal(r[5]),decimal(r[7])))
        previous=end
    if len(candles)<21:raise ValueError('INSUFFICIENT_CANDLES')
    errors=validate_candles(candles[-21:],at(received_ms))
    if errors:raise ValueError(';'.join(errors))
    return candles

def aggregate(candles,frame,decision):
    seconds={'30m':1800,'1h':3600,'4h':14400,'1d':86400,'1w':604800}[frame]
    offset=345600 if frame=='1w'else 0
    groups={}
    for c in candles:
        key=(int(c.open_at.timestamp())-offset)//seconds*seconds+offset
        groups.setdefault(key,[]).append(c)
    output=[]
    for key,group in sorted(groups.items()):
        if (len(group)!=seconds//300 or int(group[0].open_at.timestamp())!=key or
            int(group[-1].close_at.timestamp())!=key+seconds):continue
        w=CandleWindow(frame,at(key*1000),at((key+seconds)*1000),max(x.received_at for x in group),
            max(x.available_at for x in group),'BINANCE_SPOT_OBSERVATIONS',group[0].open,max(x.high for x in group),
            min(x.low for x in group),group[-1].close,sum((x.base_volume for x in group),Decimal(0)),sum((x.quote_volume for x in group),Decimal(0)))
        if not w.errors_at(decision):output.append(w)
    return output

def liquidity(snapshot,decision_seconds,max_age=10):
    if snapshot is None:return dict(status='MISSING',spread_bps=None,normalized=None,reason='NO_DECISION_TIME_LIQUIDITY')
    try:
        observed=snapshot['received_at']
        if not 0<=decision_seconds-observed<=max_age:raise ValueError('STALE_OR_FUTURE_LIQUIDITY')
        bid,ask,volume=map(decimal,(snapshot['bid'],snapshot['ask'],snapshot['quote_volume_24h']))
        spread=spread_bps(bid,ask)
        if volume<0:raise ValueError('NEGATIVE_VOLUME')
        if snapshot.get('gap',False):raise ValueError('LIQUIDITY_SOURCE_GAP')
        return dict(status='OBSERVED_UNQUALIFIED',spread_bps=str(spread),
            normalized=str(max(Decimal(0),min(Decimal(1),1-spread/20))),
            eligible=volume>=10000000 and spread<=20,reason='CONTEMPORANEOUS_RECEIPT_NOT_HISTORICAL_PUBLICATION')
    except (ValueError,KeyError,TypeError):
        return dict(status='INVALID',spread_bps=None,normalized=None,reason='INVALID_GAPPED_OR_LATE_LIQUIDITY')

def group_features(frames,horizon,direction,liq,decision):
    prefix='I'if horizon=='INTRADAY'else'S';frame='30m'if prefix=='I'else'4h'
    parents=frames[frame]
    if not parents:return {prefix+str(i):dict(value=None,reason='PARENT_CONTEXT_MISSING')for i in range(1,7)},None
    parent=parents[-1]
    child_frame='5m'if prefix=='I'else'1h'
    children=[x for x in frames[child_frame]if parent.open_at<=x.open_at and x.close_at<=parent.close_at]
    join=reconcile(parent,children,decision,tolerance=ReconciliationTolerance(Decimal(0),Decimal(0),Decimal(0),'SAME_SOURCE_EXACT_DECIMAL'))
    if join.status!='PASS':raise ValueError('PARENT_CHILD_RECONCILIATION_FAILED')
    m={x.name:x.value for x in describe(parent,children,direction=Direction.UP if direction==1 else Direction.DOWN,decision_at=decision)}
    close=m['DIRECTIONAL_PARENT_CLOSE_LOCATION'];quality=m['DIRECTION_FAVORABLE_QUOTE_VOLUME_SHARE']
    early=m['SIGNED_CHILD_NET_TO_PATH'];continuity=m['SECOND_HALF_QUOTE_VOLUME_SHARE']
    daily,weekly=frames['1d'],frames['1w']
    context=(Decimal(int(direction*(daily[-1].close-daily[-1].open)>0))+Decimal(int(direction*(weekly[-1].close-weekly[-1].open)>0)))/2 if daily and weekly else None
    if prefix=='I':values=[close,quality,(early+1)/2 if early is not None else None,continuity,context,
                            decimal(liq['normalized'])if liq['normalized']is not None else None]
    else:values=[context,close,quality,context,continuity,decimal(liq['normalized'])if liq['normalized']is not None else None]
    return {prefix+str(i):dict(value=str(v)if v is not None else None,
            reason='RESEARCH_FIXED_R_UNAPPROVED'if v is not None else 'CONTEXT_OR_LIQUIDITY_UNAVAILABLE')for i,v in enumerate(values,1)},join.status

def evaluate(raw,*,expected_sha256,decision_ms,source_mode='HISTORICAL_ARCHIVE',market=None,
             witness=None,reviewed_proof_hashes=frozenset(),decision_mono_ns=None):
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('RAW_SHA_CONFLICT')
    import json
    data=json.loads(raw);received=data['received_ms'];symbol=data['symbol']
    if source_mode=='NEW_FUTURE_OBSERVATION':
        if (data.get('provenance',{}).get('mode')!='NEW_AFTER_FREEZE_LIVE_RECEIPT' or
            decision_mono_ns is None or type(data.get('received_mono_ns'))is not int or not data.get('collector_epoch')):
            raise ValueError('FUTURE_REQUIRES_REAL_RECEIPT_MONOTONIC_PROVENANCE')
    if source_mode=='HISTORICAL_ARCHIVE'and market is not None:
        raise ValueError('CURRENT_LIQUIDITY_CANNOT_BACKFILL_HISTORY')
    if received>decision_ms:raise ValueError('SOURCE_RECEIVED_AFTER_DECISION')
    candles=parse_rows(data['rows'],received)
    decision=at(decision_ms)
    frames={f:aggregate(candles,f,decision)for f in ['30m','1h','4h','1d','1w']}
    frames['5m']=[CandleWindow.from_five_minute(c,source_id='BINANCE_SPOT_OBSERVATIONS')for c in candles]
    liq=liquidity(market,decision_ms/1000)
    rows={};joins={}
    for h in ['INTRADAY','SWING']:
        for direction in [1,-1]:
            features,join=group_features(frames,h,direction,liq,decision)
            rows[h+':'+str(direction)]=features;joins[h+':'+str(direction)]=join
    # Replay clock labels cannot be mistaken for original historical receipts.
    epoch=data.get('collector_epoch','016-replay')if source_mode=='NEW_FUTURE_OBSERVATION'else'016-replay'
    mono=data['received_mono_ns']if source_mode=='NEW_FUTURE_OBSERVATION'else 1000000000
    dmono=decision_mono_ns if source_mode=='NEW_FUTURE_OBSERVATION'else mono+(decision_ms-received)*1000000
    event=receipt(raw,source_event_id=symbol+':snapshot',seq=1,epoch=epoch,previous='0'*64,
        received_wall=received/1000,received_mono=mono,closed_at=candles[-1].close_at.timestamp())
    causal=assess([event],{expected_sha256:raw},anchor='0'*64,decision_wall=decision_ms/1000,
        decision_mono=dmono,epoch=epoch,source_mode=source_mode,
        used_digests=[event['digest']],witness=witness,reviewed_proof_hashes=reviewed_proof_hashes)
    candidate=None
    if market is not None and liq['status']=='OBSERVED_UNQUALIFIED':
        snap=MarketSnapshot(symbol,market.get('quote_asset','UNKNOWN'),market.get('spot_enabled')is True,market.get('trading_status','UNKNOWN'),
            decimal(market['quote_volume_24h']),decimal(market['bid']),decimal(market['ask']),at(int(market['received_at']*1000)))
        candidate=build_candidate(snap,candles[-21:],decision).as_dict()
        # Existing partial V1 diagnostics are never promoted to an approved score.
        candidate['score']=None;candidate['score_status']='SCORE_UNAVAILABLE'
    reasons=['NUMERIC_V2_AND_SCIENCE_NOT_APPROVED']
    if causal['status']!='PROSPECTIVE_CAUSALITY_PASS_CANDIDATE':reasons.append('PROSPECTIVE_CAUSALITY_OR_UTC_HOLD')
    if source_mode!='NEW_FUTURE_OBSERVATION':reasons.append('HISTORICAL_PUBLISHER_PIT_HOLD')
    if liq['status']!='OBSERVED_UNQUALIFIED':reasons.append('LIQUIDITY_UNAVAILABLE')
    if any(x is None for x in joins.values()):reasons.append('MULTIFRAME_CONTEXT_MISSING')
    identity=hashlib.sha256(canonical_bytes(dict(symbol=symbol,raw_sha256=expected_sha256,decision_ms=decision_ms,source_mode=source_mode))).hexdigest()
    return dict(event_id='decision-'+identity[:24],symbol=symbol,status='BLOCKED_RESEARCH_ONLY',
        raw_sha256=expected_sha256,decision_ms=decision_ms,source_mode=source_mode,frames={k:len(v)for k,v in frames.items()},
        reconciliation=joins,features=rows,liquidity=liq,causality=causal,scanner_candidate=candidate,
        score=None,score_status='SCORE_UNAVAILABLE',publishable=False,reasons=reasons,
        historical_publisher_pit='HOLD',forward_state='NOT_ARMED',new_oos_eligible=False)
