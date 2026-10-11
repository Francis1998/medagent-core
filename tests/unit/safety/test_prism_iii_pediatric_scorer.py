"""Unit tests for PrismIiiPediatricScorer."""

from __future__ import annotations

import pytest

from medagent.safety.prism_iii_pediatric_scorer import (
    PrismIiiPediatricFactors,
    PrismIiiPediatricScorer,
)


def test_low() -> None:
    """Low band."""

    findings = PrismIiiPediatricScorer().check(PrismIiiPediatricFactors())
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = PrismIiiPediatricScorer().check(
        PrismIiiPediatricFactors(cardio_ok=1, neuro_ok=1, resp_ok=1)
    )
    assert findings[0].band == "high"


def test_invalid_raises() -> None:
    """Invalid factor raises ValueError."""

    with pytest.raises(ValueError):
        PrismIiiPediatricScorer().check(PrismIiiPediatricFactors(cardio_ok=2))
