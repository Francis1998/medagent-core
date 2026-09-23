"""Unit tests for Curb65PneumoniaScorer."""

from __future__ import annotations

from medagent.models import Severity
from medagent.safety.curb65_pneumonia_scorer import Curb65Factors, Curb65PneumoniaScorer


def test_low_band() -> None:
    findings = Curb65PneumoniaScorer().check(Curb65Factors())
    assert findings[0].band == "mild"
    assert findings[0].severity == Severity.LOW
    assert findings[0].rationale


def test_high_band() -> None:
    findings = Curb65PneumoniaScorer().check(
        Curb65Factors(
            confusion=True,
            urea_over_7=True,
            resp_rate_30_plus=True,
            low_blood_pressure=True,
            age_65_plus=True,
        )
    )
    assert findings[0].score == 5
    assert findings[0].band == "severe"
    assert findings[0].severity == Severity.HIGH


def test_moderate_band() -> None:
    findings = Curb65PneumoniaScorer().check(Curb65Factors(confusion=True, age_65_plus=True))
    assert findings[0].score == 2
    assert findings[0].band == "moderate"
