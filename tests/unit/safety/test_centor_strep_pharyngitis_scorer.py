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


def test_mcisaac_age_45_or_older_subtracts_one_point() -> None:
    """McIsaac 1998 (PMID 9475915): age >= 45 scores -1, so four signs at 50 years total 3."""
    findings = CentorStrepPharyngitisScorer().check(
        CentorStrepPharyngitisFactors(
            tonsillar_exudate=1,
            tender_anterior_nodes=1,
            fever_history=1,
            cough_absent=1,
            age_bonus=-1,
        )
    )
    assert findings[0].score == 3
    assert findings[0].band == "moderate"


def test_age_bonus_outside_mcisaac_range_raises() -> None:
    with pytest.raises(ValueError, match="age_bonus"):
        CentorStrepPharyngitisScorer().check(CentorStrepPharyngitisFactors(age_bonus=2))
