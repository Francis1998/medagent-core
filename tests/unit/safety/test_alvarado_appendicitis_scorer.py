"""Unit tests for AlvaradoAppendicitisScorer."""

from __future__ import annotations

from medagent.safety.alvarado_appendicitis_scorer import (
    AlvaradoAppendicitisFactors,
    AlvaradoAppendicitisScorer,
)


def test_low_band() -> None:
    """No factors is low."""

    findings = AlvaradoAppendicitisScorer().check(AlvaradoAppendicitisFactors())
    assert findings[0].band == "low"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_moderate_band() -> None:
    """Score 4 is moderate."""

    findings = AlvaradoAppendicitisScorer().check(
        AlvaradoAppendicitisFactors(rlq_tenderness=1, migration=1, anorexia=1)
    )
    assert findings[0].band == "moderate"
    assert findings[0].score == 4


def test_high_band() -> None:
    """Score >= 7 is high."""

    findings = AlvaradoAppendicitisScorer().check(
        AlvaradoAppendicitisFactors(
            rlq_tenderness=1, leukocytosis=1, migration=1, anorexia=1, fever=1, rebound=1
        )
    )
    assert findings[0].band == "high"
    assert findings[0].score >= 7
