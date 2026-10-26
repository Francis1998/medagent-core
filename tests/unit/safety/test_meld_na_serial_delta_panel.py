"""Unit tests for MeldNaSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.meld_na_serial_delta_panel import (
    MeldNaSerialDeltaFactors,
    MeldNaSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = MeldNaSerialDeltaPanel().check(MeldNaSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = MeldNaSerialDeltaPanel().check(
        MeldNaSerialDeltaFactors(
            prior_meld_elevated=1,
            creatinine_up=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = MeldNaSerialDeltaPanel().check(
        MeldNaSerialDeltaFactors(
            prior_meld_elevated=1,
            creatinine_up=1,
            bilirubin_up=1,
            inr_up=1,
            sodium_down=1,
            dialysis_new=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        MeldNaSerialDeltaPanel().check(MeldNaSerialDeltaFactors(prior_meld_elevated=2))
