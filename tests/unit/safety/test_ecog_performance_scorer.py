"""Tests for EcogPerformanceScorer."""

from __future__ import annotations

import pytest

from medagent.safety.ecog_performance_scorer import (
    EcogPerformanceFactors,
    EcogPerformanceScorer,
)


def test_low() -> None:
    """Low band."""

    findings = EcogPerformanceScorer().check(EcogPerformanceFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = EcogPerformanceScorer().check(
        EcogPerformanceFactors(
            restricted_activity=1,
            ambulatory_capable=1,
            limited_self_care=1,
            disabled=1,
            bedridden=1,
            hospitalized=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        EcogPerformanceScorer().check(EcogPerformanceFactors(restricted_activity=2))
