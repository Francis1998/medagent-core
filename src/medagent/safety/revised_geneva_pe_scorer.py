"""RevisedGenevaPeScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ESC / EHR Revised Geneva PE gap for
offline medical-ward agent pipelines.
Distinct from ``WellsPeProbabilityScorer / PercPeExclusionScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import RevisedGenevaPeRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RevisedGenevaPeFactors:
    """Simplified RevisedGenevaPeScorer factors."""

    age_gt_65: int = 0
    prior_dvt_pe: int = 0
    surgery_or_fracture_1mo: int = 0
    active_malignancy: int = 0
    unilateral_lower_limb_pain: int = 0
    hemoptysis: int = 0
    heart_rate_ge_75: int = 0
    pain_on_palpation_edema: int = 0


class RevisedGenevaPeScorer:
    """Compute advisory RevisedGenevaPeRisk findings."""

    def check(self, factors: RevisedGenevaPeFactors) -> list[RevisedGenevaPeRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_gt_65": factors.age_gt_65,
            "prior_dvt_pe": factors.prior_dvt_pe,
            "surgery_or_fracture_1mo": factors.surgery_or_fracture_1mo,
            "active_malignancy": factors.active_malignancy,
            "unilateral_lower_limb_pain": factors.unilateral_lower_limb_pain,
            "hemoptysis": factors.hemoptysis,
            "heart_rate_ge_75": factors.heart_rate_ge_75,
            "pain_on_palpation_edema": factors.pain_on_palpation_edema,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 1:
            band = "low_probability"
            severity = Severity.LOW
        elif score <= 3:
            band = "intermediate_probability"
            severity = Severity.MODERATE
        else:
            band = "high_probability"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: RevisedGenevaPeScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = RevisedGenevaPeRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("revised_geneva_pe_scorer_scored", score=score, band=band)
        return [finding]
