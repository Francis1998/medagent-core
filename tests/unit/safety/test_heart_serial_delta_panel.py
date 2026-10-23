"""Unit tests for HeartSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.heart_serial_delta_panel import (
    HeartSerialDeltaFactors,
    HeartSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = HeartSerialDeltaPanel().check(HeartSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = HeartSerialDeltaPanel().check(
        HeartSerialDeltaFactors(
            prior_heart_elevated=1,
            current_heart_rise=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = HeartSerialDeltaPanel().check(
        HeartSerialDeltaFactors(
            prior_heart_elevated=1,
            current_heart_rise=1,
            troponin_worsening=1,
            ecg_worsening=1,
            history_worsening=1,
            risk_factor_worsening=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        HeartSerialDeltaPanel().check(HeartSerialDeltaFactors(prior_heart_elevated=4))
