"""Unit tests for LrinecNecfascScorer."""

from __future__ import annotations

import pytest

from medagent.safety.lrinec_necfasc_scorer import LrinecNecfascFactors, LrinecNecfascScorer


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = LrinecNecfascScorer().check(LrinecNecfascFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_elevated_band() -> None:
    """Multiple factors elevate band."""

    findings = LrinecNecfascScorer().check(
        LrinecNecfascFactors(
            crp_ge_150=1, wbc_ge_15=1, hemoglobin_le_11=1, sodium_lt_135=1, creatinine_gt_1_6=1
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        LrinecNecfascScorer().check(LrinecNecfascFactors(crp_ge_150=2))
