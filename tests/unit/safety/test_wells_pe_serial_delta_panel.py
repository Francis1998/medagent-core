"""Unit tests for WellsPeSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.wells_pe_serial_delta_panel import (
    WellsPeSerialDeltaFactors,
    WellsPeSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = WellsPeSerialDeltaPanel().check(WellsPeSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = WellsPeSerialDeltaPanel().check(
        WellsPeSerialDeltaFactors(
            prior_wells_elevated=1,
            current_wells_rise=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = WellsPeSerialDeltaPanel().check(
        WellsPeSerialDeltaFactors(
            prior_wells_elevated=1,
            current_wells_rise=1,
            dvt_signs_worsening=1,
            hr_worsening=1,
            immobilization_new=1,
            hemoptysis_new=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        WellsPeSerialDeltaPanel().check(WellsPeSerialDeltaFactors(prior_wells_elevated=4))
