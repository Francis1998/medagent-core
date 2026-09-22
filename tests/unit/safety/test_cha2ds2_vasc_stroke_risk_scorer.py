"""Unit tests for Cha2ds2VascStrokeRiskScorer."""

from __future__ import annotations

from medagent.models import Severity
from medagent.safety.cha2ds2_vasc_stroke_risk_scorer import (
    Cha2ds2VascFactors,
    Cha2ds2VascStrokeRiskScorer,
)


def test_low() -> None:
    findings = Cha2ds2VascStrokeRiskScorer().check(Cha2ds2VascFactors())
    assert findings[0].score == 0
    assert findings[0].band == "low"


def test_high_age_stroke() -> None:
    findings = Cha2ds2VascStrokeRiskScorer().check(
        Cha2ds2VascFactors(age_ge_75=True, stroke_tia_thromboembolism=True)
    )
    assert findings[0].score == 4
    assert findings[0].band == "high"
    assert findings[0].severity == Severity.HIGH


def test_moderate() -> None:
    findings = Cha2ds2VascStrokeRiskScorer().check(Cha2ds2VascFactors(female_sex=True))
    assert findings[0].score == 1
    assert findings[0].band == "moderate"
