"""One explicit <=6 GET public-only compatibility batch. No scheduler/retries.

Each child is killed after5s, including DNS/TLS/body; CREATE_NO_WINDOW on Windows.
Only exact frozen endpoint/parameter pairs are accepted; redirects are errors.
"""
import argparse,base64,hashlib,http.client,json,os,subprocess,sys,time
from pathlib import Path
from urllib.parse import urlencode
from zs_smart_gate.evidence_journal import canonical_bytes

HOST='data-api.binance.vision'
SYMBOLS='["BTCUSDT","ETHUSDT"]'
REQUESTS=[('/api/v3/time',{},1),('/api/v3/exchangeInfo',{'symbols':SYMBOLS},20),
 ('/api/v3/ticker/24hr',{'symbols':SYMBOLS},2),('/api/v3/ticker/bookTicker',{'symbols':SYMBOLS},4),
 ('/api/v3/klines',{'symbol':'BTCUSDT','interval':'5m','limit':'100'},2),
 ('/api/v3/klines',{'symbol':'ETHUSDT','interval':'5m','limit':'100'},2)]

def one(index):
    path,params,weight=REQUESTS[index]
    url=path+('?' +urlencode(params)if params else'')
    start=time.monotonic_ns();wall=time.time_ns();connection=http.client.HTTPSConnection(HOST,timeout=4.8)
    try:
        connection.request('GET',url,headers={'Accept':'application/json','User-Agent':'SMART-GATE-016-bounded-public-research'})
        response=connection.getresponse()
        if response.status!=200:raise ValueError('HTTP_'+str(response.status))
        if response.getheader('Location'):raise ValueError('REDIRECT_FORBIDDEN')
        raw=response.read(65536)
        if len(raw)>=65536:raise ValueError('RESPONSE_64KIB_LIMIT')
        json.loads(raw)
        return dict(path=path,params=params,weight=weight,status=response.status,bytes=len(raw),
             body_base64=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest(),
             started_wall_ns=wall,received_wall_ns=time.time_ns(),received_mono_ns=time.monotonic_ns(),
             elapsed_seconds=(time.monotonic_ns()-start)/1e9,
             used_weight_1m=response.getheader('X-MBX-USED-WEIGHT-1M'))
    finally:connection.close()

def batch(output,plan_sha):
    plan=Path('research/stage03-016/public-probe-plan.json').read_bytes()
    if hashlib.sha256(plan).hexdigest()!=plan_sha:raise ValueError('FROZEN_PLAN_HASH_REQUIRED')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'one-shot-intent.json').write_bytes(canonical_bytes(dict(plan_sha256=plan_sha,requested_utc_ns=time.time_ns(),max_attempts=6)))
    report=dict(status='NOT_STARTED',http_attempts=0,responses=[],weight_attempted=0,response_bytes=0,
                retries=0,continuous_capture_events=0,source_mode='BOUNDED_COMPATIBILITY_PROBE_NOT_FORWARD')
    for i,(_,_,weight)in enumerate(REQUESTS):
        if report['http_attempts']>=8 or report['weight_attempted']+weight>32:raise ValueError('PLAN_EXCEEDS_AUTHORIZATION')
        report['http_attempts']+=1;report['weight_attempted']+=weight
        started=time.monotonic()
        try:
            kwargs={'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)}if os.name=='nt'else{}
            child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--single',str(i)],
                capture_output=True,text=True,timeout=5,**kwargs)
            if child.returncode!=0:raise ValueError('STOP_CHILD_ERROR_'+str(child.returncode))
            r=json.loads(child.stdout)
            if r['bytes']>=65536 or r['elapsed_seconds']>=5:raise ValueError('RESPONSE_TIME_OR_SIZE_LIMIT')
            report['response_bytes']+=r['bytes']
            if report['response_bytes']>262144:raise ValueError('TOTAL_SIZE_LIMIT')
            report['responses'].append(r)
            raw=base64.b64decode(r['body_base64'],validate=True)
            (output/f'response-{i:02d}.json').write_bytes(raw)
            report['status']='COMPLETED_ONE_BATCH'
        except Exception as exc:
            report.update(status='STOPPED_NO_RETRY',failure_type=type(exc).__name__,failure_code=str(exc)[:120])
            break
        finally:
            report['last_parent_elapsed_seconds']=time.monotonic()-started
            (output/'report.json').write_bytes(canonical_bytes(report))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--single',type=int,choices=range(6));p.add_argument('--output');p.add_argument('--approved-plan-sha256')
    a=p.parse_args()
    if a.single is not None:
        print(json.dumps(one(a.single)))
    elif a.output and a.approved_plan_sha256:
        r=batch(a.output,a.approved_plan_sha256);print(json.dumps({k:v for k,v in r.items()if k!='responses'}))
    else:raise SystemExit('NOT_ARMED_ZERO_NETWORK_WITHOUT_EXPLICIT_PLAN_HASH')
