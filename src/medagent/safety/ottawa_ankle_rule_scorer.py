"""OttawaAnkleRuleScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AAOS / EHR Ottawa Ankle Rule gap for
offline agent pipelines.
Distinct from ``WellsPeProbabilityScorer / CapriniVteRiskScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified binary factors for offline unit tests — not a full Ottawa chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import OttawaAnkleRuleRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class OttawaAnkleFactors:
    """Simplified Ottawa Ankle Rule factors."""

    malleolar_pain: int = 0
    bone_tenderness: int = 0
    unable_to_bear_weight: int = 0
    midfoot_pain: int = 0
    navicular_tenderness: int = 0


class OttawaAnkleRuleScorer:
    """Compute advisory OttawaAnkleRuleRisk findings."""

    def check(self, factors: OttawaAnkleFactors) -> list[OttawaAnkleRuleRisk]:
        """Return one advisory finding."""

        binaries = {
            "malleolar_pain": factors.malleolar_pain,
            "bone_tenderness": factors.bone_tenderness,
            "unable_to_bear_weight": factors.unable_to_bear_weight,
            "midfoot_pain": factors.midfoot_pain,
            "navicular_tenderness": factors.navicular_tenderness,
        }
        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        # Imaging suggested when malleolar/midfoot pain plus tenderness or inability
        ankle_positive = factors.malleolar_pain and (
            factors.bone_tenderness or factors.unable_to_bear_weight
        )
        foot_positive = factors.midfoot_pain and (
            factors.navicular_tenderness or factors.unable_to_bear_weight
        )
        score = int(bool(ankle_positive)) + int(bool(foot_positive))
        positive = [k for k, v in binaries.items() if v > 0]
        if score >= 2:
            band = "imaging_both"
            severity = Severity.HIGH
        elif score == 1:
            band = "imaging_indicated"
            severity = Severity.MODERATE
        else:
            band = "imaging_unlikely"
            severity = Severity.LOW
        rationale = (
            "RESEARCH USE ONLY: OttawaAnkleRuleScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = OttawaAnkleRuleRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("ottawa_ankle_rule_scorer_scored", score=score, band=band)
        return [finding]
