"""010 preregistered research primitives; never emits a V2 score or trade.

Retrospective integrity and descriptive diagnostics are not PIT qualification.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import atan, pi, isfinite, atanh, ceil, sqrt
from statistics import median, NormalDist

VERSION='010-PILOT-1'

def finite(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value):
        raise ValueError('FINITE_NUMBER_REQUIRED')
    return float(value)

@dataclass(frozen=True)
class ECDF:
    values: tuple
    @classmethod
    def fit(cls,values,*,phase):
        if phase!='DEV':raise ValueError('HOLDOUT_FIT_FORBIDDEN')
        data=tuple(sorted(finite(x) for x in values))
        if not data:raise ValueError('EMPTY_DEV')
        return cls(data)
    def apply(self,value):
        if value is None:return None
        value=finite(value)
        return (sum(x<value for x in self.values)+.5*sum(x==value for x in self.values))/len(self.values)

def robust(value,dev,*,phase='DEV'):
    if phase!='DEV':raise ValueError('HOLDOUT_FIT_FORBIDDEN')
    if value is None:return None
    xs=[finite(x) for x in dev]
    if not xs:return None
    center=median(xs);mad=median(abs(x-center) for x in xs)
    return None if mad==0 else .5+atan((finite(value)-center)/(1.4826*mad))/pi

def child_features(children,direction):
    """Rows: open,high,low,close,base,quote. Caller verifies time/source integrity."""
    if direction not in (-1,1) or len(children) not in (4,6):raise ValueError('SCOPE')
    cs=[tuple(finite(x) for x in c) for c in children]
    if any(len(c)!=6 or c[2]<=0 or c[1]<max(c[0],c[3]) or c[2]>min(c[0],c[3]) or c[4]<0 or c[5]<0 for c in cs):raise ValueError('OHLCV')
    start=cs[0][0];net=direction*(cs[-1][3]-start)
    path=sum(abs(c[3]-c[0]) for c in cs)
    favorable=max((c[1]-start if direction==1 else start-c[2]) for c in cs)
    volume=sum(c[5] for c in cs)
    return {'net_path':net/path if path else None,
            'retention':max(0.,min(1.,net/favorable)) if favorable>0 else None,
            'consistency':sum(direction*(c[3]-c[0])>0 for c in cs)/len(cs),
            'half_quote_share':sum(c[5] for c in cs[len(cs)//2:])/volume if volume else None}

def relative_volume(current,previous):
    if len(previous)!=20:return None
    xs=[finite(x) for x in previous];current=finite(current)
    if current<0 or any(x<0 for x in xs):raise ValueError('NEGATIVE_VOLUME')
    mean=sum(xs)/20
    return current/mean if mean>0 else None

def pit_status(*,close,publication,source_available,received,decision,uncertainty,independent):
    times=(close,publication,source_available,received,decision)
    if any(t is None for t in times):return 'UNKNOWN_PUBLICATION_OR_TIME'
    if any(not isinstance(t,datetime) or t.tzinfo is None or t.utcoffset() is None for t in times):return 'INVALID_UTC'
    if not independent:return 'NO_INDEPENDENT_AUTHORITY'
    if uncertainty is None:return 'CLOCK_UNKNOWN'
    try:u=finite(uncertainty)
    except ValueError:return 'CLOCK_INVALID'
    if not 0<=u<1:return 'CLOCK_UNTRUSTED'
    utc=[x.astimezone(timezone.utc) for x in times]
    if utc!=sorted(utc):return 'LATE_OR_REVERSED_TIME'
    return 'PASS_INJECTED_EVIDENCE_NOT_EXTERNAL_CERTIFICATION'

def split_admissible(decision,outcome_end,*,phase,boundary,horizon):
    if any(x.tzinfo is None for x in (decision,outcome_end,boundary)):raise ValueError('UTC_REQUIRED')
    if outcome_end<=decision:raise ValueError('OUTCOME_ORDER')
    if phase=='DEV':return decision<boundary and outcome_end<boundary
    if phase=='OOS':return decision>=boundary+horizon
    raise ValueError('PHASE')

def fixed_outcome(entry,exit,direction):
    entry=finite(entry);exit=finite(exit)
    if entry<=0 or exit<=0 or direction not in (-1,1):raise ValueError('PRICE_DIRECTION')
    return direction*(exit-entry)/entry

def first_hit(rows,entry,direction,barrier=.01):
    entry=finite(entry);barrier=finite(barrier)
    if entry<=0 or direction not in (-1,1) or barrier<=0:raise ValueError('BARRIER')
    for high,low in rows:
        high,low=finite(high),finite(low)
        favorable=(high>=entry*(1+barrier) if direction==1 else low<=entry*(1-barrier))
        adverse=(low<=entry*(1-barrier) if direction==1 else high>=entry*(1+barrier))
        if favorable and adverse:return 'UNKNOWN_SAME_BAR_ORDER'
        if favorable:return 'FAVORABLE'
        if adverse:return 'ADVERSE'
    return 'CENSORED'

def correlation(xs,ys):
    if len(xs)!=len(ys) or len(xs)<3:return None
    xs=[finite(x) for x in xs];ys=[finite(y) for y in ys]
    a=sum(xs)/len(xs);b=sum(ys)/len(ys)
    denominator=sqrt(sum((x-a)**2 for x in xs)*sum((y-b)**2 for y in ys))
    return sum((x-a)*(y-b) for x,y in zip(xs,ys))/denominator if denominator else None

def planned_independent_clusters(effect=.1,alpha=.05,power=.8,comparisons=16):
    if not 0<effect<1 or not 0<alpha<1 or not .5<power<1 or comparisons<1:raise ValueError('POWER_INPUT')
    z=NormalDist()
    return ceil(((z.inv_cdf(1-alpha/(2*comparisons))+z.inv_cdf(power))/atanh(effect))**2+3)
