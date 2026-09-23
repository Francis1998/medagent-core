"""Unit tests for HeartScoreAcsScorer."""

from __future__ import annotations

import pytest

from medagent.models import Severity
from medagent.safety.heart_score_acs_scorer import HeartScoreAcsScorer, HeartScoreFactors


def test_low_band() -> None:
    findings = HeartScoreAcsScorer().check(HeartScoreFactors())
    assert findings[0].band == "low"
    assert findings[0].severity == Severity.LOW
    assert findings[0].rationale


def test_high_band() -> None:
    findings = HeartScoreAcsScorer().check(
        HeartScoreFactors(
            history_points=2,
            ecg_points=2,
            age_points=2,
            risk_factors_points=2,
            troponin_points=2,
        )
    )
    assert findings[0].score == 10
    assert findings[0].band == "high"
    assert findings[0].severity == Severity.HIGH


def test_invalid() -> None:
    with pytest.raises(ValueError, match="history_points"):
        HeartScoreAcsScorer().check(HeartScoreFactors(history_points=3))
