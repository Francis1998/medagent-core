"""Unit tests for KarnofskyPerformanceScorer."""

from __future__ import annotations

import pytest

from medagent.safety.karnofsky_performance_scorer import (
    KarnofskyPerformanceFactors,
    KarnofskyPerformanceScorer,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = KarnofskyPerformanceScorer().check(KarnofskyPerformanceFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = KarnofskyPerformanceScorer().check(
        KarnofskyPerformanceFactors(normal_activity=1, minor_symptoms=1)
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = KarnofskyPerformanceScorer().check(
        KarnofskyPerformanceFactors(
            normal_activity=1,
            minor_symptoms=1,
            cares_for_self=1,
            needs_occasional_assistance=1,
            disabled=1,
            hospital_level_care=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        KarnofskyPerformanceScorer().check(KarnofskyPerformanceFactors(normal_activity=4))
