"""Unit tests for MewsSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.mews_serial_delta_panel import (
    MewsSerialDeltaFactors,
    MewsSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = MewsSerialDeltaPanel().check(MewsSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = MewsSerialDeltaPanel().check(
        MewsSerialDeltaFactors(
            prior_mews_elevated=1,
            current_mews_rise=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = MewsSerialDeltaPanel().check(
        MewsSerialDeltaFactors(
            prior_mews_elevated=1,
            current_mews_rise=1,
            resp_worsening=1,
            hr_worsening=1,
            bp_worsening=1,
            avs_worsening=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        MewsSerialDeltaPanel().check(MewsSerialDeltaFactors(prior_mews_elevated=4))
