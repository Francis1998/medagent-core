"""Unit tests for FeverPainScorer."""

from __future__ import annotations

import pytest

from medagent.safety.feverpain_scorer import FeverPainFactors, FeverPainScorer


def test_low_band() -> None:
    """Empty factors yield low band."""

    findings = FeverPainScorer().check(FeverPainFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_intermediate_band() -> None:
    """Two positive factors yield intermediate band."""

    findings = FeverPainScorer().check(
        FeverPainFactors(
            fever_in_past_24h=1,
            purulence=1,
        )
    )
    assert findings[0].band == "intermediate"
    assert findings[0].score == 2


def test_invalid_factor_raises() -> None:
    """Non-binary factor raises ValueError."""

    with pytest.raises(ValueError, match="fever_in_past_24h"):
        FeverPainScorer().check(FeverPainFactors(fever_in_past_24h=2))
