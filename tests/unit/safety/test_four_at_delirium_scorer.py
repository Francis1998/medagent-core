"""Unit tests for FourAtDeliriumScorer."""

from __future__ import annotations

import pytest

from medagent.safety.four_at_delirium_scorer import (
    FourAtDeliriumFactors,
    FourAtDeliriumScorer,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = FourAtDeliriumScorer().check(FourAtDeliriumFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = FourAtDeliriumScorer().check(
        FourAtDeliriumFactors(alertness_change=1, amt4_errors=1)
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = FourAtDeliriumScorer().check(
        FourAtDeliriumFactors(
            alertness_change=1,
            amt4_errors=1,
            attention_months=1,
            acute_change_fluctuation=1,
            collateral_confusion=1,
            hospitalized=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        FourAtDeliriumScorer().check(FourAtDeliriumFactors(alertness_change=4))
