"""Unit tests for SirsCriteriaScorer."""

from __future__ import annotations

import pytest

from medagent.safety.sirs_criteria_scorer import SirsCriteriaFactors, SirsCriteriaScorer


def test_low_band() -> None:
    """Empty factors yield low band."""

    findings = SirsCriteriaScorer().check(SirsCriteriaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_intermediate_band() -> None:
    """Two positive factors yield intermediate band."""

    findings = SirsCriteriaScorer().check(
        SirsCriteriaFactors(
            temp_ok=1,
            hr_ok=1,
        )
    )
    assert findings[0].band == "intermediate"
    assert findings[0].score == 2


def test_invalid_factor_raises() -> None:
    """Non-binary factor raises ValueError."""

    with pytest.raises(ValueError, match="temp_ok"):
        SirsCriteriaScorer().check(SirsCriteriaFactors(temp_ok=2))
