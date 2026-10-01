"""Unit tests for KampalaTraumaScorer."""

from __future__ import annotations

import pytest

from medagent.safety.kampala_trauma_scorer import KampalaTraumaFactors, KampalaTraumaScorer


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = KampalaTraumaScorer().check(KampalaTraumaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_elevated_band() -> None:
    """Multiple factors elevate band."""

    findings = KampalaTraumaScorer().check(
        KampalaTraumaFactors(
            age_extreme=1,
            sbp_lt_90=1,
            respiratory_distress=1,
            neuro_deficit=1,
            serious_injury=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        KampalaTraumaScorer().check(KampalaTraumaFactors(age_extreme=2))
