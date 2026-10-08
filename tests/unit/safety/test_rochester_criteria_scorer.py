"""Unit tests for RochesterCriteriaScorer."""

from __future__ import annotations

import pytest

from medagent.safety.rochester_criteria_scorer import (
    RochesterCriteriaFactors,
    RochesterCriteriaScorer,
)


def test_low_band() -> None:
    """Empty factors yield low band."""

    findings = RochesterCriteriaScorer().check(RochesterCriteriaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_intermediate_band() -> None:
    """Two positive factors yield intermediate band."""

    findings = RochesterCriteriaScorer().check(
        RochesterCriteriaFactors(
            infant_age_le_60d=1,
            fever_ge_38c=1,
        )
    )
    assert findings[0].band == "intermediate"
    assert findings[0].score == 2


def test_invalid_factor_raises() -> None:
    """Non-binary factor raises ValueError."""

    with pytest.raises(ValueError, match="infant_age_le_60d"):
        RochesterCriteriaScorer().check(RochesterCriteriaFactors(infant_age_le_60d=2))
