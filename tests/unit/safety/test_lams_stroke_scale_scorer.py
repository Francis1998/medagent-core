"""Unit tests for LamsStrokeScaleScorer."""

from __future__ import annotations

import pytest

from medagent.safety.lams_stroke_scale_scorer import (
    LamsStrokeScaleFactors,
    LamsStrokeScaleScorer,
)


def test_low() -> None:
    """Low band."""

    findings = LamsStrokeScaleScorer().check(LamsStrokeScaleFactors())
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = LamsStrokeScaleScorer().check(LamsStrokeScaleFactors(face_ok=1, arm_ok=1, grip_ok=1))
    assert findings[0].band == "high"


def test_invalid_raises() -> None:
    """Invalid factor raises ValueError."""

    with pytest.raises(ValueError):
        LamsStrokeScaleScorer().check(LamsStrokeScaleFactors(face_ok=2))
