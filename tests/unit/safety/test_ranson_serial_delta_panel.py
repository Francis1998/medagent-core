"""Unit tests for RansonSerialDeltaPanel."""

from __future__ import annotations

import pytest

from medagent.safety.ranson_serial_delta_panel import (
    RansonSerialDeltaFactors,
    RansonSerialDeltaPanel,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = RansonSerialDeltaPanel().check(RansonSerialDeltaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = RansonSerialDeltaPanel().check(
        RansonSerialDeltaFactors(
            prior_ranson_elevated=1,
            wbc_up=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = RansonSerialDeltaPanel().check(
        RansonSerialDeltaFactors(
            prior_ranson_elevated=1,
            wbc_up=1,
            glucose_up=1,
            ldh_up=1,
            ast_up=1,
            calcium_down=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Out-of-range factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        RansonSerialDeltaPanel().check(RansonSerialDeltaFactors(prior_ranson_elevated=2))
