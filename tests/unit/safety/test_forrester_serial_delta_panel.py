"""Tests for ForresterSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.forrester_serial_delta_panel import (
    ForresterSerialDeltaFactors,
    ForresterSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = ForresterSerialDeltaPanel().check(ForresterSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_forrester_elevated",
            "pulmonary_congestion_worsen",
            "hypoperfusion_new",
            "filling_pressure_rise",
            "cardiac_index_drop",
            "vasopressor_escalation",
        ],
        1,
    )
    panel = ForresterSerialDeltaPanel()
    findings = panel.check(ForresterSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        ForresterSerialDeltaPanel().check(ForresterSerialDeltaFactors(prior_forrester_elevated=2))
