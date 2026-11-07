"""Tests for FlaccSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.flacc_serial_delta_panel import (
    FlaccSerialDeltaFactors,
    FlaccSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = FlaccSerialDeltaPanel().check(FlaccSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = {
        "face_worsening": 1,
        "legs_worsening": 1,
        "activity_worsening": 1,
        "cry_worsening": 1,
        "consolability_worsening": 1,
        "caregiver_concern": 1,
    }
    panel = FlaccSerialDeltaPanel()
    findings = panel.check(FlaccSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        FlaccSerialDeltaPanel().check(FlaccSerialDeltaFactors(face_worsening=2))
