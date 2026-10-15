"""Tests for BisapPancreatitisScorer."""

from __future__ import annotations

import pytest

from medagent.safety.bisap_pancreatitis_scorer import (
    BisapPancreatitisFactors,
    BisapPancreatitisScorer,
)


def test_low() -> None:
    """Low band."""

    findings = BisapPancreatitisScorer().check(BisapPancreatitisFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = BisapPancreatitisScorer().check(
        BisapPancreatitisFactors(
            bun_ok=1,
            impaired_mental_ok=1,
            sirs_ok=1,
            age_ok=1,
            pleural_effusion_ok=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        BisapPancreatitisScorer().check(BisapPancreatitisFactors(bun_ok=2))
