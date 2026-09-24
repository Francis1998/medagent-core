"""Unit tests for CentorStrepPharyngitisScorer."""

from __future__ import annotations

import pytest

from medagent.safety.centor_strep_pharyngitis_scorer import (
    CentorStrepPharyngitisFactors,
    CentorStrepPharyngitisScorer,
)


def test_default_band() -> None:
    """Default factors yield expected advisory band."""

    findings = CentorStrepPharyngitisScorer().check(CentorStrepPharyngitisFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_elevated_band() -> None:
    """Elevated factors yield high/severe band."""

    findings = CentorStrepPharyngitisScorer().check(
        CentorStrepPharyngitisFactors(
            tonsillar_exudate=1,
            tender_anterior_nodes=1,
            fever_history=1,
            cough_absent=1,
            age_bonus=1,
        )
    )
    assert findings[0].band == "high"
    assert findings[0].score == 5


def test_invalid_factor_raises() -> None:
    """Non-binary factor raises ValueError."""

    with pytest.raises(ValueError, match="tonsillar_exudate"):
        CentorStrepPharyngitisScorer().check(CentorStrepPharyngitisFactors(tonsillar_exudate=2))
