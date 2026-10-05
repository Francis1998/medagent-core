"""GraceAcsScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ACC / EHR GRACE ACS risk gap for
offline medical-ward agent pipelines.
Distinct from ``KillipClassScorer / HeartScoreAcsScorer / TimiUaNstemiScorer``. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import GraceAcsRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GraceAcsFactors:
    """Simplified GraceAcsScorer factors."""

    age_ge_70: int = 0
    hr_ge_100: int = 0
    sbp_lt_100: int = 0
    killip_ge_ii: int = 0
    troponin_positive: int = 0


class GraceAcsScorer:
    """Compute advisory GraceAcsRisk findings."""

    def check(self, factors: GraceAcsFactors) -> list[GraceAcsRisk]:
        """Return one advisory finding."""

        binaries = {
            "age_ge_70": factors.age_ge_70,
            "hr_ge_100": factors.hr_ge_100,
            "sbp_lt_100": factors.sbp_lt_100,
            "killip_ge_ii": factors.killip_ge_ii,
            "troponin_positive": factors.troponin_positive,
        }

        for name, points in binaries.items():
            if points not in {0, 1}:
                raise ValueError(f"{name} must be 0 or 1")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 1:
            band = "low"
            severity = Severity.LOW
        elif score <= 2:
            band = "intermediate"
            severity = Severity.MODERATE
        else:
            band = "high"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: GraceAcsScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = GraceAcsRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("grace_acs_scorer_scored", score=score, band=band)
        return [finding]
