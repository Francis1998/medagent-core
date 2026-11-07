"""Tests for SofaDeltaOfDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.sofa_delta_of_delta_panel import (
    SofaDeltaOfDeltaFactors,
    SofaDeltaOfDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = SofaDeltaOfDeltaPanel().check(SofaDeltaOfDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = {
        "respiration_accel": 1,
        "coagulation_accel": 1,
        "liver_accel": 1,
        "cardiovascular_accel": 1,
        "cns_accel": 1,
        "renal_accel": 1,
    }
    panel = SofaDeltaOfDeltaPanel()
    findings = panel.check(SofaDeltaOfDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        SofaDeltaOfDeltaPanel().check(SofaDeltaOfDeltaFactors(respiration_accel=2))
