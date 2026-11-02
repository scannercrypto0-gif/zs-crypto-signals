"""Preregistered 010-PILOT-2A retrospective research. No network or trading.

Independent archive reconciliation is price/volume integrity, never proof of
historical publication, bid/ask, executable returns or prospective PIT.
"""
from bisect import bisect_right
from collections import defaultdict, Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import random
from statistics import median
import zipfile
from .stage03_science_pilot import ECDF, child_features, relative_volume, fixed_outcome, first_hit

VERSION='010-PILOT-2A'
DURATIONS={'5m':300,'30m':1800,'1h':3600,'4h':14400}
DOMAIN={'I1','I4','I5','S1','S2','S4'}

@dataclass(frozen=True)
class Bar:
    start: int
    end: int
    o: Decimal
    h: Decimal
    l: Decimal
    c: Decimal
    base: Decimal
    quote: Decimal
    def vector(self):return tuple(float(x) for x in (self.o,self.h,self.l,self.c,self.base,self.quote))

def aggregate(bars, duration):
    if not bars or len(bars)* (bars[0].end-bars[0].start)!=duration:return None
    if any(a.end!=b.start for a,b in zip(bars,bars[1:])):return None
    return Bar(bars[0].start,bars[-1].end,bars[0].o,max(x.h for x in bars),
               min(x.l for x in bars),bars[-1].c,sum(x.base for x in bars),sum(x.quote for x in bars))

