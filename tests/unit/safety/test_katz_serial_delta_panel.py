"""Tests for KatzSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.katz_serial_delta_panel import (
    KatzSerialDeltaFactors,
    KatzSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = KatzSerialDeltaPanel().check(KatzSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = {
        "bathing_decline": 1,
        "dressing_decline": 1,
        "toileting_decline": 1,
        "transferring_decline": 1,
        "continence_decline": 1,
        "feeding_decline": 1,
    }
    panel = KatzSerialDeltaPanel()
    findings = panel.check(KatzSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        KatzSerialDeltaPanel().check(KatzSerialDeltaFactors(bathing_decline=2))
