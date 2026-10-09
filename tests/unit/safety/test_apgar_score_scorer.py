"""Unit tests for ApgarScoreScorer."""

from __future__ import annotations

import pytest

from medagent.safety.apgar_score_scorer import ApgarScoreFactors, ApgarScoreScorer


def test_low_band() -> None:
    """Empty factors yield low band."""

    findings = ApgarScoreScorer().check(ApgarScoreFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_intermediate_band() -> None:
    """Two positive factors yield intermediate band."""

    findings = ApgarScoreScorer().check(
        ApgarScoreFactors(
            appearance_ok=1,
            pulse_ok=1,
        )
    )
    assert findings[0].band == "intermediate"
    assert findings[0].score == 2


def test_invalid_factor_raises() -> None:
    """Non-binary factor raises ValueError."""

    with pytest.raises(ValueError, match="appearance_ok"):
        ApgarScoreScorer().check(ApgarScoreFactors(appearance_ok=2))
