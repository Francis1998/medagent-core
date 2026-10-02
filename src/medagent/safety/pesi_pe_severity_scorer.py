"""PesiPeSeverityScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ESC / EHR PESI PE severity score gap for
offline medical-ward agent pipelines.
Distinct from ``WellsPeProbabilityScorer / RevisedGenevaPeScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import PesiPeSeverityRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PesiPeSeverityFactors:
    """Simplified PesiPeSeverityScorer factors."""

    age_gt_65: int = 0
    male_sex: int = 0
    cancer: int = 0
    heart_failure: int = 0
    chronic_lung: int = 0
    hr_ge_110: int = 0
    sbp_lt_100: int = 0
    rr_ge_30: int = 0
    temp_lt_36: int = 0
    altered_mental: int = 0
    o2_sat_lt_90: int = 0


class PesiPeSeverityScorer:
    """Compute advisory PesiPeSeverityRisk findings."""

    def check(self, factors: PesiPeSeverityFactors) -> list[PesiPeSeverityRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_gt_65": factors.age_gt_65,
            "male_sex": factors.male_sex,
            "cancer": factors.cancer,
            "heart_failure": factors.heart_failure,
            "chronic_lung": factors.chronic_lung,
            "hr_ge_110": factors.hr_ge_110,
            "sbp_lt_100": factors.sbp_lt_100,
            "rr_ge_30": factors.rr_ge_30,
            "temp_lt_36": factors.temp_lt_36,
            "altered_mental": factors.altered_mental,
            "o2_sat_lt_90": factors.o2_sat_lt_90,
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
            "RESEARCH USE ONLY: PesiPeSeverityScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = PesiPeSeverityRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("pesi_pe_severity_scorer_scored", score=score, band=band)
        return [finding]
