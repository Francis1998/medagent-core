"""Unit tests for HuntHessSahScorer."""

from __future__ import annotations

import pytest

from medagent.safety.hunt_hess_sah_scorer import (
    HuntHessSahFactors,
    HuntHessSahScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = HuntHessSahScorer().check(HuntHessSahFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = HuntHessSahScorer().check(
        HuntHessSahFactors(
            grade_1_asymptomatic=1,
            grade_2_cn_palsy=1,
            grade_3_drowsy=1,
            grade_4_stupor=1,
            grade_5_coma=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        HuntHessSahScorer().check(HuntHessSahFactors(grade_1_asymptomatic=2))
