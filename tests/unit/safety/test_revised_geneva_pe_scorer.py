"""Unit tests for RevisedGenevaPeScorer."""

from __future__ import annotations

from medagent.safety.revised_geneva_pe_scorer import (
    RevisedGenevaPeFactors,
    RevisedGenevaPeScorer,
)


def test_low_probability() -> None:
    """No factors is low_probability."""

    findings = RevisedGenevaPeScorer().check(RevisedGenevaPeFactors())
    assert findings[0].band == "low_probability"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_intermediate_probability() -> None:
    """Mid score is intermediate_probability."""

    findings = RevisedGenevaPeScorer().check(RevisedGenevaPeFactors(age_gt_65=1, prior_dvt_pe=1))
    assert findings[0].band == "intermediate_probability"


def test_high_probability() -> None:
    """High score is high_probability."""

    findings = RevisedGenevaPeScorer().check(
        RevisedGenevaPeFactors(
            age_gt_65=1,
            prior_dvt_pe=1,
            surgery_or_fracture_1mo=1,
            hemoptysis=1,
        )
    )
    assert findings[0].band == "high_probability"
