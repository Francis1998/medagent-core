"""Unit tests for AspectsStrokeScorer."""

from __future__ import annotations

import pytest

from medagent.safety.aspects_stroke_scorer import (
    AspectsStrokeFactors,
    AspectsStrokeScorer,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = AspectsStrokeScorer().check(AspectsStrokeFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = AspectsStrokeScorer().check(
        AspectsStrokeFactors(
            mca_cortical_loss=1,
            insula_ribbon_loss=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = AspectsStrokeScorer().check(
        AspectsStrokeFactors(
            mca_cortical_loss=1,
            insula_ribbon_loss=1,
            lentiform_hypodensity=1,
            caudate_hypodensity=1,
            internal_capsule_loss=1,
            posterior_mca_loss=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        AspectsStrokeScorer().check(AspectsStrokeFactors(mca_cortical_loss=4))
