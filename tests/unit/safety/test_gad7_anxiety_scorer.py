"""Tests for Gad7AnxietyScorer."""

from __future__ import annotations

import pytest

from medagent.safety.gad7_anxiety_scorer import (
    Gad7AnxietyFactors,
    Gad7AnxietyScorer,
)


def test_low() -> None:
    """Low band."""

    findings = Gad7AnxietyScorer().check(Gad7AnxietyFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = Gad7AnxietyScorer().check(
        Gad7AnxietyFactors(
            nervous_ok=1,
            control_worry_ok=1,
            worry_ok=1,
            relax_ok=1,
            restless_ok=1,
            irritable_ok=1,
            afraid_ok=1,
        )
    )
    assert findings[0].band == "high"


def test_invalid() -> None:
    """Invalid factor raises."""

    with pytest.raises(ValueError):
        Gad7AnxietyScorer().check(Gad7AnxietyFactors(nervous_ok=2))
