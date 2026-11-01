"""Tests for HuntHessSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.hunt_hess_serial_delta_panel import (
    HuntHessSerialDeltaFactors,
    HuntHessSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = HuntHessSerialDeltaPanel().check(HuntHessSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_hunt_hess_elevated",
            "consciousness_drop",
            "focal_deficit_new",
            "severe_headache_worsen",
            "nuchal_rigidity_new",
            "vasospasm_signal",
        ],
        1,
    )
    panel = HuntHessSerialDeltaPanel()
    findings = panel.check(HuntHessSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        HuntHessSerialDeltaPanel().check(HuntHessSerialDeltaFactors(prior_hunt_hess_elevated=2))
