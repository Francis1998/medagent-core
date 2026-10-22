"""Unit tests for ImproveVteScorer."""

from __future__ import annotations

import pytest

from medagent.safety.improve_vte_scorer import (
    ImproveVteFactors,
    ImproveVteScorer,
)


def test_low_band() -> None:
    """Zero factors -> low."""

    findings = ImproveVteScorer().check(ImproveVteFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_intermediate_band() -> None:
    """Few positives -> intermediate."""

    findings = ImproveVteScorer().check(
        ImproveVteFactors(
            prior_vte=1,
            known_thrombophilia=1,
        )
    )
    assert findings[0].band == "intermediate"


def test_high_band() -> None:
    """Many positives -> high."""

    findings = ImproveVteScorer().check(
        ImproveVteFactors(
            prior_vte=1,
            known_thrombophilia=1,
            active_cancer=1,
            icu_stay=1,
            lower_limb_paralysis=1,
            immobilization_7d=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid_factor() -> None:
    """Non binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        ImproveVteScorer().check(ImproveVteFactors(prior_vte=4))
