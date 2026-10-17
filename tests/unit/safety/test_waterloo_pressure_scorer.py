"""Tests for WaterlooPressureScorer."""

from __future__ import annotations

import pytest

from medagent.safety.waterloo_pressure_scorer import (
    WaterlooPressureFactors,
    WaterlooPressureScorer,
)


def test_low() -> None:
    """Low band."""

    findings = WaterlooPressureScorer().check(WaterlooPressureFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = WaterlooPressureScorer().check(
        WaterlooPressureFactors(
            build_risk=1,
            skin_risk=1,
            continence_risk=1,
            mobility_risk=1,
            appetite_risk=1,
            special_risk=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        WaterlooPressureScorer().check(WaterlooPressureFactors(build_risk=2))
