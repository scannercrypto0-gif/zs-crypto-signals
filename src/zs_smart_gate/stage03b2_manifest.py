"""03B2 executable, predeclared and immutable research protocol (stdlib only).

This manifest MUST be committed before the first market-data LIVE execution.
Historical Binance REST retrieval proves ONLY present retrieval of old OHLCV,
not that the original observer knew prices, eligibility or publication times.
Changing *any* protocol field produces a DIFFERENT SHA256 study identity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json
import re

from .core import utc
from .stage03a_contracts import Direction, Horizon

PROTOCOL_VERSION = "03B2_FROZEN_RESEARCH_PROTOCOL_V1"
RETROSPECTIVE_EVIDENCE = "RETROSPECTIVE_RETRIEVAL_NOT_HISTORICAL_PIT_PROOF"
EXPECTED_HORIZONS = (Horizon.INTRADAY, Horizon.SWING)
EXPECTED_DIRECTIONS = (Direction.UP, Direction.DOWN)


class Partition(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    HOLDOUT = "HOLDOUT"


@dataclass(frozen=True)
class AssetSpec:
    symbol: str
    declared_cohort: str  # hypotheses for stratification; NOT verified historical liquidity

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not re.fullmatch(r"[A-Z0-9]{1,16}USDT", self.symbol):
            raise ValueError("INVALID_FROZEN_SPOT_ASSET")
        if self.declared_cohort not in ("MAJOR_REFERENCE", "ALT_LARGE_REFERENCE",
                                        "ALT_LIQUIDITY_UNVERIFIED"):
            raise ValueError("UNAPPROVED_COHORT_LABEL")


@dataclass(frozen=True)
class WindowSpec:
    partition: Partition
    close_at: datetime  # EXCLUSIVE closed parent UTC time (fixed before fetching)
    label: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "close_at", utc(self.close_at))
        if not isinstance(self.partition, Partition) or not self.label.strip():
            raise ValueError("INVALID_WINDOW_PARTITION_OR_LABEL")


@dataclass(frozen=True)
class StudyManifest:
    version: str
    provider_source: str
    assets: tuple[AssetSpec, ...]
    horizons: tuple[Horizon, ...]
    directions: tuple[Direction, ...]
    windows: tuple[WindowSpec, ...]
    metric_version: str
    candidate_formulas: tuple[str, ...]
    baseline_formulas: tuple[str, ...]
    transport_attempt_budget: int
    ingestion_semantics: str
    retrospective_assumption: str
    missingness_policy: str
    evaluation_policy: str
    study_id: str = field(init=False)

    def __post_init__(self) -> None:
        if self.version != PROTOCOL_VERSION:
            raise ValueError("UNSUPPORTED_MANIFEST_VERSION")
        if self.provider_source != "BINANCE:SPOT:PUBLIC_KLINES":
            raise ValueError("UNAPPROVED_SOURCE")
        if self.horizons != EXPECTED_HORIZONS or self.directions != EXPECTED_DIRECTIONS:
            raise ValueError("INVALID_HORIZON_OR_DIRECTION_UNIVERSE")
        if type(self.assets) is not tuple or len(self.assets) < 2 or not all(
            isinstance(a, AssetSpec) for a in self.assets):
            raise ValueError("INVALID_FROZEN_ASSET_SAMPLE")
        if len(set(a.symbol for a in self.assets)) != len(self.assets):
            raise ValueError("DUPLICATE_ASSET_IN_MANIFEST")
        if type(self.windows) is not tuple or len(self.windows) < 2 or not all(
            isinstance(w, WindowSpec) for w in self.windows):
            raise ValueError("INVALID_FROZEN_WINDOW_LIST")
        if len(set(w.close_at for w in self.windows)) != len(self.windows):
            raise ValueError("DUPLICATE_STUDY_WINDOW")
        # Commit order is a protocol input: a later holdout must never be
        # presented before development, even if the set of dates is unchanged.
        if tuple(w.close_at for w in self.windows) != tuple(
                sorted(w.close_at for w in self.windows)):
            raise ValueError("SPLIT_LEAKAGE_NONCHRONOLOGICAL_MANIFEST_ORDER")
        dev = [w.close_at for w in self.windows if w.partition is Partition.DEVELOPMENT]
        hold = [w.close_at for w in self.windows if w.partition is Partition.HOLDOUT]
        if not dev or not hold or max(dev) >= min(hold):
            raise ValueError("SPLIT_LEAKAGE_OR_NONCHRONOLOGICAL_WINDOWS")
        if any(w.close_at.microsecond or w.close_at.second or
               int(w.close_at.timestamp()) % (4 * 3600) for w in self.windows):
            raise ValueError("WINDOWS_MUST_ALIGN_TO_BOTH_30M_AND_4H")
        if not (type(self.candidate_formulas) is tuple
                and type(self.baseline_formulas) is tuple
                and self.candidate_formulas and self.baseline_formulas
                and all(isinstance(x, str) and x.strip()
                        for x in (*self.candidate_formulas, *self.baseline_formulas))):
            raise ValueError("INVALID_FROZEN_FORMULA_DECLARATION")
        if self.transport_attempt_budget != 8 or isinstance(self.transport_attempt_budget, bool):
            raise ValueError("PHYSICAL_ATTEMPT_CEILING_MUST_REMAIN_8")
        if self.retrospective_assumption != RETROSPECTIVE_EVIDENCE:
            raise ValueError("CANNOT_CLAIM_RETROSPECTIVE_HISTORICAL_PIT")
        if not all(isinstance(v, str) and v.strip() for v in
                   (self.ingestion_semantics, self.missingness_policy, self.evaluation_policy,
                    self.metric_version)):
            raise ValueError("MISSING_RESEARCH_GOVERNANCE")
        serialized = json.dumps(self.canonical_fields(), sort_keys=True,
                                ensure_ascii=True, separators=(",", ":"))
        object.__setattr__(self, "study_id",
                           "STUDY-SHA256-" + hashlib.sha256(serialized.encode("utf-8")).hexdigest())

    def canonical_fields(self) -> dict:
        return {
            "version": self.version, "provider_source": self.provider_source,
            "assets": [{"symbol": a.symbol, "declared_cohort": a.declared_cohort}
                       for a in self.assets],
            "horizons": [h.value for h in self.horizons],
            "directions": [d.value for d in self.directions],
            "windows": [{"partition": w.partition.value, "close_at": w.close_at.isoformat(),
                         "label": w.label} for w in self.windows],
            "metric_version": self.metric_version,
            "candidate_formulas": list(self.candidate_formulas),
            "baseline_formulas": list(self.baseline_formulas),
            "transport_attempt_budget": self.transport_attempt_budget,
            "ingestion_semantics": self.ingestion_semantics,
            "retrospective_assumption": self.retrospective_assumption,
            "missingness_policy": self.missingness_policy,
            "evaluation_policy": self.evaluation_policy,
        }

    def as_dict(self) -> dict:
        return {"study_id": self.study_id, **self.canonical_fields()}

    def session(self, symbol: str, horizon: Horizon, partition: Partition) -> WindowSpec:
        if symbol not in tuple(a.symbol for a in self.assets) or horizon not in self.horizons:
            raise ValueError("SESSION_NOT_IN_FROZEN_MANIFEST")
        selected = tuple(w for w in self.windows if w.partition is partition)
        if len(selected) != 1:
            raise ValueError("UNBOUNDED_OR_AMBIGUOUS_SESSION")
        return selected[0]

    @property
    def planned_sessions(self) -> int:
        return len(self.assets) * len(self.horizons) * len(self.windows)


# FROZEN IN CODE BEFORE LIVE. 2 chronological nonoverlapping closed UTC
# observations, deliberately sparse to avoid claiming statistical confidence.
# 3 assets × 2 horizons × 2 windows = 12 separately budgeted sessions, NOT
# 12 independent periods/volatility regimes or 12 prospective trades.
MANIFEST = StudyManifest(
    version=PROTOCOL_VERSION,
    provider_source="BINANCE:SPOT:PUBLIC_KLINES",
    assets=(
        AssetSpec("BTCUSDT", "MAJOR_REFERENCE"),
        AssetSpec("ETHUSDT", "ALT_LARGE_REFERENCE"),
        AssetSpec("ADAUSDT", "ALT_LIQUIDITY_UNVERIFIED"),
    ),
    horizons=EXPECTED_HORIZONS,
    directions=EXPECTED_DIRECTIONS,
    windows=(
        WindowSpec(Partition.DEVELOPMENT,
                   datetime.fromisoformat("2026-10-14T08:00:00+00:00"), "DEV_UTC_20261014"),
        WindowSpec(Partition.HOLDOUT,
                   datetime.fromisoformat("2026-10-21T08:00:00+00:00"), "HOLD_UTC_20261021"),
    ),
    metric_version="03B2_DESCRIPTIVE_ALTERNATIVES_V1_UNAPPROVED",
    candidate_formulas=(
        "directional_parent_close_location_fraction",
        "signed_body_fraction_plus_adverse_wick_fraction",
        "signed_child_net_over_body_path",
        "signed_child_net_over_gap_aware_path",
        "first_vs_second_half_quote_and_base_volume_share",
        "directional_child_quote_and_base_volume_share",
    ),
    baseline_formulas=("signed_parent_open_to_close_fraction", "parent_base_volume",
                       "parent_quote_volume"),
    transport_attempt_budget=8,
    ingestion_semantics=("One asset, one horizon, one named fixed historical window per "
                         "run; present-time receipt, explicit exchange inclusive close and "
                         "strict 03A same-source zero-delta comparison"),
    retrospective_assumption=RETROSPECTIVE_EVIDENCE,
    missingness_policy=("FAIL_CLOSED on missing/duplicate/stale/nonaligned OHLCV; "
                        "UNKNOWN historical eligibility, source publication and "
                        "fees/slippage; no imputation, no thresholds"),
    evaluation_policy=("development and strictly later holdout summarized independently; "
                       "NO holdout-based tuning/selection, NO forward outcomes, "
                       "INSUFFICIENT_EVIDENCE for prediction or adoption"),
)
