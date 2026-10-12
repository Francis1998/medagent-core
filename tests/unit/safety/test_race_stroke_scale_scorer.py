"""Unit tests for RaceStrokeScaleScorer."""

from __future__ import annotations

import pytest

from medagent.safety.race_stroke_scale_scorer import (
    RaceStrokeScaleFactors,
    RaceStrokeScaleScorer,
)


def test_low() -> None:
    """Low band."""

    findings = RaceStrokeScaleScorer().check(RaceStrokeScaleFactors())
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = RaceStrokeScaleScorer().check(
        RaceStrokeScaleFactors(facial_ok=1, arm_ok=1, speech_ok=1)
    )
    assert findings[0].band == "high"


def test_invalid_raises() -> None:
    """Invalid factor raises ValueError."""

    with pytest.raises(ValueError):
        RaceStrokeScaleScorer().check(RaceStrokeScaleFactors(facial_ok=2))
