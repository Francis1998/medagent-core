"""Unit tests for CiwaArWithdrawalScorer."""

from __future__ import annotations

import pytest

from medagent.safety.ciwa_ar_withdrawal_scorer import (
    CiwaArWithdrawalFactors,
    CiwaArWithdrawalScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = CiwaArWithdrawalScorer().check(CiwaArWithdrawalFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = CiwaArWithdrawalScorer().check(
        CiwaArWithdrawalFactors(
            nausea=1, tremor=1, anxiety=1, agitation=1, paroxysmal_sweats=1, orientation_deficit=1
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        CiwaArWithdrawalScorer().check(CiwaArWithdrawalFactors(nausea=2))
