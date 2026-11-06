"""Tests for Phq9SerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.phq9_serial_delta_panel import (
    Phq9SerialDeltaFactors,
    Phq9SerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = Phq9SerialDeltaPanel().check(Phq9SerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = {
        "anhedonia_worsening": 1,
        "mood_worsening": 1,
        "sleep_worsening": 1,
        "energy_worsening": 1,
        "appetite_worsening": 1,
        "self_worth_worsening": 1,
    }
    panel = Phq9SerialDeltaPanel()
    findings = panel.check(Phq9SerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        Phq9SerialDeltaPanel().check(Phq9SerialDeltaFactors(anhedonia_worsening=2))
