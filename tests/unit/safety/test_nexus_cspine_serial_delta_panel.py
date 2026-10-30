"""Tests for NexusCspineSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.nexus_cspine_serial_delta_panel import (
    NexusCspineSerialDeltaFactors,
    NexusCspineSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = NexusCspineSerialDeltaPanel().check(NexusCspineSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_nexus_positive",
            "midline_tenderness_new",
            "focal_neuro_new",
            "altered_alertness_new",
            "intoxication_new",
            "distracting_injury_new",
        ],
        1,
    )
    findings = NexusCspineSerialDeltaPanel().check(NexusCspineSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        NexusCspineSerialDeltaPanel().check(NexusCspineSerialDeltaFactors(prior_nexus_positive=2))
