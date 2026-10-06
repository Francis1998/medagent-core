"""Unit tests for FisherGradeScorer."""

from __future__ import annotations

import pytest

from medagent.safety.fisher_grade_scorer import (
    FisherGradeFactors,
    FisherGradeScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = FisherGradeScorer().check(FisherGradeFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = FisherGradeScorer().check(
        FisherGradeFactors(
            diffuse_blood=1,
            localized_clot=1,
            vertical_layer_ge_1mm=1,
            intraparenchymal_or_ivh=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        FisherGradeScorer().check(FisherGradeFactors(diffuse_blood=2))