def aligned_context(bars,duration,offset=0):
    groups=defaultdict(list)
    for b in bars:groups[(b.start-offset)//duration*duration+offset].append(b)
    result=[]
    for start,items in sorted(groups.items()):
        b=aggregate(items,duration)
        if b is not None and b.start==start and b.end==start+duration:result.append(b)
    return result

class Series:
    def __init__(self,bars):
        self.bars=bars;self.ends=[b.end for b in bars];self.starts={b.start:i for i,b in enumerate(bars)}
    def past(self,close,count=1):
        i=bisect_right(self.ends,close)
        return self.bars[max(0,i-count):i] if i>=count else []

def load_archives(root,manifest):
    result=defaultdict(lambda:defaultdict(list))
    for item in manifest['files']:
        path=Path(root)/item['name'];raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('DATA_CHANGED')
        frame=item['interval'];duration=DURATIONS[frame]
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members=z.infolist()
            if len(members)!=1 or members[0].filename!=item['name'][:-4]+'.csv':raise ValueError('ZIP_SCHEMA')
            if members[0].file_size>32*1024*1024:raise ValueError('UNCOMPRESSED_CAP')
            rows=list(csv.reader(io.TextIOWrapper(z.open(members[0]),encoding='utf-8')))
        for r in rows:
            if len(r)!=12 or int(r[0])%1000000 or (int(r[6])+1)%1000000:raise ValueError('MICROSECOND_SCHEMA')
            start=int(r[0])//1000000;end=(int(r[6])+1)//1000000
            values=[Decimal(r[k]) for k in (1,2,3,4,5,7)]
            if end-start!=duration or any(not x.is_finite() for x in values):raise ValueError('BAR_SCHEMA')
            o,h,l,c,base,quote=values
            if not 0<l<=min(o,c)<=max(o,c)<=h or min(base,quote)<0:raise ValueError('OHLCV')
            result[item['symbol']][frame].append(Bar(start,end,*values))
    for frames in result.values():
        for frame,bars in frames.items():
            bars.sort(key=lambda b:b.start)
            if any(a.end!=b.start for a,b in zip(bars,bars[1:])):raise ValueError('GAP_DUPLICATE')
    return result

def close_location(b,direction):
    if b is None or b.h==b.l:return None
    return float((b.c-b.l)/(b.h-b.l) if direction==1 else (b.h-b.c)/(b.h-b.l))

def strong_close(b,direction):
    loc=close_location(b,direction)
    if loc is None:return None
    body=float(direction*(b.c-b.o)/(b.h-b.l))
    wick=float((b.h-max(b.o,b.c))/(b.h-b.l) if direction==1 else (min(b.o,b.c)-b.l)/(b.h-b.l))
    return (loc+(body+1)/2+1-wick)/3

def channel(bars,direction):
    if len(bars)!=20:return None
    hi=max(x.h for x in bars);lo=min(x.l for x in bars)
    if hi==lo:return None
    return float((bars[-1].c-lo)/(hi-lo) if direction==1 else (hi-bars[-1].c)/(hi-lo))

def confirmed_pivots(bars):
    """Two-left/two-right pivot becomes usable only at confirmation close."""
    hi=lo=None;output=[]
    for i in range(len(bars)):
        if i>=4:
            c=bars[i-2];left=bars[i-4:i-2];right=bars[i-1:i+1]
            if all(c.h>x.h for x in left) and all(c.h>=x.h for x in right):hi=c.h
            if all(c.l<x.l for x in left) and all(c.l<=x.l for x in right):lo=c.l
        output.append((hi,lo))
    return output

def setup_label(parent,previous,atr,pivot,direction):
    if direction*(parent.c-parent.o)<=0:return 'NEGATIVE'
    if previous is None or atr is None or atr<=0:return 'UNKNOWN'
    body=previous.c-previous.o
    if abs(body)<=Decimal('.25')*atr:return 'EARLY'
    if direction*body>Decimal('.25')*atr:return 'CONTINUATION'
    if direction*body<-Decimal('.25')*atr and pivot is not None:
        if (direction==1 and parent.c>pivot) or (direction==-1 and parent.c<pivot):return 'REVERSAL'
    return 'UNKNOWN'

def _mean(values):return sum(values)/len(values) if values and all(x is not None for x in values) else None

def build_records(data,phase):
    boundary=int(datetime(2025,4,1,tzinfo=timezone.utc).timestamp())
    dev_start=int(datetime(2025,2,1,tzinfo=timezone.utc).timestamp())
    records=[];audit=Counter()
    for asset,frames in data.items():
        series={f:Series(b) for f,b in frames.items()}
        five=series['5m'];daily=Series(aligned_context(five.bars,86400))
        weekly=Series(aligned_context(five.bars,604800,345600))
        eight=Series(aligned_context(frames['4h'],28800))
        for horizon,pf,cf,n,holding in [('INTRADAY','30m','5m',6,3600),('SWING','4h','1h',4,86400)]:
            parents=frames[pf];pivots=confirmed_pivots(parents)
            for i,p in enumerate(parents):
                decision=p.end+60;entry=p.end+300;end=entry+holding
                if phase=='DEV' and not (dev_start<=decision<boundary and end<boundary):continue
                if phase=='OOS' and decision<boundary+holding:continue
                if phase not in ('DEV','OOS'):raise ValueError('PHASE')
                ei=five.starts.get(entry);xi=five.starts.get(end-300)
                if ei is None or xi is None:audit['outcome_unavailable']+=1;continue
                children=series[cf].past(p.end,n)
                merged=aggregate(children,DURATIONS[pf])
                if merged!=p:audit[horizon+'_mtf_exact_mismatch']+=1;continue
                audit[horizon+'_mtf_exact_pass']+=1
                recent=five.past(p.end,21);history=parents[max(0,i-19):i+1]
                if len(recent)!=21 or i<20:audit['context_missing']+=1;continue
                day=daily.past(p.end);week=weekly.past(p.end);last8=eight.past(p.end)
                h1=series['1h'].past(p.end);h4=series['4h'].past(p.end,20)
                trs=[max(b.h-b.l,abs(b.h-parents[k-1].c),abs(b.l-parents[k-1].c)) for k,b in enumerate(parents[i-20:i],start=i-20) if k>0]
                atr=sum(trs)/len(trs) if len(trs)==20 else None
                # Use only pivots already confirmed before the current parent.
                high,low=pivots[i-1] if i else (None,None)
                for direction in (-1,1):
                    child=child_features([b.vector() for b in children],direction)
                    vbase=relative_volume(float(recent[-1].base),[float(b.base) for b in recent[:-1]])
                    vquote=relative_volume(float(recent[-1].quote),[float(b.quote) for b in recent[:-1]])
                    ch=channel(h4,direction)
                    context=_mean([close_location(day[-1],direction) if day else None,close_location(week[-1],direction) if week else None])
                    context_b=_mean([context,close_location(last8[-1],direction) if last8 else None,ch])
                    pivot=high if direction==1 else low
                    broken=None if pivot is None else float(p.c>pivot if direction==1 else p.c<pivot)
                    rv4=relative_volume(float(p.quote),[float(b.quote) for b in parents[i-20:i]])
                    if horizon=='INTRADAY':
                        raw={'I1':strong_close(p,direction),'I2':child['net_path'],
                          'I3':100*direction*float(recent[-1].c/recent[-2].c-1),'I4':child['half_quote_share'],
                          'I5':_mean([close_location(h1[-1],direction) if h1 else None,close_location(h4[-1],direction) if h4 else None]),'I6':None}
                    else:
                        raw={'S1':_mean([ch,broken]),'S2':strong_close(p,direction),'S3':child['net_path'],
                          'S4':context,'S5':None,'S5_MOM':100*direction*float(p.c/p.o-1),'S5_VOL':rv4,'S6':None}
                    raw.update(V_BASE=vbase,V_QUOTE=vquote)
                    future=five.bars[ei:xi+1]
                    if len(future)*300!=holding:raise ValueError('OUTCOME_GAP')
                    dt=datetime.fromtimestamp(p.end,tz=timezone.utc);weekstart=p.end-(dt.weekday()*86400+dt.hour*3600+dt.minute*60+dt.second)
                    regime='UNKNOWN' if not day else 'UP' if day[-1].c>day[-1].o else 'DOWN' if day[-1].c<day[-1].o else 'QUIET'
                    outcome=fixed_outcome(float(five.bars[ei].o),float(five.bars[xi].c),direction)
                    records.append({'asset':asset,'horizon':horizon,'direction':direction,'close':p.end,'week':weekstart,
                        'slot':p.end-weekstart,'setup':setup_label(p,parents[i-1] if i else None,atr,pivot,direction),
                        'regime':regime,'raw':raw,'child':child,'S4_B':context_b,'outcome':outcome,
                        'barrier':first_hit([(float(b.h),float(b.l)) for b in future],float(five.bars[ei].o),direction),
                        'fee_sensitivity':{str(bps):outcome-2*bps/10000 for bps in (0,5,10)}})
    return records,dict(audit)

def fit_models(records,phase):
    if phase!='DEV':raise ValueError('HOLDOUT_FIT_FORBIDDEN')
    values=defaultdict(list)
    for r in records:
        for key,value in r['raw'].items():
            if value is not None:
                if not math.isfinite(value):raise ValueError('NONFINITE_FEATURE')
                values[f"{r['horizon']}:{r['direction']}:{key}"].append(value)
    models={}
    for key,v in values.items():
        center=median(v);mad=median(abs(x-center) for x in v)
        models[key]={'values':sorted(v),'median':center,'mad':mad,'fit_phase':'DEV'}
    return models

def normalized(r,key,models,family='Q'):
    value=r['raw'].get(key)
    if key=='S5':return _mean([normalized(r,'S5_MOM',models,family),normalized(r,'S5_VOL',models,family)])
    if value is None:return None
    if family=='D':
        if key not in DOMAIN:return None
        if not 0<=value<=1:raise ValueError('DOMAIN_FEATURE_RANGE')
        return value
    m=models.get(f"{r['horizon']}:{r['direction']}:{key}")
    if not m or m['fit_phase']!='DEV':return None
    if family=='Q':
        from bisect import bisect_left,bisect_right
        v=m['values'];return (bisect_left(v,value)+bisect_right(v,value))/(2*len(v))
    if family=='R':return None if m['mad']==0 else .5+math.atan((value-m['median'])/(1.4826*m['mad']))/math.pi
    raise ValueError('NORMALIZER')

def semantic_arms(r,models,key):
    family='D' if key in DOMAIN else 'Q'
    a=normalized(r,key,models,family)
    if a is None:return (None,None)
    if key in ('I2','S3'):return a,_mean([a,r['child']['retention'],r['child']['consistency']])
    if key=='I4_BASE':return None,None
    if key=='S4':return a,r['S4_B']
    raise ValueError('SEMANTIC_SCOPE')

def _moments(rows):
    # n,x,y,xx,yy,xy,z,zz,zy: paired x/y vs z/y correlations.
    return [len(rows),sum(x for x,y,z in rows),sum(y for x,y,z in rows),sum(x*x for x,y,z in rows),
            sum(y*y for x,y,z in rows),sum(x*y for x,y,z in rows),sum(z for x,y,z in rows),
            sum(z*z for x,y,z in rows),sum(z*y for x,y,z in rows)]

def _delta(m):
    n,x,y,xx,yy,xy,z,zz,zy=m
    if n<3:return None
    sy=yy-y*y/n;sx=xx-x*x/n;sz=zz-z*z/n
    if min(sx,sy,sz)<=0:return None
    return (zy-z*y/n)/math.sqrt(sz*sy)-(xy-x*y/n)/math.sqrt(sx*sy)

def _sum_moments(items):return [sum(column) for column in zip(*items)]

def holm(pvalues,family_size=40):
    valid=sorted((p,key) for key,p in pvalues.items() if p is not None)
    if len(valid)>family_size:raise ValueError('MULTIPLICITY_FAMILY_EXCEEDED')
    output={key:None for key in pvalues};bound=0.
    for i,(p,key) in enumerate(valid):
        if not 0<=p<=1:raise ValueError('INVALID_P_VALUE')
        bound=max(bound,min(1.,p*(family_size-i)));output[key]=bound
    return output

def compare(records,xvalues,zvalues,*,permutations=4096,bootstraps=512):
    """Whole-week label exchangeability is an explicit research assumption.

    P-values are Monte Carlo null-association diagnostics, not causal/PIT proof.
    Bootstrap intervals are exploratory; they do not certify independent N.
    """
    groups=defaultdict(list)
    for i,r in enumerate(records):groups[(r['asset'],r['week'])].append(i)
    horizon=records[0]['horizon'] if records else 'INTRADAY'
    expected=672 if horizon=='INTRADAY' else 84
    groups={k:v for k,v in groups.items() if len(v)==expected}
    lookup={(r['asset'],r['week'],r['slot'],r['direction']):r['outcome'] for r in records}
    keys=sorted(groups);byasset=defaultdict(list)
    for k in keys:byasset[k[0]].append(k)
    matrices={};common_count=0
    for source,indices in groups.items():
        selected=[i for i in indices if xvalues[i] is not None and zvalues[i] is not None]
        common_count+=len(selected)
        for target in byasset[source[0]]:
            pairs=[(xvalues[i],lookup[(source[0],target[1],records[i]['slot'],records[i]['direction'])],zvalues[i]) for i in selected]
            matrices[(source,target)]=_moments(pairs)
    if not keys:return {'status':'INSUFFICIENT_COMPLETE_WEEKS','p':None,'N_common':0,'N_week_blocks':0}
    diagonal=[matrices[k,k] for k in keys];observed=_delta(_sum_moments(diagonal))
    if observed is None:return {'status':'ZERO_VARIANCE_OR_MISSING','p':None,'N_common':common_count,'N_week_blocks':len(keys)}
    rng=random.Random(1042);boots=[]
    for _ in range(bootstraps):
        value=_delta(_sum_moments([rng.choice(diagonal) for k in keys]))
        if value is not None:boots.append(value)
    rng=random.Random(2042);extreme=0;valid=0
    for _ in range(permutations):
        mapping={}
        for same in byasset.values():
            target=same[:];rng.shuffle(target);mapping.update(zip(same,target))
        value=_delta(_sum_moments([matrices[k,mapping[k]] for k in keys]))
        if value is not None:
            valid+=1;extreme+=abs(value)>=abs(observed)
    boots.sort()
    total=_sum_moments(diagonal)
    n,x,y,xx,yy,xy,z,zz,zy=total
    mx,my,mz=x/n,y/n,z/n
    vx,vy,vz=xx/n-mx*mx,yy/n-my*my,zz/n-mz*mz
    rx=(xy/n-mx*my)/math.sqrt(vx*vy);rz=(zy/n-mz*my)/math.sqrt(vz*vy)
    influences=[];events=set()
    for indices in groups.values():
        for i in indices:
            if xvalues[i] is None or zvalues[i] is None:continue
            a=(xvalues[i]-mx)/math.sqrt(vx);b=(records[i]['outcome']-my)/math.sqrt(vy);c=(zvalues[i]-mz)/math.sqrt(vz)
            influences.append(c*b-.5*rz*(c*c+b*b)-(a*b-.5*rx*(a*a+b*b)))
            events.add((records[i]['asset'],records[i].get('close',records[i]['week']+records[i]['slot'])))
    iid_var=sum(v*v for v in influences)/(n*(n-1)) if n>1 else 0
    mean_boot=sum(boots)/len(boots) if boots else 0
    block_var=sum((v-mean_boot)**2 for v in boots)/(len(boots)-1) if len(boots)>1 else 0
    neff=min(len(events),n*iid_var/block_var) if iid_var>0 and block_var>0 else None
    return {'status':'EXPLORATORY_BLOCK_EXCHANGEABILITY_ASSUMED','delta_correlation_B_minus_A':observed,
      'p':(extreme+1)/(valid+1) if valid else None,'bootstrap_95_exploratory':[boots[int(.025*(len(boots)-1))],boots[int(.975*(len(boots)-1))]] if boots else None,
      'N_common':common_count,'N_week_blocks':len(keys),'N_effective':None,'N_effective_variance_ratio_diagnostic':neff,'N_event_clusters_common':len(events),'valid_permutations':valid,
      'independent_PIT':False,'economic_qualification':False}

def forward_admission(*,now,close,publication_attested,clock_age,uncertainty,pinned,frozen,evidence_approved):
    if not pinned or not frozen or not evidence_approved:return 'NOT_ATTEMPTED_APPROVAL_OR_PIN'
    if not publication_attested:return 'NOT_ATTEMPTED_PUBLICATION_UNKNOWN'
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in (now,close,clock_age,uncertainty)):return 'CLOCK_UNTRUSTED'
    if not 0<=clock_age<=30 or not 0<=uncertainty<1:return 'CLOCK_UNTRUSTED'
    if now<close+60:return 'NOT_YET_ADMITTED'
    if now>=close+600:return 'LATE_ZERO_HTTP'
    return 'ELIGIBLE_CONTRACT_ONLY_NO_TRANSPORT'
