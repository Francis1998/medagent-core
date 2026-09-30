"""Unit tests for RansonPancreatitisScorer."""

from __future__ import annotations

import pytest

from medagent.safety.ranson_pancreatitis_scorer import (
    RansonPancreatitisFactors,
    RansonPancreatitisScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = RansonPancreatitisScorer().check(RansonPancreatitisFactors())
    assert len(findings) == 1
    assert findings[0].band == "mild"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_elevated_band() -> None:
    """Multiple factors elevate band."""

    findings = RansonPancreatitisScorer().check(
        RansonPancreatitisFactors(
            age_gt_55=1, wbc_gt_16=1, glucose_gt_200=1, ldh_gt_350=1, ast_gt_250=1
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"mild", "moderate", "severe"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        RansonPancreatitisScorer().check(RansonPancreatitisFactors(age_gt_55=2))
