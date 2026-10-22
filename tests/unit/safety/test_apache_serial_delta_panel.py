"""Unit tests for ApacheSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.apache_serial_delta_panel import (
    ApacheSerialDeltaFactors,
    ApacheSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = ApacheSerialDeltaPanel().check(ApacheSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = ApacheSerialDeltaPanel().check(
        ApacheSerialDeltaFactors(
            prior_apache_elevated=1,
            current_apache_rise=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = ApacheSerialDeltaPanel().check(
        ApacheSerialDeltaFactors(
            prior_apache_elevated=1,
            current_apache_rise=1,
            resp_worsening=1,
            cardio_worsening=1,
            neuro_worsening=1,
            renal_worsening=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        ApacheSerialDeltaPanel().check(ApacheSerialDeltaFactors(prior_apache_elevated=4))
