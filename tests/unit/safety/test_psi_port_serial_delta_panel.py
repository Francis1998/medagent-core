"""Tests for PsiPortSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.psi_port_serial_delta_panel import (
    PsiPortSerialDeltaFactors,
    PsiPortSerialDeltaPanel,
)


def test_low_band() -> None:
    """Low score band."""

    findings = PsiPortSerialDeltaPanel().check(PsiPortSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high_band() -> None:
    """High when many factors set."""

    kwargs = dict.fromkeys(
        [
            "prior_psi_elevated",
            "age_band_worsened",
            "comorbidity_new",
            "vitals_worsened",
            "labs_worsened",
            "oxygen_need_new",
        ],
        1,
    )
    findings = PsiPortSerialDeltaPanel().check(PsiPortSerialDeltaFactors(**kwargs))
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError):
        PsiPortSerialDeltaPanel().check(PsiPortSerialDeltaFactors(prior_psi_elevated=2))
