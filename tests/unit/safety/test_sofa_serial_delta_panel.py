"""Unit tests for SofaSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.sofa_serial_delta_panel import (
    SofaSerialDeltaFactors,
    SofaSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = SofaSerialDeltaPanel().check(SofaSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = SofaSerialDeltaPanel().check(
        SofaSerialDeltaFactors(prior_sofa_elevated=1, current_sofa_rise=1)
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = SofaSerialDeltaPanel().check(
        SofaSerialDeltaFactors(
            prior_sofa_elevated=1,
            current_sofa_rise=1,
            resp_worsening=1,
            coag_worsening=1,
            liver_worsening=1,
            cv_worsening=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        SofaSerialDeltaPanel().check(SofaSerialDeltaFactors(prior_sofa_elevated=4))
