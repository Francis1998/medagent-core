"""Unit tests for AbcIchScorer."""

from __future__ import annotations

import pytest

from medagent.safety.abc_ich_scorer import (
    AbcIchFactors,
    AbcIchScorer,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = AbcIchScorer().check(AbcIchFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = AbcIchScorer().check(
        AbcIchFactors(
            large_volume=1,
            intraventricular_extension=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = AbcIchScorer().check(
        AbcIchFactors(
            large_volume=1,
            intraventricular_extension=1,
            infratentorial_origin=1,
            gcs_depressed=1,
            anticoagulation=1,
            age_high=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        AbcIchScorer().check(AbcIchFactors(large_volume=4))
