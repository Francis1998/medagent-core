"""Unit tests for MaddreyDiscriminantScorer."""

from __future__ import annotations

import pytest

from medagent.safety.maddrey_discriminant_scorer import (
    MaddreyDiscriminantFactors,
    MaddreyDiscriminantScorer,
)


def test_low() -> None:
    """Low band."""

    findings = MaddreyDiscriminantScorer().check(MaddreyDiscriminantFactors())
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = MaddreyDiscriminantScorer().check(
        MaddreyDiscriminantFactors(pt_ok=1, bili_ok=1, enceph_ok=1)
    )
    assert findings[0].band == "high"


def test_invalid_raises() -> None:
    """Invalid factor raises ValueError."""

    with pytest.raises(ValueError):
        MaddreyDiscriminantScorer().check(MaddreyDiscriminantFactors(pt_ok=2))
