"""Tests for PesiSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.pesi_serial_delta_panel import (
    PesiSerialDeltaFactors,
    PesiSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = PesiSerialDeltaPanel().check(PesiSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_pesi_elevated",
            "hr_rise",
            "sbp_drop",
            "o2_sat_drop",
            "mental_status_worsen",
            "rr_rise",
        ],
        1,
    )
    findings = PesiSerialDeltaPanel().check(PesiSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        PesiSerialDeltaPanel().check(PesiSerialDeltaFactors(prior_pesi_elevated=2))
