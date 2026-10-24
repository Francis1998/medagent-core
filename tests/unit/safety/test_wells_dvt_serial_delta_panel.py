"""Unit tests for WellsDvtSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.wells_dvt_serial_delta_panel import (
    WellsDvtSerialDeltaFactors,
    WellsDvtSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = WellsDvtSerialDeltaPanel().check(WellsDvtSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = WellsDvtSerialDeltaPanel().check(
        WellsDvtSerialDeltaFactors(
            prior_wells_dvt_elevated=1,
            current_wells_dvt_rise=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = WellsDvtSerialDeltaPanel().check(
        WellsDvtSerialDeltaFactors(
            prior_wells_dvt_elevated=1,
            current_wells_dvt_rise=1,
            calf_swelling_worsening=1,
            tenderness_worsening=1,
            immobility_worsening=1,
            alt_diagnosis_less_likely=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        WellsDvtSerialDeltaPanel().check(WellsDvtSerialDeltaFactors(prior_wells_dvt_elevated=2))
