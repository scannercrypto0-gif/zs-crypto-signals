"""03B3 frozen prospective research protocol. No historical replay and no trading.

Freeze preceded all planned candle closes. Asset #3 was selected once from the
strict sorted eligible Binance Spot USDT universe in the opt-in Actions run
40687445599 (4 physical attempts, UTC 2026-10-28T12:24:01.709500+00:00).
The selected AAVEUSDT and universe fingerprint are immutable study inputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import json
import re

from .core import utc
from .stage03a_contracts import Direction, Horizon

VERSION="03B3_PROSPECTIVE_PIT_FINITE_V1"
SOURCE="BINANCE:SPOT:PUBLIC_KLINES"
SELECTION_EVIDENCE_RUN=40687445599
SELECTED_AT="2026-10-28T12:24:01.709500+00:00"
ELIGIBLE_UNIVERSE_SHA="3b29fa4c5d96d9cd9ef70eca0f965c296afdf21f4cc17a9727c3494592128bc9"
THIRD="AAVEUSDT"  # lexicographic first; no post-outcome replacement


@dataclass(frozen=True)
class Slot:
    horizon: Horizon
    close_at: datetime
    label: str

    def __post_init__(self):
        if not isinstance(self.horizon,Horizon):
            raise ValueError("INVALID_SLOT_HORIZON")
        object.__setattr__(self,"close_at",utc(self.close_at))
        if not self.label or self.close_at.second or self.close_at.microsecond:
            raise ValueError("INVALID_SLOT_CLOSE")
        step=1800 if self.horizon is Horizon.INTRADAY else 14400
        if int(self.close_at.timestamp())%step:
            raise ValueError("INVALID_UTC_CLOSE_ALIGNMENT")


@dataclass(frozen=True)
class Protocol:
    version: str
    source: str
    assets: tuple[str,...]
    directions: tuple[Direction,...]
    slots: tuple[Slot,...]
    start_at: datetime
    stop_at: datetime
    receipt_grace_seconds: int
    physical_attempts_per_slot: int
    total_slot_attempt_ceiling: int
    preselection_attempt_ceiling: int
    selection_run: int
    selection_at: datetime
    eligible_universe_sha256: str
    metrics: tuple[str,...]
    missing_policy: str
    capture_policy: str
    terminal_policy: str
    study_id: str=field(init=False)

    def __post_init__(self):
        for k in ("start_at","stop_at","selection_at"):
            object.__setattr__(self,k,utc(getattr(self,k)))
        if self.version!=VERSION or self.source!=SOURCE:
            raise ValueError("INVALID_PROSPECTIVE_PROTOCOL_VERSION_SOURCE")
        if (self.assets!=("BTCUSDT","ETHUSDT",THIRD) or
            any(not re.fullmatch(r"[A-Z0-9]{1,16}USDT",s) for s in self.assets) or
            len(set(self.assets))!=3 or self.directions!=(Direction.UP,Direction.DOWN)):
            raise ValueError("THREE_IMMUTABLY_SELECTED_SPOT_ASSETS_REQUIRED")
        if (type(self.slots) is not tuple or len(self.slots)!=4 or
            sum(s.horizon is Horizon.INTRADAY for s in self.slots)!=2 or
            sum(s.horizon is Horizon.SWING for s in self.slots)!=2 or
            len({(s.horizon,s.close_at) for s in self.slots})!=4 or
            list(s.close_at for s in self.slots)!=sorted(s.close_at for s in self.slots)):
            raise ValueError("EXACTLY_FOUR_ORDERED_UNIQUE_HORIZON_WINDOWS")
        if self.stop_at-self.start_at!=timedelta(hours=24):
            raise ValueError("ONE_FINITE_24H_STUDY_ONLY")
        if (self.selection_at>=self.start_at or
            any(s.close_at<=self.start_at or s.close_at>=self.stop_at for s in self.slots) or
            self.selection_run!=SELECTION_EVIDENCE_RUN or
            self.eligible_universe_sha256!=ELIGIBLE_UNIVERSE_SHA or
            self.selection_at.isoformat()!=SELECTED_AT):
            raise ValueError("FROZEN_SELECTION_OR_SLOT_TIME_INVALID")
        if (self.receipt_grace_seconds!=600 or
            self.physical_attempts_per_slot!=8 or
            self.total_slot_attempt_ceiling!=96 or
            self.preselection_attempt_ceiling!=8):
            raise ValueError("UNAUTHORIZED_CAPTURE_OR_ATTEMPT_BUDGET")
        if (not self.metrics or len(set(self.metrics))!=len(self.metrics) or
            any(not isinstance(x,str) or not x for x in self.metrics) or
            not all(isinstance(v,str) and v for v in (
                self.missing_policy,self.capture_policy,self.terminal_policy))):
            raise ValueError("MISSING_FROZEN_SCIENTIFIC_POLICY")
        raw=json.dumps(self.canonical(),sort_keys=True,ensure_ascii=True,
                       separators=(",",":")).encode("utf-8")
        object.__setattr__(self,"study_id","PROSPECTIVE-SHA256-"+hashlib.sha256(raw).hexdigest())

    def canonical(self):
        return {"version":self.version,"source":self.source,
                "assets":list(self.assets),"directions":[d.value for d in self.directions],
                "slots":[{"horizon":s.horizon.value,"close_at":s.close_at.isoformat(),
                          "label":s.label} for s in self.slots],
                "start_at":self.start_at.isoformat(),"stop_at":self.stop_at.isoformat(),
                "receipt_grace_seconds":self.receipt_grace_seconds,
                "physical_attempts_per_slot":self.physical_attempts_per_slot,
                "total_slot_attempt_ceiling":self.total_slot_attempt_ceiling,
                "preselection_attempt_ceiling":self.preselection_attempt_ceiling,
                "selection_run":self.selection_run,
                "selection_at":self.selection_at.isoformat(),
                "eligible_universe_sha256":self.eligible_universe_sha256,
                "metrics":list(self.metrics),
                "missing_policy":self.missing_policy,
                "capture_policy":self.capture_policy,
                "terminal_policy":self.terminal_policy}

    def as_dict(self):
        return {"study_id":self.study_id,**self.canonical()}

    def slot(self,symbol,horizon,label):
        if symbol not in self.assets or not isinstance(horizon,Horizon):
            raise ValueError("SESSION_NOT_IN_PREDECLARED_SPOT_UNIVERSE")
        matched=[s for s in self.slots if s.horizon is horizon and s.label==label]
        if len(matched)!=1:
            raise ValueError("UNDECLARED_PROSPECTIVE_WINDOW")
        return matched[0]

    @property
    def planned_observations(self):
        return len(self.assets)*len(self.slots)


def T(iso):
    return datetime.fromisoformat(iso)


MANIFEST=Protocol(
    version=VERSION,source=SOURCE,
    assets=("BTCUSDT","ETHUSDT",THIRD),
    directions=(Direction.UP,Direction.DOWN),
    slots=(
        Slot(Horizon.INTRADAY,T("2026-10-28T14:00:00+00:00"),"I1"),
        Slot(Horizon.INTRADAY,T("2026-10-28T14:30:00+00:00"),"I2"),
        Slot(Horizon.SWING,T("2026-10-28T16:00:00+00:00"),"S1"),
        Slot(Horizon.SWING,T("2026-10-28T20:00:00+00:00"),"S2"),
    ),
    start_at=T("2026-10-28T13:00:00+00:00"),
    stop_at=T("2026-10-29T13:00:00+00:00"),
    receipt_grace_seconds=600,
    physical_attempts_per_slot=8,
    total_slot_attempt_ceiling=96,
    preselection_attempt_ceiling=8,
    selection_run=SELECTION_EVIDENCE_RUN,
    selection_at=T(SELECTED_AT),
    eligible_universe_sha256=ELIGIBLE_UNIVERSE_SHA,
    metrics=("DIRECTIONAL_CLOSE_LOCATION","SIGNED_BODY_RANGE","ADVERSE_WICK_RANGE",
             "NET_OVER_BODY_PATH","NET_OVER_GAP_AWARE_PATH","SECOND_HALF_BASE_SHARE",
             "SECOND_HALF_QUOTE_SHARE","FAVORABLE_BASE_SHARE","FAVORABLE_QUOTE_SHARE",
             "BASELINE_SIGNED_OC_PCT","BASELINE_PARENT_BASE_VOLUME",
             "BASELINE_PARENT_QUOTE_VOLUME"),
    missing_policy=("Every one of twelve fixed slots must be accounted as OBSERVED_PIT, "
                    "INELIGIBLE, FAILED, LATE or NOT_ATTEMPTED; absent capture is "
                    "NOT_ATTEMPTED, no backfill/resample/substitution"),
    capture_policy=("One manually dispatched per-slot GET cycle strictly within 600 seconds "
                    "AFTER declared close, receipt and eligibility at capture only; "
                    "no late historical re-fetch treated as PIT. Max 8 physical attempts "
                    "including retries, 60 second pre-attempt soft guard"),
    terminal_policy=("Stop on 12 slots OR after 24 hours, no automatic next phase; "
                     "INSUFFICIENT_EVIDENCE/ BLOCKED_DATA are valid terminal conclusions; "
                     "no thresholds, outcomes, trading, Signal IDs or messaging"),
)
