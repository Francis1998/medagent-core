"""Unit tests for MeldNaScorer."""

from __future__ import annotations

import pytest

from medagent.safety.meld_na_scorer import MeldNaFactors, MeldNaScorer


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = MeldNaScorer().check(MeldNaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_elevated_band() -> None:
    """Multiple factors elevate band."""

    findings = MeldNaScorer().check(
        MeldNaFactors(
            bilirubin_ge_2=1, inr_ge_1_5=1, creatinine_ge_1_5=1, sodium_lt_135=1, dialysis=1
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        MeldNaScorer().check(MeldNaFactors(bilirubin_ge_2=2))
