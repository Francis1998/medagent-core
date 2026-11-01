"""Tests for WfnsSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.wfns_serial_delta_panel import (
    WfnsSerialDeltaFactors,
    WfnsSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = WfnsSerialDeltaPanel().check(WfnsSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_wfns_elevated",
            "gcs_drop",
            "motor_deficit_new",
            "aphasia_new",
            "pupil_asymmetry_new",
            "delayed_ischemia_signal",
        ],
        1,
    )
    panel = WfnsSerialDeltaPanel()
    findings = panel.check(WfnsSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        WfnsSerialDeltaPanel().check(WfnsSerialDeltaFactors(prior_wfns_elevated=2))
