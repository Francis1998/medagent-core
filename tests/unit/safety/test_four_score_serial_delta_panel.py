"""Tests for FourScoreSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.four_score_serial_delta_panel import (
    FourScoreSerialDeltaFactors,
    FourScoreSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = FourScoreSerialDeltaPanel().check(FourScoreSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_four_elevated",
            "eye_response_drop",
            "motor_response_drop",
            "brainstem_worsening",
            "respiration_pattern_worsen",
            "new_intubation",
        ],
        1,
    )
    panel = FourScoreSerialDeltaPanel()
    findings = panel.check(FourScoreSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        FourScoreSerialDeltaPanel().check(FourScoreSerialDeltaFactors(prior_four_elevated=2))
