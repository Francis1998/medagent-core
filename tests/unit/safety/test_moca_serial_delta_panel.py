"""Tests for MocaSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.moca_serial_delta_panel import (
    MocaSerialDeltaFactors,
    MocaSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = MocaSerialDeltaPanel().check(MocaSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = {
        "visuospatial_decline": 1,
        "naming_decline": 1,
        "attention_decline": 1,
        "language_decline": 1,
        "abstraction_decline": 1,
        "delayed_recall_decline": 1,
    }
    panel = MocaSerialDeltaPanel()
    findings = panel.check(MocaSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        MocaSerialDeltaPanel().check(MocaSerialDeltaFactors(visuospatial_decline=2))
