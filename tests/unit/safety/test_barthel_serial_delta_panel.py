"""Tests for BarthelSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.barthel_serial_delta_panel import (
    BarthelSerialDeltaFactors,
    BarthelSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = BarthelSerialDeltaPanel().check(BarthelSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = {
        "feeding_decline": 1,
        "bathing_decline": 1,
        "dressing_decline": 1,
        "toileting_decline": 1,
        "mobility_decline": 1,
        "continence_worsening": 1,
    }
    panel = BarthelSerialDeltaPanel()
    findings = panel.check(BarthelSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        BarthelSerialDeltaPanel().check(BarthelSerialDeltaFactors(feeding_decline=2))
