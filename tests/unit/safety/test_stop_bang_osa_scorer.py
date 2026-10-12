"""Unit tests for StopBangOsaScorer."""

from __future__ import annotations

import pytest

from medagent.safety.stop_bang_osa_scorer import (
    StopBangOsaFactors,
    StopBangOsaScorer,
)


def test_low() -> None:
    """Low band."""

    findings = StopBangOsaScorer().check(StopBangOsaFactors())
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = StopBangOsaScorer().check(StopBangOsaFactors(snore_ok=1, tired_ok=1, observed_ok=1))
    assert findings[0].band == "high"


def test_invalid_raises() -> None:
    """Invalid factor raises ValueError."""

    with pytest.raises(ValueError):
        StopBangOsaScorer().check(StopBangOsaFactors(snore_ok=2))
