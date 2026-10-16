"""Tests for BradenPressureScorer."""

from __future__ import annotations

import pytest

from medagent.safety.braden_pressure_scorer import (
    BradenPressureFactors,
    BradenPressureScorer,
)


def test_low() -> None:
    """Low band."""

    findings = BradenPressureScorer().check(BradenPressureFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = BradenPressureScorer().check(
        BradenPressureFactors(
            sensory_ok=1,
            moisture_ok=1,
            activity_ok=1,
            mobility_ok=1,
            nutrition_ok=1,
            friction_ok=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        BradenPressureScorer().check(BradenPressureFactors(sensory_ok=2))
