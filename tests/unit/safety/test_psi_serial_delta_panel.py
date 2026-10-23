"""Unit tests for PsiSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.psi_serial_delta_panel import (
    PsiSerialDeltaFactors,
    PsiSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = PsiSerialDeltaPanel().check(PsiSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = PsiSerialDeltaPanel().check(
        PsiSerialDeltaFactors(
            prior_psi_elevated=1,
            current_psi_rise=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = PsiSerialDeltaPanel().check(
        PsiSerialDeltaFactors(
            prior_psi_elevated=1,
            current_psi_rise=1,
            resp_worsening=1,
            bp_worsening=1,
            mental_status_worsening=1,
            lab_worsening=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        PsiSerialDeltaPanel().check(PsiSerialDeltaFactors(prior_psi_elevated=4))
