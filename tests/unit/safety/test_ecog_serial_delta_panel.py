"""Tests for EcogSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.ecog_serial_delta_panel import (
    EcogSerialDeltaFactors,
    EcogSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = EcogSerialDeltaPanel().check(EcogSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_ecog_elevated",
            "ambulation_decline",
            "self_care_loss",
            "work_capacity_drop",
            "bedbound_signal",
            "symptom_burden_rise",
        ],
        1,
    )
    panel = EcogSerialDeltaPanel()
    findings = panel.check(EcogSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        EcogSerialDeltaPanel().check(EcogSerialDeltaFactors(prior_ecog_elevated=2))
