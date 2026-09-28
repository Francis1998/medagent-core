"""Unit tests for CanadianCspineRuleScorer."""

from __future__ import annotations

from medagent.safety.canadian_cspine_rule_scorer import (
    CanadianCspineFactors,
    CanadianCspineRuleScorer,
)


def test_imaging_not_indicated() -> None:
    """No factors is imaging_not_indicated."""

    findings = CanadianCspineRuleScorer().check(CanadianCspineFactors())
    assert findings[0].band == "imaging_not_indicated"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_consider_imaging() -> None:
    """Single factor is consider_imaging."""

    findings = CanadianCspineRuleScorer().check(CanadianCspineFactors(age_ge_65=1))
    assert findings[0].band == "consider_imaging"
    assert findings[0].score == 1


def test_imaging_indicated() -> None:
    """Two+ factors is imaging_indicated."""

    findings = CanadianCspineRuleScorer().check(
        CanadianCspineFactors(age_ge_65=1, dangerous_mechanism=1)
    )
    assert findings[0].band == "imaging_indicated"
    assert findings[0].score == 2
