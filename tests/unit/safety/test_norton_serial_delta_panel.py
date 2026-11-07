"""Tests for NortonSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.norton_serial_delta_panel import (
    NortonSerialDeltaFactors,
    NortonSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = NortonSerialDeltaPanel().check(NortonSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = {
        "physical_condition_worsening": 1,
        "mental_condition_worsening": 1,
        "activity_worsening": 1,
        "mobility_worsening": 1,
        "incontinence_worsening": 1,
        "nutrition_worsening": 1,
    }
    panel = NortonSerialDeltaPanel()
    findings = panel.check(NortonSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        NortonSerialDeltaPanel().check(NortonSerialDeltaFactors(physical_condition_worsening=2))
