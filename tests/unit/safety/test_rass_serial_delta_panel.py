"""Tests for RassSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.rass_serial_delta_panel import (
    RassSerialDeltaFactors,
    RassSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = RassSerialDeltaPanel().check(RassSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_rass_elevated",
            "agitation_rise",
            "sedation_deepening",
            "ventilator_dyssynchrony",
            "pain_breakthrough",
            "delirium_overlap",
        ],
        1,
    )
    panel = RassSerialDeltaPanel()
    findings = panel.check(RassSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        RassSerialDeltaPanel().check(RassSerialDeltaFactors(prior_rass_elevated=2))
