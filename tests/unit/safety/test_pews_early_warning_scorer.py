"""Unit tests for PewsEarlyWarningScorer."""

from __future__ import annotations

import pytest

from medagent.safety.pews_early_warning_scorer import (
    PewsEarlyWarningFactors,
    PewsEarlyWarningScorer,
)


def test_low_band() -> None:
    """Empty factors yield low band."""

    findings = PewsEarlyWarningScorer().check(PewsEarlyWarningFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_intermediate_band() -> None:
    """Two positive factors yield intermediate band."""

    findings = PewsEarlyWarningScorer().check(
        PewsEarlyWarningFactors(
            behavior_ok=1,
            cardiovascular_ok=1,
        )
    )
    assert findings[0].band == "intermediate"
    assert findings[0].score == 2


def test_invalid_factor_raises() -> None:
    """Non-binary factor raises ValueError."""

    with pytest.raises(ValueError, match="behavior_ok"):
        PewsEarlyWarningScorer().check(PewsEarlyWarningFactors(behavior_ok=2))
