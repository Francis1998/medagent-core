"""Unit tests for NihssStrokeScorer."""

from __future__ import annotations

from medagent.safety.nihss_stroke_scorer import NihssFactors, NihssStrokeScorer


def test_mild_band() -> None:
    """Low NIHSS is mild."""

    findings = NihssStrokeScorer().check(NihssFactors())
    assert findings[0].band == "mild"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_moderate_band() -> None:
    """Mid NIHSS is moderate."""

    findings = NihssStrokeScorer().check(
        NihssFactors(loc_score=2, motor_arm_score=2, motor_leg_score=2)
    )
    assert findings[0].band == "moderate"
    assert findings[0].score == 6


def test_severe_band() -> None:
    """High NIHSS is severe."""

    findings = NihssStrokeScorer().check(
        NihssFactors(
            loc_score=3,
            motor_arm_score=4,
            motor_leg_score=4,
            language_score=3,
            neglect_score=2,
        )
    )
    assert findings[0].band == "severe"
    assert findings[0].score == 16
