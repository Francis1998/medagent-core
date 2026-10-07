"""Unit tests for CanadianCtHeadScorer."""

from __future__ import annotations

import pytest

from medagent.safety.canadian_ct_head_scorer import (
    CanadianCtHeadFactors,
    CanadianCtHeadScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = CanadianCtHeadScorer().check(CanadianCtHeadFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = CanadianCtHeadScorer().check(
        CanadianCtHeadFactors(
            gcs_lt_15_2h=1,
            suspected_open_skull_fracture=1,
            sign_basal_skull_fracture=1,
            vomiting_ge_2=1,
            age_ge_65=1,
            amnesia_ge_30min=1,
            dangerous_mechanism=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        CanadianCtHeadScorer().check(CanadianCtHeadFactors(gcs_lt_15_2h=2))
