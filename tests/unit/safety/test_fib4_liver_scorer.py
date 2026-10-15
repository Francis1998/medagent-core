"""Tests for Fib4LiverScorer."""

from __future__ import annotations

import pytest

from medagent.safety.fib4_liver_scorer import (
    Fib4LiverFactors,
    Fib4LiverScorer,
)


def test_low() -> None:
    """Low band."""

    findings = Fib4LiverScorer().check(Fib4LiverFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = Fib4LiverScorer().check(
        Fib4LiverFactors(
            age_ok=1,
            ast_ok=1,
            alt_ok=1,
            platelet_ok=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        Fib4LiverScorer().check(Fib4LiverFactors(age_ok=2))
