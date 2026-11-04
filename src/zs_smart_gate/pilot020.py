"""One-event pilot020 policy. Pure validation, no I/O or implicit activation."""
import base64
import hashlib
import json
from decimal import Decimal
from .manual_alert019 import closed_source

WS_URL='wss://data-stream.binance.vision:443/stream?streams=btcusdt@kline_5m/ethusdt@kline_5m'
SYMBOLS=('BTCUSDT','ETHUSDT')
REST_PLAN=(('/api/v3/time',{},1),('/api/v3/time',{},1),
           ('/api/v3/ticker/bookTicker',{'symbol':'BTCUSDT'},2),
           ('/api/v3/ticker/bookTicker',{'symbol':'ETHUSDT'},2),
           ('/api/v3/ticker/24hr',{'symbol':'BTCUSDT'},2),
           ('/api/v3/ticker/24hr',{'symbol':'ETHUSDT'},2))


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def sha(value):return hashlib.sha256(canonical(value)).hexdigest()


def validate_manifest(m):
    exact={'version':'BOUNDED_MANUAL_FIELD_020_V1','symbols':list(SYMBOLS),'ws_url':WS_URL,
           'rest_host':'data-api.binance.vision','ws_connections':1,'ws_seconds':720,
           'ws_messages':1200,'ws_raw_bytes':2097152,'rest_GETs':6,'rest_weight_cap':24,
           'rest_seconds_per_response':5,'rest_bytes_per_response':65536,'rest_total_bytes':262144,
           'study_bytes':3145728,'research_total_cap_bytes':10485760,'reconnect':False,
           'trading':False,'publishable':False,'owner_windows_only':True}
    for k,v in exact.items():
        if type(m.get(k)) is not type(v) or m[k]!=v:raise ValueError('MANIFEST_LIMIT_OR_SCOPE_CHANGED:'+k)
    if m.get('rest_plan')!=[{'path':p,'params':q,'weight':w} for p,q,w in REST_PLAN]:
        raise ValueError('REST_PLAN_CHANGED')
    for k in ('frozen_at','target_close','start_at','end_at','expires_at'):
        if type(m.get(k)) is not int:raise ValueError('MANIFEST_TIME_TYPE')
    if (m['target_close']%300 or m['target_close']-m['frozen_at']<600 or
        m['expires_at']!=m['frozen_at']+86400 or m['target_close']+120>m['expires_at'] or
        m['start_at']!=m['target_close']-240 or m['end_at']!=m['target_close']+120):
        raise ValueError('MANIFEST_TARGET_OR_WINDOW_INVALID')
    for k in ('code_sha','plan_sha256','host_fingerprint_sha256'):
        n=40 if k=='code_sha' else 64
        if not isinstance(m.get(k),str) or len(m[k])!=n or any(c not in '0123456789abcdef' for c in m[k]):
            raise ValueError('MISSING_PIN:'+k)
    if m.get('study_id')!='zs03-020-'+str(m['target_close']) or m.get('evidence_branch')!='evidence-stage03-020':
        raise ValueError('STUDY_OR_BRANCH_CHANGED')
    return True


def permit(m,review,*,now,code_sha,host_fingerprint,windows,ci=False):
    validate_manifest(m)
    if not windows or ci:raise ValueError('OWNER_WINDOWS_ONLY_NOT_CI')
    if code_sha!=m['code_sha'] or host_fingerprint!=m['host_fingerprint_sha256']:
        raise ValueError('CODE_OR_OWNER_HOST_CHANGED')
    expected={'decision':'020_FIELD_PREFLIGHT_PASS','review_role':'PM 1.3','code_sha':m['code_sha'],
        'manifest_sha256':sha(m),'plan_sha256':m['plan_sha256'],'study_id':m['study_id'],
        'host_fingerprint_sha256':host_fingerprint,'native_github_storage_pass':True,
        'source_rights_and_quota_pass':True,'single_event_scope_pass':True}
    if any(type(review.get(k)) is not type(v) or review[k]!=v for k,v in expected.items()):
        raise ValueError('020_FIELD_PREFLIGHT_BLOCKED_INDEPENDENT_REVIEW_MISSING_OR_MISMATCHED')
    if type(review.get('comment_id')) is not int or review['comment_id']<=0:
        raise ValueError('EXTERNAL_GITHUB_REVIEW_COMMENT_REQUIRED')
    if not m['start_at']<=now<m['target_close'] or now>m['expires_at']:
        raise ValueError('MISSED_OR_NOT_YET_START_WINDOW_NO_ROLLOVER')
    return True


