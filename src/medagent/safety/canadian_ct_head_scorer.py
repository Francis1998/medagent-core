"""CanadianCtHeadScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACEP Canadian CT Head Rule gap for
offline medical-ward agent pipelines.
Distinct from ``PecarnHeadTraumaScorer / NexusCspineScorer``. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import CanadianCtHeadRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CanadianCtHeadFactors:
    """Simplified CanadianCtHeadScorer factors."""

    gcs_lt_15_2h: int = 0
    suspected_open_skull_fracture: int = 0
    sign_basal_skull_fracture: int = 0
    vomiting_ge_2: int = 0
    age_ge_65: int = 0
    amnesia_ge_30min: int = 0
    dangerous_mechanism: int = 0


class CanadianCtHeadScorer:
    """Compute advisory CanadianCtHeadRisk findings."""

    def check(self, factors: CanadianCtHeadFactors) -> list[CanadianCtHeadRisk]:
        """Return one advisory finding."""

        binaries = {
            "gcs_lt_15_2h": factors.gcs_lt_15_2h,
            "suspected_open_skull_fracture": factors.suspected_open_skull_fracture,
            "sign_basal_skull_fracture": factors.sign_basal_skull_fracture,
            "vomiting_ge_2": factors.vomiting_ge_2,
            "age_ge_65": factors.age_ge_65,
            "amnesia_ge_30min": factors.amnesia_ge_30min,
            "dangerous_mechanism": factors.dangerous_mechanism,
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
            "RESEARCH USE ONLY: CanadianCtHeadScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = CanadianCtHeadRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("canadian_ct_head_scorer_scored", score=score, band=band)
        return [finding]
