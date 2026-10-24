"""Unit tests for GenevaPeSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.geneva_pe_serial_delta_panel import (
    GenevaPeSerialDeltaFactors,
    GenevaPeSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = GenevaPeSerialDeltaPanel().check(GenevaPeSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = GenevaPeSerialDeltaPanel().check(
        GenevaPeSerialDeltaFactors(
            prior_geneva_elevated=1,
            current_geneva_rise=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = GenevaPeSerialDeltaPanel().check(
        GenevaPeSerialDeltaFactors(
            prior_geneva_elevated=1,
            current_geneva_rise=1,
            hr_worsening=1,
            hemoptysis_new=1,
            unilateral_pain_worsening=1,
            spo2_worsening=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        GenevaPeSerialDeltaPanel().check(GenevaPeSerialDeltaFactors(prior_geneva_elevated=2))
