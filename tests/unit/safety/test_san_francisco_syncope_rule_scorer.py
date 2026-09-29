"""Unit tests for SanFranciscoSyncopeRuleScorer."""

from __future__ import annotations

from medagent.safety.san_francisco_syncope_rule_scorer import (
    SanFranciscoSyncopeFactors,
    SanFranciscoSyncopeRuleScorer,
)


def test_low_risk() -> None:
    """No factors is low_risk."""

    findings = SanFranciscoSyncopeRuleScorer().check(SanFranciscoSyncopeFactors())
    assert findings[0].band == "low_risk"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_moderate_risk() -> None:
    """Mid score is moderate_risk."""

    findings = SanFranciscoSyncopeRuleScorer().check(SanFranciscoSyncopeFactors(chf_history=1))
    assert findings[0].band == "moderate_risk"


def test_high_risk() -> None:
    """High score is high_risk."""

    findings = SanFranciscoSyncopeRuleScorer().check(
        SanFranciscoSyncopeFactors(chf_history=1, hematocrit_lt_30=1)
    )
    assert findings[0].band == "high_risk"
