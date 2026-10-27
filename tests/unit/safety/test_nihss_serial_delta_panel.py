"""Unit tests for NihssSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.nihss_serial_delta_panel import (
    NihssSerialDeltaFactors,
    NihssSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = NihssSerialDeltaPanel().check(NihssSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = NihssSerialDeltaPanel().check(
        NihssSerialDeltaFactors(
            prior_nihss_elevated=1,
            loc_worse=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = NihssSerialDeltaPanel().check(
        NihssSerialDeltaFactors(
            prior_nihss_elevated=1,
            loc_worse=1,
            motor_worse=1,
            language_worse=1,
            gaze_worse=1,
            sensory_worse=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        NihssSerialDeltaPanel().check(NihssSerialDeltaFactors(prior_nihss_elevated=2))
