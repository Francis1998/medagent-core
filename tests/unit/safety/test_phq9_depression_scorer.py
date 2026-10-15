"""Tests for Phq9DepressionScorer."""

from __future__ import annotations

import pytest

from medagent.safety.phq9_depression_scorer import (
    Phq9DepressionFactors,
    Phq9DepressionScorer,
)


def test_low() -> None:
    """Low band."""

    findings = Phq9DepressionScorer().check(Phq9DepressionFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = Phq9DepressionScorer().check(
        Phq9DepressionFactors(
            interest_ok=1,
            mood_ok=1,
            sleep_ok=1,
            energy_ok=1,
            appetite_ok=1,
            guilt_ok=1,
            concentration_ok=1,
            motor_ok=1,
            suicidality_ok=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        Phq9DepressionScorer().check(Phq9DepressionFactors(interest_ok=2))
