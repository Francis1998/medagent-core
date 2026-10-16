"""Tests for MorseFallScorer."""

from __future__ import annotations

import pytest

from medagent.safety.morse_fall_scorer import (
    MorseFallFactors,
    MorseFallScorer,
)


def test_low() -> None:
    """Low band."""

    findings = MorseFallScorer().check(MorseFallFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = MorseFallScorer().check(
        MorseFallFactors(
            history_fall=1,
            secondary_diagnosis=1,
            ambulatory_aid=1,
            iv_therapy=1,
            gait_impaired=1,
            mental_status=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        MorseFallScorer().check(MorseFallFactors(history_fall=2))
