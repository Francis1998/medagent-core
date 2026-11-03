"""Tests for CamIcuSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.cam_icu_serial_delta_panel import (
    CamIcuSerialDeltaFactors,
    CamIcuSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = CamIcuSerialDeltaPanel().check(CamIcuSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_cam_positive",
            "fluctuation_rise",
            "inattention_worsening",
            "disorganized_thinking",
            "altered_loc",
            "sleep_wake_disruption",
        ],
        1,
    )
    panel = CamIcuSerialDeltaPanel()
    findings = panel.check(CamIcuSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        CamIcuSerialDeltaPanel().check(CamIcuSerialDeltaFactors(prior_cam_positive=2))
