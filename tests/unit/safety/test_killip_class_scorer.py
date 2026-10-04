"""Unit tests for KillipClassScorer."""

from __future__ import annotations

import pytest

from medagent.safety.killip_class_scorer import (
    KillipClassFactors,
    KillipClassScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = KillipClassScorer().check(KillipClassFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = KillipClassScorer().check(
        KillipClassFactors(
            class_i_no_failure=1,
            class_ii_s3_rales=1,
            class_iii_pulmonary_edema=1,
            class_iv_cardiogenic_shock=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        KillipClassScorer().check(KillipClassFactors(class_i_no_failure=2))