class Budget:
    def __init__(self):self.ws=0;self.messages=0;self.frames=0;self.wire=0;self.gets=0;self.weight=0;self.rest_bytes=0
    def connect(self):
        if self.ws:raise ValueError('NO_RECONNECT')
        self.ws+=1
    def wire_received(self,n):
        if type(n) is not int or n<0 or self.wire+n>2097152:raise ValueError('WS_RAW_CAP')
        self.wire+=n
    def message(self):
        if self.messages>=1200:raise ValueError('WS_MESSAGE_CAP')
        self.messages+=1
    def data_frame(self):
        if self.frames>=1200:raise ValueError('WS_FRAGMENT_FRAME_CAP')
        self.frames+=1
    def request(self,entry):
        if self.gets>=6 or entry!=REST_PLAN[self.gets]:raise ValueError('REST_SCOPE_SEQUENCE_OR_COUNT')
        if self.weight+entry[2]>24:raise ValueError('REST_WEIGHT_CAP')
        self.gets+=1;self.weight+=entry[2]
    def response(self,status,body,elapsed):
        self.rest_bytes+=len(body)
        if status!=200 or elapsed>=5 or len(body)>65536 or self.rest_bytes>262144:
            raise ValueError('REST_HTTP_TIME_OR_SIZE_STOP_NO_RETRY')


def stream_payload(raw,target_close):
    p=json.loads(raw);stream=p.get('stream');data=p.get('data')
    if stream not in ('btcusdt@kline_5m','ethusdt@kline_5m') or not isinstance(data,dict):
        raise ValueError('STREAM_OR_ENVELOPE_SCOPE')
    symbol=stream.split('@')[0].upper();k=data.get('k',{})
    if data.get('s')!=symbol or k.get('s')!=symbol or k.get('i')!='5m':raise ValueError('SYMBOL_OR_FRAME_SCOPE')
    if k.get('T')!=target_close*1000-1 or k.get('t')!=(target_close-300)*1000:
        return symbol,None,'NON_TARGET_NOT_USED'
    if k.get('x') is not True:return symbol,None,'FORMING_NOT_USED'
    value=closed_source(canonical(data),{'symbol':symbol,'frame':'5m','event_id':f"{symbol}:5m:{k['t']}"},
                        {'kind':'BINANCE_SPOT_UTC_KLINE_X','timezone':'UTC'})
    return symbol,value,'TARGET_SOURCE_CLOSED'


