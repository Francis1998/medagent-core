"""Unit tests for TimiUaNstemiScorer."""

from __future__ import annotations

from medagent.safety.timi_ua_nstemi_scorer import TimiUaNstemiFactors, TimiUaNstemiScorer


def test_low_band() -> None:
    """Low TIMI is low."""

    findings = TimiUaNstemiScorer().check(TimiUaNstemiFactors())
    assert findings[0].band == "low"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_intermediate_band() -> None:
    """Mid TIMI is intermediate."""

    findings = TimiUaNstemiScorer().check(
        TimiUaNstemiFactors(age_ge_65=1, known_cad=1, st_deviation=1)
    )
    assert findings[0].band == "intermediate"
    assert findings[0].score == 3


def test_high_band() -> None:
    """High TIMI is high."""

    findings = TimiUaNstemiScorer().check(
        TimiUaNstemiFactors(
            age_ge_65=1,
            ge_3_cad_risk_factors=1,
            known_cad=1,
            aspirin_last_7d=1,
            severe_angina=1,
        )
    )
    assert findings[0].band == "high"
    assert findings[0].score == 5
