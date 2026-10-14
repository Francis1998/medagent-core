"""Tests for ShockIndexScorer."""

from __future__ import annotations

import pytest

from medagent.safety.shock_index_scorer import (
    ShockIndexFactors,
    ShockIndexScorer,
)


def test_low() -> None:
    """Low band."""

    findings = ShockIndexScorer().check(ShockIndexFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = ShockIndexScorer().check(
        ShockIndexFactors(
            hr_ok=1,
            sbp_ok=1,
            altered_ok=1,
            lactate_ok=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        ShockIndexScorer().check(ShockIndexFactors(hr_ok=2))
