"""Unit tests for PercSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.perc_serial_delta_panel import (
    PercSerialDeltaFactors,
    PercSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = PercSerialDeltaPanel().check(PercSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = PercSerialDeltaPanel().check(
        PercSerialDeltaFactors(
            prior_perc_positive=1,
            new_perc_factor=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = PercSerialDeltaPanel().check(
        PercSerialDeltaFactors(
            prior_perc_positive=1,
            new_perc_factor=1,
            hr_rise=1,
            spo2_drop=1,
            hemoptysis_onset=1,
            estrogen_exposure=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        PercSerialDeltaPanel().check(PercSerialDeltaFactors(prior_perc_positive=2))
