"""Unit tests for Abcd2SerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.abcd2_serial_delta_panel import (
    Abcd2SerialDeltaFactors,
    Abcd2SerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = Abcd2SerialDeltaPanel().check(Abcd2SerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = Abcd2SerialDeltaPanel().check(
        Abcd2SerialDeltaFactors(
            prior_abcd2_elevated=1,
            age_factor_new=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = Abcd2SerialDeltaPanel().check(
        Abcd2SerialDeltaFactors(
            prior_abcd2_elevated=1,
            age_factor_new=1,
            bp_factor_new=1,
            clinical_features_worsened=1,
            duration_extended=1,
            diabetes_new=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        Abcd2SerialDeltaPanel().check(Abcd2SerialDeltaFactors(prior_abcd2_elevated=2))
