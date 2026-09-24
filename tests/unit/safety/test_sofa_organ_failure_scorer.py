"""Unit tests for SofaOrganFailureScorer."""

from __future__ import annotations

import pytest

from medagent.safety.sofa_organ_failure_scorer import (
    SofaOrganFailureFactors,
    SofaOrganFailureScorer,
)


def test_default_band() -> None:
    """Default factors yield expected advisory band."""

    findings = SofaOrganFailureScorer().check(SofaOrganFailureFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_elevated_band() -> None:
    """Elevated factors yield high/severe band."""

    findings = SofaOrganFailureScorer().check(
        SofaOrganFailureFactors(
            respiration_points=4,
            coagulation_points=4,
            liver_points=4,
            cardiovascular_points=4,
            cns_points=4,
            renal_points=4,
        )
    )
    assert findings[0].band == "high"
    assert findings[0].score == 24


def test_invalid_points_raises() -> None:
    """Out-of-range domain points raise ValueError."""

    with pytest.raises(ValueError, match="respiration_points"):
        SofaOrganFailureScorer().check(SofaOrganFailureFactors(respiration_points=5))
