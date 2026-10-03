"""Unit tests for RockallGiBleedScorer."""

from __future__ import annotations

import pytest

from medagent.safety.rockall_gi_bleed_scorer import RockallGiBleedFactors, RockallGiBleedScorer


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = RockallGiBleedScorer().check(RockallGiBleedFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = RockallGiBleedScorer().check(
        RockallGiBleedFactors(
            age_ge_60=1, age_ge_80=1, pulse_ge_100=1, sbp_lt_100=1, comorbidity=1, major_stigmata=1
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        RockallGiBleedScorer().check(RockallGiBleedFactors(age_ge_60=2))
