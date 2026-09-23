"""Unit tests for WellsPeProbabilityScorer."""

from __future__ import annotations

from medagent.models import Severity
from medagent.safety.wells_pe_probability_scorer import WellsPeFactors, WellsPeProbabilityScorer


def test_low_band() -> None:
    findings = WellsPeProbabilityScorer().check(WellsPeFactors())
    assert findings[0].band == "low"
    assert findings[0].severity == Severity.LOW
    assert findings[0].rationale


def test_high_band() -> None:
    findings = WellsPeProbabilityScorer().check(
        WellsPeFactors(
            clinical_dvt_signs=True,
            pe_most_likely=True,
            heart_rate_over_100=True,
        )
    )
    assert findings[0].score == 7.5
    assert findings[0].band == "high"
    assert findings[0].severity == Severity.HIGH


def test_moderate_band() -> None:
    findings = WellsPeProbabilityScorer().check(WellsPeFactors(hemoptysis=True, malignancy=True))
    assert findings[0].score == 2.0
    assert findings[0].band == "moderate"
