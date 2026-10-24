"""Unit tests for TimiSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.timi_serial_delta_panel import (
    TimiSerialDeltaFactors,
    TimiSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = TimiSerialDeltaPanel().check(TimiSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = TimiSerialDeltaPanel().check(
        TimiSerialDeltaFactors(
            prior_timi_elevated=1,
            current_timi_rise=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = TimiSerialDeltaPanel().check(
        TimiSerialDeltaFactors(
            prior_timi_elevated=1,
            current_timi_rise=1,
            troponin_rise=1,
            st_deviation_worsening=1,
            angina_frequency_rise=1,
            asa_use_recent=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        TimiSerialDeltaPanel().check(TimiSerialDeltaFactors(prior_timi_elevated=2))
