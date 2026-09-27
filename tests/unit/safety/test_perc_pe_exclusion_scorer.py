"""Unit tests for PercPeExclusionScorer."""

from __future__ import annotations

from medagent.safety.perc_pe_exclusion_scorer import PercPeExclusionScorer, PercPeFactors


def test_rule_out_band() -> None:
    """No PERC factors is rule_out."""

    findings = PercPeExclusionScorer().check(PercPeFactors())
    assert findings[0].band == "rule_out"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_near_miss_band() -> None:
    """Single factor is near_miss."""

    findings = PercPeExclusionScorer().check(PercPeFactors(hr_ge_100=1))
    assert findings[0].band == "near_miss"
    assert findings[0].score == 1


def test_not_ruled_out_band() -> None:
    """Two+ factors is not_ruled_out."""

    findings = PercPeExclusionScorer().check(PercPeFactors(hr_ge_100=1, hemoptysis=1))
    assert findings[0].band == "not_ruled_out"
    assert findings[0].score == 2
