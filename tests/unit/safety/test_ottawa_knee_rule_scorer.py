"""Unit tests for OttawaKneeRuleScorer."""

from __future__ import annotations

import pytest

from medagent.safety.ottawa_knee_rule_scorer import OttawaKneeRuleFactors, OttawaKneeRuleScorer


def test_low_band() -> None:
    """Zero factors -> low band."""

    findings = OttawaKneeRuleScorer().check(OttawaKneeRuleFactors())
    assert len(findings) == 1
    assert findings[0].band == "low"
    assert "RESEARCH USE ONLY" in findings[0].rationale


def test_elevated_band() -> None:
    """Multiple factors elevate band."""

    findings = OttawaKneeRuleScorer().check(
        OttawaKneeRuleFactors(
            age_ge_55=1,
            isolated_patellar_tenderness=1,
            fibular_head_tenderness=1,
            unable_flex_90=1,
            unable_bear_weight=1,
        )
    )
    assert findings[0].score >= 1
    assert findings[0].band in {"low", "intermediate", "high"}


def test_invalid_factor() -> None:
    """Non-binary factor raises."""

    with pytest.raises(ValueError, match="must be 0 or 1"):
        OttawaKneeRuleScorer().check(OttawaKneeRuleFactors(age_ge_55=2))
