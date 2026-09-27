"""Unit tests for WellsDvtProbabilityScorer."""

from __future__ import annotations

from medagent.safety.wells_dvt_probability_scorer import WellsDvtFactors, WellsDvtProbabilityScorer


def test_low_band() -> None:
    """No factors is low."""

    findings = WellsDvtProbabilityScorer().check(WellsDvtFactors())
    assert findings[0].band == "low"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_moderate_band() -> None:
    """Score 1-2 is moderate."""

    findings = WellsDvtProbabilityScorer().check(WellsDvtFactors(active_cancer=1))
    assert findings[0].band == "moderate"
    assert findings[0].score == 1


def test_high_band() -> None:
    """Score >= 3 is high."""

    findings = WellsDvtProbabilityScorer().check(
        WellsDvtFactors(active_cancer=1, entire_leg_swollen=1, calf_swelling_3cm=1)
    )
    assert findings[0].band == "high"
    assert findings[0].score == 3
