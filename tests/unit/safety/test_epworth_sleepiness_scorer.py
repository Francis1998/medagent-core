"""Tests for EpworthSleepinessScorer."""

from __future__ import annotations

import pytest

from medagent.safety.epworth_sleepiness_scorer import (
    EpworthSleepinessFactors,
    EpworthSleepinessScorer,
)


def test_low() -> None:
    """Low band."""

    findings = EpworthSleepinessScorer().check(EpworthSleepinessFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = EpworthSleepinessScorer().check(
        EpworthSleepinessFactors(sitting_ok=1, watching_tv_ok=1, passenger_ok=1, lying_down_ok=1)
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        EpworthSleepinessScorer().check(EpworthSleepinessFactors(sitting_ok=2))
