"""Unit tests for PecarnHeadTraumaScorer."""

from __future__ import annotations

import pytest

from medagent.safety.pecarn_head_trauma_scorer import (
    PecarnHeadTraumaFactors,
    PecarnHeadTraumaScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = PecarnHeadTraumaScorer().check(PecarnHeadTraumaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_elevated_band() -> None:
    """Multiple factors elevate band."""

    findings = PecarnHeadTraumaScorer().check(
        PecarnHeadTraumaFactors(
            altered_mental_status=1,
            skull_fracture_suspect=1,
            severe_mechanism=1,
            vomiting_or_headache=1,
            basilar_signs=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        PecarnHeadTraumaScorer().check(PecarnHeadTraumaFactors(altered_mental_status=2))
