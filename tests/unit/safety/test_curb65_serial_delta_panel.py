"""Unit tests for Curb65SerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.curb65_serial_delta_panel import (
    Curb65SerialDeltaFactors,
    Curb65SerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = Curb65SerialDeltaPanel().check(Curb65SerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = Curb65SerialDeltaPanel().check(
        Curb65SerialDeltaFactors(prior_curb_elevated=1, current_curb_rise=1)
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = Curb65SerialDeltaPanel().check(
        Curb65SerialDeltaFactors(
            prior_curb_elevated=1,
            current_curb_rise=1,
            urea_rise=1,
            rr_worsening=1,
            bp_drop=1,
            confusion_new=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        Curb65SerialDeltaPanel().check(Curb65SerialDeltaFactors(prior_curb_elevated=4))
