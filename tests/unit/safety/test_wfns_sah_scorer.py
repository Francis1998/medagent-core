"""Unit tests for WfnsSahScorer."""

from __future__ import annotations

import pytest

from medagent.safety.wfns_sah_scorer import (
    WfnsSahFactors,
    WfnsSahScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = WfnsSahScorer().check(WfnsSahFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = WfnsSahScorer().check(
        WfnsSahFactors(
            grade_ge_3=1,
            motor_deficit=1,
            gcs_le_12=1,
            gcs_le_6=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        WfnsSahScorer().check(WfnsSahFactors(grade_ge_3=2))
