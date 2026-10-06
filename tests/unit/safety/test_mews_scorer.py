"""Unit tests for MewsScorer."""

from __future__ import annotations

import pytest

from medagent.safety.mews_scorer import (
    MewsFactors,
    MewsScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = MewsScorer().check(MewsFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = MewsScorer().check(
        MewsFactors(
            rr_abnormal=1,
            hr_abnormal=1,
            sbp_abnormal=1,
            temp_abnormal=1,
            avpu_not_alert=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        MewsScorer().check(MewsFactors(rr_abnormal=2))
