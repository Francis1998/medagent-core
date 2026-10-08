"""LightCriteriaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ATS Light criteria for pleural effusion gap for
offline medical-ward agent pipelines.
Distinct from `WellsPeProbabilityScorer / PsiPortPneumoniaScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import LightCriteriaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class LightCriteriaFactors:
    """Simplified LightCriteriaScorer factors."""

    protein_ratio_gt_05: int = 0
    ldh_ratio_gt_06: int = 0
    ldh_gt_two_thirds_serum_uln: int = 0
    exudate_suspected: int = 0
    complicated_effusion: int = 0
    empyema_risk: int = 0


class LightCriteriaScorer:
    """Compute advisory LightCriteriaRisk findings."""

    def check(self, factors: LightCriteriaFactors) -> list[LightCriteriaRisk]:
        """Return one advisory finding."""

        binaries = {
            "protein_ratio_gt_05": factors.protein_ratio_gt_05,
            "ldh_ratio_gt_06": factors.ldh_ratio_gt_06,
            "ldh_gt_two_thirds_serum_uln": factors.ldh_gt_two_thirds_serum_uln,
            "exudate_suspected": factors.exudate_suspected,
            "complicated_effusion": factors.complicated_effusion,
            "empyema_risk": factors.empyema_risk,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 1:
            band = "low"
            severity = Severity.LOW
        elif score <= 3:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: LightCriteriaScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = LightCriteriaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("light_criteria_scorer_scored", score=score, band=band)
        return [finding]
