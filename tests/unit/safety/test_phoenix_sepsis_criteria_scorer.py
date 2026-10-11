"""Unit tests for PhoenixSepsisCriteriaScorer."""

from __future__ import annotations

import pytest

from medagent.safety.phoenix_sepsis_criteria_scorer import (
    PhoenixSepsisCriteriaFactors,
    PhoenixSepsisCriteriaScorer,
)


def test_low() -> None:
    """Low band."""

    findings = PhoenixSepsisCriteriaScorer().check(PhoenixSepsisCriteriaFactors())
    assert findings[0].band == "low"
    assert findings[0].rationale


def test_high() -> None:
    """High band."""

    findings = PhoenixSepsisCriteriaScorer().check(
        PhoenixSepsisCriteriaFactors(resp_ok=1, cardio_ok=1, coag_ok=1)
    )
    assert findings[0].band == "high"


def test_invalid_raises() -> None:
    """Invalid factor raises ValueError."""

    with pytest.raises(ValueError):
        PhoenixSepsisCriteriaScorer().check(PhoenixSepsisCriteriaFactors(resp_ok=2))
