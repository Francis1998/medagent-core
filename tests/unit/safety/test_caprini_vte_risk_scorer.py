"""Unit tests for CapriniVteRiskScorer."""

from __future__ import annotations

import pytest

from medagent.safety.caprini_vte_risk_scorer import CapriniVteFactors, CapriniVteRiskScorer


def test_default_band() -> None:
    """Default factors yield low advisory band."""

    findings = CapriniVteRiskScorer().check(CapriniVteFactors())
    assert findings[0].band == "low"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_high_band() -> None:
    """Weighted score >= 5 yields high band."""

    findings = CapriniVteRiskScorer().check(CapriniVteFactors(age_ge_75=1, major_surgery=1))
    assert findings[0].band == "high"
    assert findings[0].score == 5


def test_invalid_factor_raises() -> None:
    """Non-binary factor raises ValueError."""

    with pytest.raises(ValueError, match="prior_vte"):
        CapriniVteRiskScorer().check(CapriniVteFactors(prior_vte=2))
