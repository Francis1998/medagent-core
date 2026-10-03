"""Unit tests for GlasgowBlatchfordScorer."""

from __future__ import annotations

import pytest

from medagent.safety.glasgow_blatchford_scorer import (
    GlasgowBlatchfordFactors,
    GlasgowBlatchfordScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = GlasgowBlatchfordScorer().check(GlasgowBlatchfordFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = GlasgowBlatchfordScorer().check(
        GlasgowBlatchfordFactors(
            bun_ge_6_5=1,
            bun_ge_10_0=1,
            bun_ge_25_0=1,
            hb_lt_13_male_or_12_female=1,
            hb_lt_10=1,
            sbp_90_109=1,
            sbp_lt_90=1,
            hr_ge_100=1,
            melena=1,
            syncope=1,
            liver_disease=1,
            heart_failure=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        GlasgowBlatchfordScorer().check(GlasgowBlatchfordFactors(bun_ge_6_5=2))
