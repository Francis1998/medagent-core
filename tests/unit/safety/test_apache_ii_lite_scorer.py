"""Unit tests for ApacheIiLiteScorer."""

from __future__ import annotations

import pytest

from medagent.safety.apache_ii_lite_scorer import ApacheIiLiteFactors, ApacheIiLiteScorer


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = ApacheIiLiteScorer().check(ApacheIiLiteFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_elevated_band() -> None:
    """Multiple factors elevate band."""

    findings = ApacheIiLiteScorer().check(
        ApacheIiLiteFactors(
            temp_extreme=1,
            map_abnormal=1,
            hr_extreme=1,
            rr_extreme=1,
            oxygenation_low=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        ApacheIiLiteScorer().check(ApacheIiLiteFactors(temp_extreme=2))
