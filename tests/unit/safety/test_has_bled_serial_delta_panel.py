"""Tests for HasBledSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.has_bled_serial_delta_panel import (
    HasBledSerialDeltaFactors,
    HasBledSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = HasBledSerialDeltaPanel().check(HasBledSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_has_bled_elevated",
            "hypertension_uncontrolled_new",
            "renal_liver_worsened",
            "stroke_history_new",
            "bleeding_history_new",
            "labile_inr_new",
        ],
        1,
    )
    findings = HasBledSerialDeltaPanel().check(HasBledSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        HasBledSerialDeltaPanel().check(HasBledSerialDeltaFactors(prior_has_bled_elevated=2))
