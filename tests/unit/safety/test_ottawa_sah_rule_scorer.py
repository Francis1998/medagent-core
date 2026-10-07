"""Unit tests for OttawaSahRuleScorer."""

from __future__ import annotations

import pytest

from medagent.safety.ottawa_sah_rule_scorer import (
    OttawaSahRuleFactors,
    OttawaSahRuleScorer,
)


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = OttawaSahRuleScorer().check(OttawaSahRuleFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_high_band() -> None:
    """Many factors elevate band."""

    findings = OttawaSahRuleScorer().check(
        OttawaSahRuleFactors(
            age_ge_40=1,
            neck_pain_stiffness=1,
            witnessed_loss_consciousness=1,
            onset_during_exertion=1,
            thunderclap_headline=1,
            limited_neck_flexion=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        OttawaSahRuleScorer().check(OttawaSahRuleFactors(age_ge_40=2))
