"""Unit tests for HasBledBleedRiskScorer."""

from __future__ import annotations

from medagent.models import Severity
from medagent.safety.has_bled_bleed_risk_scorer import HasBledBleedRiskScorer, HasBledFactors


def test_low_score() -> None:
    findings = HasBledBleedRiskScorer().check(HasBledFactors(elderly=True))
    assert len(findings) == 1
    assert findings[0].score == 1
    assert findings[0].band == "low"
    assert findings[0].severity == Severity.LOW


def test_high_score() -> None:
    findings = HasBledBleedRiskScorer().check(
        HasBledFactors(
            hypertension=True,
            abnormal_renal=True,
            stroke_history=True,
            elderly=True,
        )
    )
    assert findings[0].score == 4
    assert findings[0].band == "high"
    assert findings[0].severity == Severity.HIGH
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_moderate_score() -> None:
    findings = HasBledBleedRiskScorer().check(HasBledFactors(hypertension=True, drugs=True))
    assert findings[0].score == 2
    assert findings[0].band == "moderate"
