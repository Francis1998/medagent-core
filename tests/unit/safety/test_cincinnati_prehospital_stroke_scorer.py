"""Tests for CincinnatiPrehospitalStrokeScorer."""

from __future__ import annotations

import pytest

from medagent.safety.cincinnati_prehospital_stroke_scorer import (
    CincinnatiPrehospitalStrokeFactors,
    CincinnatiPrehospitalStrokeScorer,
)


def test_low() -> None:
    """Low band."""

    findings = CincinnatiPrehospitalStrokeScorer().check(CincinnatiPrehospitalStrokeFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = CincinnatiPrehospitalStrokeScorer().check(
        CincinnatiPrehospitalStrokeFactors(
            facial_droop_ok=1,
            arm_drift_ok=1,
            speech_ok=1,
            onset_ok=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        CincinnatiPrehospitalStrokeScorer().check(
            CincinnatiPrehospitalStrokeFactors(facial_droop_ok=2)
        )
