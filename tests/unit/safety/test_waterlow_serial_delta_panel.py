"""Tests for WaterlowSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.waterlow_serial_delta_panel import (
    WaterlowSerialDeltaFactors,
    WaterlowSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = WaterlowSerialDeltaPanel().check(WaterlowSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = {
        "build_weight_worsening": 1,
        "continence_worsening": 1,
        "skin_type_worsening": 1,
        "mobility_decline": 1,
        "sex_age_risk_rise": 1,
        "appetite_decline": 1,
    }
    panel = WaterlowSerialDeltaPanel()
    findings = panel.check(WaterlowSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        WaterlowSerialDeltaPanel().check(WaterlowSerialDeltaFactors(build_weight_worsening=2))
