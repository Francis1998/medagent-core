"""Unit tests for KillipSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.killip_serial_delta_panel import (
    KillipSerialDeltaFactors,
    KillipSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = KillipSerialDeltaPanel().check(KillipSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = KillipSerialDeltaPanel().check(
        KillipSerialDeltaFactors(
            prior_killip_elevated=1,
            killip_class_rise=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = KillipSerialDeltaPanel().check(
        KillipSerialDeltaFactors(
            prior_killip_elevated=1,
            killip_class_rise=1,
            rales_worsening=1,
            s3_new=1,
            hypotension_onset=1,
            cardiogenic_shock_sign=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        KillipSerialDeltaPanel().check(KillipSerialDeltaFactors(prior_killip_elevated=2))
