"""Tests for Gad7SerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.gad7_serial_delta_panel import (
    Gad7SerialDeltaFactors,
    Gad7SerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = Gad7SerialDeltaPanel().check(Gad7SerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = {
        "nervous_worsening": 1,
        "control_worry_worsening": 1,
        "worry_breadth_worsening": 1,
        "relax_difficulty_worsening": 1,
        "restless_worsening": 1,
        "irritable_worsening": 1,
    }
    panel = Gad7SerialDeltaPanel()
    findings = panel.check(Gad7SerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        Gad7SerialDeltaPanel().check(Gad7SerialDeltaFactors(nervous_worsening=2))
