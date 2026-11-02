"""Tests for FourAtSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.four_at_serial_delta_panel import (
    FourAtSerialDeltaFactors,
    FourAtSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = FourAtSerialDeltaPanel().check(FourAtSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_four_at_elevated",
            "alertness_drop",
            "amt4_worsen",
            "attention_fail_new",
            "acute_change_flag",
            "fluctuation_new",
        ],
        1,
    )
    panel = FourAtSerialDeltaPanel()
    findings = panel.check(FourAtSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        FourAtSerialDeltaPanel().check(FourAtSerialDeltaFactors(prior_four_at_elevated=2))
