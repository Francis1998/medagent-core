"""Tests for CiwaSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.ciwa_serial_delta_panel import (
    CiwaSerialDeltaFactors,
    CiwaSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = CiwaSerialDeltaPanel().check(CiwaSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_ciwa_rise",
            "tremor_worsening",
            "anxiety_rise",
            "agitation_rise",
            "orientation_decline",
            "paroxysmal_sweats_rise",
        ],
        1,
    )
    panel = CiwaSerialDeltaPanel()
    findings = panel.check(CiwaSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        CiwaSerialDeltaPanel().check(CiwaSerialDeltaFactors(prior_ciwa_rise=2))
