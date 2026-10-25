"""Unit tests for Cha2ds2VascSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.cha2ds2_vasc_serial_delta_panel import (
    Cha2ds2VascSerialDeltaFactors,
    Cha2ds2VascSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = Cha2ds2VascSerialDeltaPanel().check(Cha2ds2VascSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = Cha2ds2VascSerialDeltaPanel().check(
        Cha2ds2VascSerialDeltaFactors(
            prior_vasc_elevated=1,
            new_chf=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = Cha2ds2VascSerialDeltaPanel().check(
        Cha2ds2VascSerialDeltaFactors(
            prior_vasc_elevated=1,
            new_chf=1,
            new_hypertension=1,
            age_band_up=1,
            new_diabetes=1,
            prior_stroke_tia=1,
            vascular_disease_new=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        Cha2ds2VascSerialDeltaPanel().check(Cha2ds2VascSerialDeltaFactors(prior_vasc_elevated=2))
