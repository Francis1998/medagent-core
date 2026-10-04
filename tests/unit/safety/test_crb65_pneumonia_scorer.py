"""Unit tests for Crb65PneumoniaScorer."""

from __future__ import annotations

import pytest

from medagent.safety.crb65_pneumonia_scorer import (
    Crb65PneumoniaFactors,
    Crb65PneumoniaScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = Crb65PneumoniaScorer().check(Crb65PneumoniaFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = Crb65PneumoniaScorer().check(
        Crb65PneumoniaFactors(
            confusion=1,
            respiratory_rate_ge_30=1,
            sbp_lt_90_or_dbp_le_60=1,
            age_ge_65=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        Crb65PneumoniaScorer().check(Crb65PneumoniaFactors(confusion=2))
