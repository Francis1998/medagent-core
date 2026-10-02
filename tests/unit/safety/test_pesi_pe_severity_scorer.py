"""Unit tests for PesiPeSeverityScorer."""

from __future__ import annotations

import pytest

from medagent.safety.pesi_pe_severity_scorer import PesiPeSeverityFactors, PesiPeSeverityScorer


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = PesiPeSeverityScorer().check(PesiPeSeverityFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_elevated_band() -> None:
    """Multiple factors elevate band."""

    findings = PesiPeSeverityScorer().check(
        PesiPeSeverityFactors(
            age_gt_65=1,
            male_sex=1,
            cancer=1,
            heart_failure=1,
            chronic_lung=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        PesiPeSeverityScorer().check(PesiPeSeverityFactors(age_gt_65=2))
