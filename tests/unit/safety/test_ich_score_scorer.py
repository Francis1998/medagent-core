"""Unit tests for IchScoreScorer."""

from __future__ import annotations

import pytest

from medagent.safety.ich_score_scorer import (
    IchScoreFactors,
    IchScoreScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = IchScoreScorer().check(IchScoreFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = IchScoreScorer().check(
        IchScoreFactors(
            gcs_le_4=1,
            ich_volume_ge_30=1,
            ivh_present=1,
            infratentorial=1,
            age_ge_80=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        IchScoreScorer().check(IchScoreFactors(gcs_le_4=2))
