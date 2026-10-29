from __future__ import annotations

import pytest

from zs_smart_gate.stage03c_score_contracts import (
    WEIGHTS, assert_delivery_blocked, detection_event_key, score_v2,
)


@pytest.mark.parametrize("horizon", ["INTRADAY", "SWING"])
def test_weight_tables_sum_to_100(horizon):
    assert sum(WEIGHTS[horizon].values()) == 100


@pytest.mark.parametrize("horizon", ["INTRADAY", "SWING"])
def test_missing_group_means_no_partial_score(horizon):
    result = score_v2(horizon, {})
    assert result.status == "SCORE_UNAVAILABLE"
    assert result.score is None
    assert result.contributions == {}
    assert result.as_dict()["publishable"] is False
    assert result.as_dict()["qualification_status"] == "NOT_EVALUATED"


@pytest.mark.parametrize("horizon", ["INTRADAY", "SWING"])
def test_complete_zero_and_one_features_are_bounded(horizon):
    weights = WEIGHTS[horizon]
    zero = score_v2(horizon, {key: 0 for key in weights})
    full = score_v2(horizon, {key: 1 for key in weights})
    assert zero.score == "0.00"
    assert full.score == "100.00"
    assert sum(map(float, full.contributions.values())) == 100.0
    assert full.score_kind == "RESEARCH_DISCOVERY_STRENGTH_NOT_PROBABILITY"


@pytest.mark.parametrize("bad", [-0.01, 1.01, float("nan"), float("inf"), True, "oops"])
def test_invalid_feature_values_rejected(bad):
    with pytest.raises(ValueError):
        score_v2("INTRADAY", {key: bad for key in WEIGHTS["INTRADAY"]})


def test_extra_group_rejected_to_prevent_silent_weight_drift():
    values = {key: 0.5 for key in WEIGHTS["SWING"]}
    values["rsi"] = 0.9
    with pytest.raises(ValueError, match="UNEXPECTED_FEATURE_GROUPS"):
        score_v2("SWING", values)


def test_event_identity_is_deterministic_and_sensitive_to_event_dimensions():
    args = dict(rule_version="v1", market="BINANCE:SPOT", symbol="BTCUSDT",
                direction="UP", horizon="INTRADAY", setup_type="CONTINUATION",
                decision_close_utc="2026-10-30T12:30:00Z")
    assert detection_event_key(**args) == detection_event_key(**args)
    assert detection_event_key(**args) != detection_event_key(**{**args, "direction": "DOWN"})
    assert detection_event_key(**args) != detection_event_key(**{**args, "symbol": "ETHUSDT"})


def test_delivery_is_fail_closed_even_with_numeric_research_score():
    result = score_v2("INTRADAY", {key: 0.5 for key in WEIGHTS["INTRADAY"]})
    with pytest.raises(PermissionError, match="PHASE_03C_RESEARCH_ONLY"):
        assert_delivery_blocked(result)
