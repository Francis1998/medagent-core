"""Unit tests for DukeEndocarditisCriteriaScorer."""

from __future__ import annotations

import pytest

from medagent.safety.duke_endocarditis_criteria_scorer import (
    DukeEndocarditisCriteriaFactors,
    DukeEndocarditisCriteriaScorer,
)


def test_low_band() -> None:
    """Empty factors yield low band."""

    findings = DukeEndocarditisCriteriaScorer().check(DukeEndocarditisCriteriaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_intermediate_band() -> None:
    """Two positive factors yield intermediate band."""

    findings = DukeEndocarditisCriteriaScorer().check(
        DukeEndocarditisCriteriaFactors(
            major_echo_ok=1,
            major_micro_ok=1,
        )
    )
    assert findings[0].band == "intermediate"
    assert findings[0].score == 2


def test_invalid_factor_raises() -> None:
    """Non-binary factor raises ValueError."""

    with pytest.raises(ValueError, match="major_echo_ok"):
        DukeEndocarditisCriteriaScorer().check(DukeEndocarditisCriteriaFactors(major_echo_ok=2))