def decision(m,records,*,decision_mono_ns,continuity_ok):
    """Limited relative field observation; missing higher contexts stay HOLD."""
    reasons=[];closed={};books={};tickers={};refs=[];per_symbol={s:{} for s in SYMBOLS}
    if not continuity_ok:reasons.append('LIFECYCLE_OR_CHAIN_GAP')
    for r in records:
        try:
            raw=base64.b64decode(r['raw_base64'],validate=True)
            if hashlib.sha256(raw).hexdigest()!=r['raw_sha256']:raise ValueError('RAW_HASH_CHANGED')
            if not r['claimed_mono_ns']<=r['sent_mono_ns']<=r['received_mono_ns']<=decision_mono_ns:
                raise ValueError('CLAIM_RECEIPT_OR_FUTURE_INPUT')
            if r['epoch']!=m['study_id']:raise ValueError('EPOCH_CHANGED')
            if r['kind']=='ws':
                symbol,value,tag=stream_payload(raw,m['target_close'])
                if value is not None:
                    if symbol in closed:raise ValueError('DUPLICATE_TARGET_FINAL_REQUIRES_REVIEW')
                    closed[symbol]=(r,value)
                    per_symbol[symbol].update(source_close_ms=value['close_ms'],source_event_ms=value['source_event_ms'],
                        final_raw_sha256=r['raw_sha256'],received_mono_ns=r['received_mono_ns'])
            else:
                data=json.loads(raw);path=r['path'];symbol=r['params'].get('symbol')
                if path=='/api/v3/time':refs.append((r,data['serverTime']))
                elif symbol not in SYMBOLS or data.get('symbol')!=symbol:raise ValueError('REST_SYMBOL_MISMATCH')
                elif path=='/api/v3/ticker/bookTicker':books[symbol]=(r,data)
                elif path=='/api/v3/ticker/24hr':tickers[symbol]=(r,data)
        except (ValueError,TypeError,KeyError,ArithmeticError):reasons.append('INVALID_RAW_SCOPE_ORDER_OR_FINALITY')
    if set(closed)!=set(SYMBOLS):reasons.append('TARGET_FINALITY_MISSING')
    if set(books)!=set(SYMBOLS) or set(tickers)!=set(SYMBOLS):reasons.append('LIQUIDITY_OR_TICKER_MISSING')
    refs.sort(key=lambda x:x[0]['received_mono_ns'])
    if len(refs)!=2:reasons.append('TWO_SOURCE_REFERENCES_MISSING')
    else:
        (a,ta),(b,tb)=refs
        if (type(ta) is not int or type(tb) is not int or
            not (b['sent_mono_ns']-a['received_mono_ns'])/1e6-2<=tb-ta<=(b['received_mono_ns']-a['sent_mono_ns'])/1e6+2 or
            any(not 0<=(decision_mono_ns-r['sent_mono_ns'])/1e9<=10 for r,t in refs)):
            reasons.append('SOURCE_REFERENCE_STALE_OR_INCONSISTENT')
        if type(tb) is int:
            for r,c in closed.values():
                age=(tb-c['close_ms'])/1000+(decision_mono_ns-b['sent_mono_ns'])/1e9+.002
                per_symbol[next(s for s,rv in closed.items() if rv[0] is r)]['source_relative_age_bound_seconds']=age
                if not 0<=age<=600 or (b['sent_mono_ns']>=r['received_mono_ns'] and tb+2<c['source_event_ms']):
                    reasons.append('SOURCE_REFERENCE_CONTRADICTS_OR_STALE_TARGET')
    for symbol,(r,p) in books.items():
        try:
            bid,ask=Decimal(p['bidPrice']),Decimal(p['askPrice'])
            if not bid.is_finite() or not ask.is_finite() or not 0<bid<=ask:raise ValueError
            if not 0<=(decision_mono_ns-r['sent_mono_ns'])/1e9<=10:raise ValueError
            per_symbol[symbol].update(liquidity_age_seconds=(decision_mono_ns-r['sent_mono_ns'])/1e9,
                observed_spread_bps=str(10000*(ask-bid)/((ask+bid)/2)))
        except (ValueError,ArithmeticError):reasons.append('LIQUIDITY_INVALID_OR_STALE')
    for symbol,(r,p) in tickers.items():
        try:
            volume=Decimal(p['quoteVolume'])
            if not volume.is_finite() or volume<0:raise ValueError
            per_symbol[symbol]['quote_volume_24h_observed']=str(volume)
        except (ValueError,KeyError,ArithmeticError):reasons.append('TICKER_SCHEMA_INVALID')
    return dict(status='HOLD',field_relative_status='HOLD' if reasons else 'FIELD_RELATIVE_CAUSALITY_CANDIDATE',
        reasons=sorted(set(reasons+['CONTEXT_INSUFFICIENT_30M_4H_1D_1W'])),
        source_closed_confirmed=set(closed)==set(SYMBOLS),
        received_before_decision=all(type(r.get('received_mono_ns')) is int and r['received_mono_ns']<=decision_mono_ns for r in records),
        data_fresh=not reasons,clock_quality='SHORT_SAME_SOURCE_RELATIVE_ONLY_NOT_ABSOLUTE_UTC',per_symbol=per_symbol,
        target_symbols=sorted(closed),ABSOLUTE_UTC_PIT='HOLD',publishable=False,score=None,OOS_QUALIFIED=False,
        forward='NOT_ARMED',historical_I6_S6='UNAVAILABLE',decision_mono_ns=decision_mono_ns)
