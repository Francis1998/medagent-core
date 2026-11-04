"""Tests for BradenSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.braden_serial_delta_panel import (
    BradenSerialDeltaFactors,
    BradenSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = BradenSerialDeltaPanel().check(BradenSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_braden_drop",
            "mobility_worsening",
            "moisture_rise",
            "nutrition_decline",
            "friction_shear_rise",
            "activity_decline",
        ],
        1,
    )
    panel = BradenSerialDeltaPanel()
    findings = panel.check(BradenSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        BradenSerialDeltaPanel().check(BradenSerialDeltaFactors(prior_braden_drop=2))
