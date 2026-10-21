"""Unit tests for ForresterClassScorer."""

from __future__ import annotations

import pytest

from medagent.safety.forrester_class_scorer import (
    ForresterClassFactors,
    ForresterClassScorer,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = ForresterClassScorer().check(ForresterClassFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = ForresterClassScorer().check(
        ForresterClassFactors(
            pulmonary_congestion=1,
            peripheral_hypoperfusion=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = ForresterClassScorer().check(
        ForresterClassFactors(
            pulmonary_congestion=1,
            peripheral_hypoperfusion=1,
            cardiogenic_shock_signs=1,
            elevated_filling_pressures=1,
            low_cardiac_index=1,
            vasopressor_support=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        ForresterClassScorer().check(ForresterClassFactors(pulmonary_congestion=4))
