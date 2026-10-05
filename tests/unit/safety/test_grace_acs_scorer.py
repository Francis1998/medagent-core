"""Unit tests for GraceAcsScorer."""

from __future__ import annotations

import pytest

from medagent.safety.grace_acs_scorer import (
    GraceAcsFactors,
    GraceAcsScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = GraceAcsScorer().check(GraceAcsFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = GraceAcsScorer().check(
        GraceAcsFactors(
            age_ge_70=1,
            hr_ge_100=1,
            sbp_lt_100=1,
            killip_ge_ii=1,
            troponin_positive=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        GraceAcsScorer().check(GraceAcsFactors(age_ge_70=2))
