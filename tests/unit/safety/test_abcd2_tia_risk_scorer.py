"""Unit tests for Abcd2TiaRiskScorer."""

from __future__ import annotations

from medagent.safety.abcd2_tia_risk_scorer import (
    Abcd2TiaFactors,
    Abcd2TiaRiskScorer,
)


def test_low_risk() -> None:
    """No factors is low_risk."""

    findings = Abcd2TiaRiskScorer().check(Abcd2TiaFactors())
    assert findings[0].band == "low_risk"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_moderate_risk() -> None:
    """Mid score is moderate_risk."""

    findings = Abcd2TiaRiskScorer().check(Abcd2TiaFactors(age_ge_60=1, bp_ge_140_90=1))
    assert findings[0].band == "moderate_risk"


def test_high_risk() -> None:
    """High score is high_risk."""

    findings = Abcd2TiaRiskScorer().check(
        Abcd2TiaFactors(
            age_ge_60=1,
            bp_ge_140_90=1,
            unilateral_weakness=1,
            diabetes=1,
        )
    )
    assert findings[0].band == "high_risk"
