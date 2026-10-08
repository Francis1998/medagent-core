"""Unit tests for LightCriteriaScorer."""

from __future__ import annotations

import pytest

from medagent.safety.light_criteria_scorer import LightCriteriaFactors, LightCriteriaScorer


def test_low_band() -> None:
    """Empty factors yield low band."""

    findings = LightCriteriaScorer().check(LightCriteriaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_intermediate_band() -> None:
    """Two positive factors yield intermediate band."""

    findings = LightCriteriaScorer().check(
        LightCriteriaFactors(
            protein_ratio_gt_05=1,
            ldh_ratio_gt_06=1,
        )
    )
    assert findings[0].band == "intermediate"
    assert findings[0].score == 2


def test_invalid_factor_raises() -> None:
    """Non-binary factor raises ValueError."""

    with pytest.raises(ValueError, match="protein_ratio_gt_05"):
        LightCriteriaScorer().check(LightCriteriaFactors(protein_ratio_gt_05=2))
