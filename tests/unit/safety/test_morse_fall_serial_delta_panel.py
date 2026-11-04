"""Tests for MorseFallSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.morse_fall_serial_delta_panel import (
    MorseFallSerialDeltaFactors,
    MorseFallSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = MorseFallSerialDeltaPanel().check(MorseFallSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_morse_rise",
            "history_of_falling",
            "secondary_diagnosis_new",
            "ambulatory_aid_change",
            "gait_worsening",
            "mental_status_decline",
        ],
        1,
    )
    panel = MorseFallSerialDeltaPanel()
    findings = panel.check(MorseFallSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        MorseFallSerialDeltaPanel().check(MorseFallSerialDeltaFactors(prior_morse_rise=2))
