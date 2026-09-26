"""Unit tests for PaduaVteRiskScorer."""

from __future__ import annotations

from medagent.safety.padua_vte_risk_scorer import PaduaVteFactors, PaduaVteRiskScorer


def test_low_band() -> None:
    """No factors is low."""

    findings = PaduaVteRiskScorer().check(PaduaVteFactors())
    assert findings[0].band == "low"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_moderate_band() -> None:
    """Score 3 is moderate."""

    findings = PaduaVteRiskScorer().check(PaduaVteFactors(active_cancer=1))
    assert findings[0].band == "moderate"
    assert findings[0].score == 3


def test_high_band() -> None:
    """Score >= 4 is high."""

    findings = PaduaVteRiskScorer().check(PaduaVteFactors(active_cancer=1, age_ge_70=1))
    assert findings[0].band == "high"
    assert findings[0].score == 4
