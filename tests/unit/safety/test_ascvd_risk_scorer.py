"""Tests for AscvdRiskScorer."""

from __future__ import annotations

import pytest

from medagent.safety.ascvd_risk_scorer import (
    AscvdRiskFactors,
    AscvdRiskScorer,
)


def test_low() -> None:
    """Low band."""

    findings = AscvdRiskScorer().check(AscvdRiskFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = AscvdRiskScorer().check(
        AscvdRiskFactors(
            age_risk=1,
            cholesterol_risk=1,
            bp_risk=1,
            diabetes=1,
            smoker=1,
            treated_bp=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        AscvdRiskScorer().check(AscvdRiskFactors(age_risk=2))
