"""Unit tests for BodeCopdScorer."""

from __future__ import annotations

import pytest

from medagent.safety.bode_copd_scorer import BodeCopdFactors, BodeCopdScorer


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = BodeCopdScorer().check(BodeCopdFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_elevated_band() -> None:
    """Multiple factors elevate band."""

    findings = BodeCopdScorer().check(
        BodeCopdFactors(
            bmi_le_21=1,
            fev1_lt_65=1,
            mmrc_dyspnea_ge_2=1,
            six_min_walk_lt_350=1,
            exacerbation_history=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        BodeCopdScorer().check(BodeCopdFactors(bmi_le_21=2))
