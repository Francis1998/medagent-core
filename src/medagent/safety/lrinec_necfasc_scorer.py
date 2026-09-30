"""LrinecNecfascScorer (research-only clinical score).

Advisory scorer closing the MDCalc / IDSA / EHR LRINEC necrotizing fasciitis score gap for
offline medical-ward agent pipelines.
Distinct from ``CentorStrepPharyngitisScorer / SofaOrganFailureScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import LrinecNecfascRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class LrinecNecfascFactors:
    """Simplified LrinecNecfascScorer factors."""

    crp_ge_150: int = 0
    wbc_ge_15: int = 0
    hemoglobin_le_11: int = 0
    sodium_lt_135: int = 0
    creatinine_gt_1_6: int = 0
    glucose_gt_180: int = 0


class LrinecNecfascScorer:
    """Compute advisory LrinecNecfascRisk findings."""

    def check(self, factors: LrinecNecfascFactors) -> list[LrinecNecfascRisk]:
        """Return one advisory finding."""

        binaries = {
            "crp_ge_150": factors.crp_ge_150,
            "wbc_ge_15": factors.wbc_ge_15,
            "hemoglobin_le_11": factors.hemoglobin_le_11,
            "sodium_lt_135": factors.sodium_lt_135,
            "creatinine_gt_1_6": factors.creatinine_gt_1_6,
            "glucose_gt_180": factors.glucose_gt_180,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 5:
            band = "low"
            severity = Severity.LOW
        elif score <= 7:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: LrinecNecfascScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = LrinecNecfascRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("lrinec_necfasc_scorer_scored", score=score, band=band)
        return [finding]
