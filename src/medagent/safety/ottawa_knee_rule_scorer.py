"""OttawaKneeRuleScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACEP / EHR Ottawa Knee Rule score gap for
offline medical-ward agent pipelines.
Distinct from ``OttawaAnkleRuleScorer / CanadianCspineRuleScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import OttawaKneeRuleRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class OttawaKneeRuleFactors:
    """Simplified OttawaKneeRuleScorer factors."""

    age_ge_55: int = 0
    isolated_patellar_tenderness: int = 0
    fibular_head_tenderness: int = 0
    unable_flex_90: int = 0
    unable_bear_weight: int = 0


class OttawaKneeRuleScorer:
    """Compute advisory OttawaKneeRuleRisk findings."""

    def check(self, factors: OttawaKneeRuleFactors) -> list[OttawaKneeRuleRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_ge_55": factors.age_ge_55,
            "isolated_patellar_tenderness": factors.isolated_patellar_tenderness,
            "fibular_head_tenderness": factors.fibular_head_tenderness,
            "unable_flex_90": factors.unable_flex_90,
            "unable_bear_weight": factors.unable_bear_weight,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 2:
            band = "low"
            severity = Severity.LOW
        elif score <= 4:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: OttawaKneeRuleScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = OttawaKneeRuleRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("ottawa_knee_rule_scorer_scored", score=score, band=band)
        return [finding]
