"""RochesterCriteriaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AAP Rochester criteria for febrile infants gap for
offline medical-ward agent pipelines.
Distinct from `PecarnHeadTraumaScorer / CentorStrepPharyngitisScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import RochesterCriteriaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RochesterCriteriaFactors:
    """Simplified RochesterCriteriaScorer factors."""

    infant_age_le_60d: int = 0
    fever_ge_38c: int = 0
    ill_appearing: int = 0
    wbc_abnormal: int = 0
    ua_abnormal: int = 0
    csf_abnormal: int = 0


class RochesterCriteriaScorer:
    """Compute advisory RochesterCriteriaRisk findings."""

    def check(self, factors: RochesterCriteriaFactors) -> list[RochesterCriteriaRisk]:
        """Return one advisory finding."""

        binaries = {
            "infant_age_le_60d": factors.infant_age_le_60d,
            "fever_ge_38c": factors.fever_ge_38c,
            "ill_appearing": factors.ill_appearing,
            "wbc_abnormal": factors.wbc_abnormal,
            "ua_abnormal": factors.ua_abnormal,
            "csf_abnormal": factors.csf_abnormal,
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
            "RESEARCH USE ONLY: RochesterCriteriaScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = RochesterCriteriaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("rochester_criteria_scorer_scored", score=score, band=band)
        return [finding]
