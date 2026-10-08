"""Unit tests for JonesCriteriaScorer."""

from __future__ import annotations

import pytest

from medagent.safety.jones_criteria_scorer import JonesCriteriaFactors, JonesCriteriaScorer


def test_low_band() -> None:
    """Empty factors yield low band."""

    findings = JonesCriteriaScorer().check(JonesCriteriaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_intermediate_band() -> None:
    """Two positive factors yield intermediate band."""

    findings = JonesCriteriaScorer().check(
        JonesCriteriaFactors(
            carditis=1,
            polyarthritis=1,
        )
    )
    assert findings[0].band == "intermediate"
    assert findings[0].score == 2


def test_invalid_factor_raises() -> None:
    """Non-binary factor raises ValueError."""

    with pytest.raises(ValueError, match="carditis"):
        JonesCriteriaScorer().check(JonesCriteriaFactors(carditis=2))
