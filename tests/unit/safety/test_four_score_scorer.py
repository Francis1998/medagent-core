"""Unit tests for FourScoreScorer."""

from __future__ import annotations

import pytest

from medagent.safety.four_score_scorer import (
    FourScoreFactors,
    FourScoreScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = FourScoreScorer().check(FourScoreFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = FourScoreScorer().check(
        FourScoreFactors(
            eye_response_ge_3=1,
            motor_response_ge_3=1,
            brainstem_reflex_ge_2=1,
            respiration_ge_2=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        FourScoreScorer().check(FourScoreFactors(eye_response_ge_3=2))
