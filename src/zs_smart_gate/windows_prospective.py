"""New-study freeze/admission contracts. No network or scheduler activation.

Original canceled 03B3 identity/history is never edited or used as observations.
The GitHub single-study journal is an owner-gated interface, not a backend.
"""
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta, timezone
from typing import Protocol

from .windows_operations import canonical_sha

UTC=timezone.utc
SYMBOLS=('BTCUSDT','ETHUSDT','AAVEUSDT')
OLD_ID='PROSPECTIVE-SHA256-6db82e807757262a7b1a54b4f533c5c1e155aa968ec2aafdb3d9d8cabc8a4422'


def aware(value):
    if value.tzinfo is None: raise ValueError('UTC_AWARE_REQUIRED')
    return value.astimezone(UTC)


def proposal(day: date, runner_sha: str):
    if len(runner_sha)!=40 or any(c not in '0123456789abcdef' for c in runner_sha):
        raise ValueError('PIN_REQUIRED')
    start=datetime.combine(day,time(),UTC)
    groups=[{'frame':frame,'close':(start+timedelta(minutes=minutes)).isoformat()}
            for frame,minutes in [('30m',30),('30m',60),('4h',240),('4h',480)]]
    return {'version':1,'kind':'WINDOWS_PROSPECTIVE_NEW','day':day.isoformat(),
            'runner_sha':runner_sha,'symbols':list(SYMBOLS),'selection':'PREREGISTERED_FIXED_THREE',
            'eligibility':'ACCEPTED_SPOT_USDT_FILTER_AT_RECEIPT;INELIGIBLE_IS_MISSING_NO_REPLACEMENT',
            'groups':groups,'grace_seconds':600,'trigger_delay_seconds':60,
            'attempts_per_symbol':8,'attempts_per_group':24,'attempts_total':96,
            'clock_uncertainty_max_seconds':0.5,'os_dispersion_max_seconds':1.0,
            'clock_sample_max_age_seconds':30,'retention':'OWNER_DECISION_REQUIRED',
            'terminal':(start+timedelta(hours=8,minutes=10)).isoformat(),
            'old_study_status':'ABORTED_BY_OWNER / EXCLUDED_FROM_SCIENTIFIC_EVALUATION'}


def freeze(plan, *, now, accepted_runner_sha, storage_decision_id):
    """Called only after independent approvals; returned object must be published
    immutably to GitHub before the full future UTC day. No in-place date moving.
    """
    now=aware(now)
    expected=proposal(date.fromisoformat(plan['day']),accepted_runner_sha)
    if plan!=expected: raise ValueError('NONCANONICAL_PLAN')
    start=datetime.combine(date.fromisoformat(plan['day']),time(),UTC)
    if now>=start or not storage_decision_id: raise ValueError('FREEZE_APPROVAL_OR_FUTURE_DAY_REQUIRED')
    manifest={'plan':plan,'frozen_at':now.isoformat(),'storage_decision_id':storage_decision_id}
    identity='WINDOWS-PROSPECTIVE-SHA256-'+canonical_sha(manifest)
    return {'study_id':identity,**manifest}


def validate(manifest):
    payload={k:v for k,v in manifest.items() if k!='study_id'}
    if manifest['study_id'] != 'WINDOWS-PROSPECTIVE-SHA256-'+canonical_sha(payload):
        raise ValueError('MANIFEST_CHANGED')
    plan=manifest['plan']
    if plan!=proposal(date.fromisoformat(plan['day']),plan['runner_sha']):
        raise ValueError('NONCANONICAL_PLAN')
    if not manifest['storage_decision_id'] or aware(datetime.fromisoformat(manifest['frozen_at'])) >= datetime.combine(date.fromisoformat(plan['day']),time(),UTC):
        raise ValueError('LATE_OR_UNAPPROVED_FREEZE')
    return plan


@dataclass(frozen=True)
class ClockEvidence:
    sampled_at: datetime
    offset_seconds: float
    rtt_seconds: float
    uncertainty_seconds: float | None
    os_root_dispersion_seconds: float | None
    os_synced: bool

    def trusted(self, now):
        import math
        vals=(self.offset_seconds,self.rtt_seconds,self.uncertainty_seconds,self.os_root_dispersion_seconds)
        return (self.os_synced and all(x is not None and math.isfinite(x) for x in vals)
                and abs(self.offset_seconds)<=0.5 and 0<=self.rtt_seconds<=1
                and self.rtt_seconds/2<=self.uncertainty_seconds<=0.5
                and 0<=self.os_root_dispersion_seconds<=1
                and 0<=(aware(now)-aware(self.sampled_at)).total_seconds()<=30)


def admission(manifest, group, now, clock):
    plan=validate(manifest);now=aware(now)
    if group not in plan['groups']:return 'UNAPPROVED_SCOPE'
    close=datetime.fromisoformat(group['close'])
    if now>=close+timedelta(seconds=600):return 'LATE'
    if clock is None or not clock.trusted(now):return 'CLOCK_UNTRUSTED'
    low=now+timedelta(seconds=clock.offset_seconds-clock.uncertainty_seconds)
    high=now+timedelta(seconds=clock.offset_seconds+clock.uncertainty_seconds)
    if low<close:return 'NOT_YET_CLOSED'
    if high>=close+timedelta(seconds=600):return 'LATE'
    return 'ELIGIBLE'


class ApprovedJournal(Protocol):
    def claim_before_attempts(self, study_id: str, event_id: str) -> bool: ...
    def append_and_readback(self, event_id: str, payload: dict, checksum: str) -> bool: ...


class AttemptBudget:
    """One process budget, not a cross-host exactly-once guarantee."""
    def __init__(self):self.counts={}
    def before_attempt(self, manifest, group, symbol, now, clock):
        plan=validate(manifest)
        if symbol not in plan['symbols'] or admission(manifest,group,now,clock)!='ELIGIBLE':
            raise ValueError('NOT_ATTEMPTED')
        key=(manifest['study_id'],group['close'],symbol)
        per_symbol=self.counts.get(key,0)
        per_group=sum(v for k,v in self.counts.items() if k[:2]==key[:2])
        total=sum(v for k,v in self.counts.items() if k[0]==key[0])
        if per_symbol>=8 or per_group>=24 or total>=96:raise ValueError('ATTEMPT_BUDGET')
        self.counts[key]=per_symbol+1


def prepare_event(manifest, group, now, clock, *, journal, pm_sha, frozen_readback_sha):
    plan=validate(manifest)
    if pm_sha!=plan['runner_sha'] or frozen_readback_sha!=canonical_sha(manifest):
        return {'status':'NOT_ATTEMPTED','reason':'PM_OR_GITHUB_READBACK','http_attempts':0}
    status=admission(manifest,group,now,clock)
    if status!='ELIGIBLE':return {'status':status,'http_attempts':0}
    event_id=canonical_sha({'study':manifest['study_id'],'group':group})
    try:
        claimed=journal.claim_before_attempts(manifest['study_id'],event_id)
    except Exception:
        return {'status':'NOT_ATTEMPTED','reason':'GITHUB_AUTHORITY_UNAVAILABLE','http_attempts':0}
    if not claimed:return {'status':'NOT_ATTEMPTED','reason':'DUPLICATE_OR_INTERRUPTED','http_attempts':0}
    # This preparation cannot arm a transport or start the prospective study.
    return {'status':'NOT_ATTEMPTED','reason':'LIVE_TRANSPORT_NOT_ARMED','http_attempts':0,'event_id':event_id}
