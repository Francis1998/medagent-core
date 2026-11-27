"""Unit tests for News2EarlyWarningScorer."""

from __future__ import annotations

import pytest

from medagent.models import Severity
from medagent.safety.news2_early_warning_scorer import (
    News2EarlyWarningFactors,
    News2EarlyWarningScorer,
)


def test_default_band() -> None:
    """Default factors yield low advisory band."""

    findings = News2EarlyWarningScorer().check(News2EarlyWarningFactors())
    assert findings[0].band == "low"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_high_band() -> None:
    """Score >= 7 yields high band."""

    findings = News2EarlyWarningScorer().check(
        News2EarlyWarningFactors(
            respiration=3,
            oxygen_sat=2,
            heart_rate=2,
        )
    )
    assert findings[0].band == "high"
    assert findings[0].score == 7


def test_invalid_factor_raises() -> None:
    """Out-of-range factor raises ValueError."""

    with pytest.raises(ValueError, match="respiration"):
        News2EarlyWarningScorer().check(News2EarlyWarningFactors(respiration=4))


def test_single_parameter_red_score_is_low_medium() -> None:
    """RCP NEWS2 (2017): a 3 in any one parameter is low-medium risk even when the total is < 5."""
    findings = News2EarlyWarningScorer().check(News2EarlyWarningFactors(respiration=3))
    assert findings[0].score == 3
    assert findings[0].band == "low_medium"
    assert findings[0].severity == Severity.MODERATE


def test_aggregate_below_five_without_a_red_score_stays_low() -> None:
    findings = News2EarlyWarningScorer().check(
        News2EarlyWarningFactors(respiration=2, heart_rate=2)
    )
    assert findings[0].score == 4
    assert findings[0].band == "low"
