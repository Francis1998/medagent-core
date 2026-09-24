"""Unit tests for GcsNeurologicStatusScorer."""

from __future__ import annotations

import pytest

from medagent.safety.gcs_neurologic_status_scorer import (
    GcsNeurologicStatusFactors,
    GcsNeurologicStatusScorer,
)


def test_default_band() -> None:
    """Default factors yield expected advisory band."""

    findings = GcsNeurologicStatusScorer().check(GcsNeurologicStatusFactors())
    assert len(findings) == 1
    assert findings[0].band == "mild"
    assert findings[0].score == 15
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_elevated_band() -> None:
    """Elevated factors yield high/severe band."""

    findings = GcsNeurologicStatusScorer().check(
        GcsNeurologicStatusFactors(eye_points=1, verbal_points=1, motor_points=1)
    )
    assert findings[0].band == "severe"
    assert findings[0].score == 3


def test_invalid_eye_raises() -> None:
    """Out-of-range eye points raise ValueError."""

    with pytest.raises(ValueError, match="eye_points"):
        GcsNeurologicStatusScorer().check(GcsNeurologicStatusFactors(eye_points=0))
