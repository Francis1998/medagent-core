"""Unit tests for OttawaAnkleRuleScorer."""

from __future__ import annotations

from medagent.safety.ottawa_ankle_rule_scorer import OttawaAnkleFactors, OttawaAnkleRuleScorer


def test_imaging_unlikely() -> None:
    """No positive factors is imaging_unlikely."""

    findings = OttawaAnkleRuleScorer().check(OttawaAnkleFactors())
    assert findings[0].band == "imaging_unlikely"
    assert findings[0].rationale.startswith("RESEARCH USE ONLY")


def test_imaging_indicated() -> None:
    """Ankle criteria alone is imaging_indicated."""

    findings = OttawaAnkleRuleScorer().check(
        OttawaAnkleFactors(malleolar_pain=1, bone_tenderness=1)
    )
    assert findings[0].band == "imaging_indicated"
    assert findings[0].score == 1


def test_imaging_both() -> None:
    """Ankle and foot criteria is imaging_both."""

    findings = OttawaAnkleRuleScorer().check(
        OttawaAnkleFactors(
            malleolar_pain=1,
            bone_tenderness=1,
            midfoot_pain=1,
            navicular_tenderness=1,
        )
    )
    assert findings[0].band == "imaging_both"
