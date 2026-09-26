"""Unit tests for PsiPortPneumoniaScorer."""

from __future__ import annotations

from medagent.safety.psi_port_pneumonia_scorer import PsiPortFactors, PsiPortPneumoniaScorer


def test_low_band() -> None:
    """No factors is low."""

    findings = PsiPortPneumoniaScorer().check(PsiPortFactors())
    assert findings[0].band == "low"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_moderate_band() -> None:
    """Mid score is moderate."""

    findings = PsiPortPneumoniaScorer().check(PsiPortFactors(age_ge_70=1, nursing_home=1))
    assert findings[0].band == "moderate"
    assert findings[0].score == 4


def test_high_band() -> None:
    """High weighted score is high."""

    findings = PsiPortPneumoniaScorer().check(
        PsiPortFactors(
            age_ge_70=1,
            nursing_home=1,
            neoplastic=1,
            respiratory_rate_ge_30=1,
        )
    )
    assert findings[0].band == "high"
