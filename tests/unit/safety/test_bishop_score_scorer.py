"""Unit tests for BishopScoreScorer."""

from __future__ import annotations

import pytest

from medagent.safety.bishop_score_scorer import BishopScoreFactors, BishopScoreScorer


def test_low_band() -> None:
    """Empty factors yield low band."""

    findings = BishopScoreScorer().check(BishopScoreFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_intermediate_band() -> None:
    """Two positive factors yield intermediate band."""

    findings = BishopScoreScorer().check(
        BishopScoreFactors(
            dilation_favorable=1,
            effacement_favorable=1,
        )
    )
    assert findings[0].band == "intermediate"
    assert findings[0].score == 2


def test_invalid_factor_raises() -> None:
    """Non-binary factor raises ValueError."""

    with pytest.raises(ValueError, match="dilation_favorable"):
        BishopScoreScorer().check(BishopScoreFactors(dilation_favorable=2))
