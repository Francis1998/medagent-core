"""SofaOrganFailureScorer (research-only clinical score).

Advisory scorer closing the MDCalc / SCCM / EHR SOFA calculator gap for offline
agent pipelines.
Distinct from ``WellsPeProbabilityScorer / Curb65PneumoniaScorer``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import Severity, SofaOrganFailureRisk

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SofaOrganFailureFactors:
    """Input domain points (0-4 each) for SOFA."""

    respiration_points: int = 0
    coagulation_points: int = 0
    liver_points: int = 0
    cardiovascular_points: int = 0
    cns_points: int = 0
    renal_points: int = 0


class SofaOrganFailureScorer:
    """Compute advisory SofaOrganFailureRisk findings."""

    def check(self, factors: SofaOrganFailureFactors) -> list[SofaOrganFailureRisk]:
        """Return one advisory finding."""

        domains = {
            "respiration": factors.respiration_points,
            "coagulation": factors.coagulation_points,
            "liver": factors.liver_points,
            "cardiovascular": factors.cardiovascular_points,
            "cns": factors.cns_points,
            "renal": factors.renal_points,
        }
        for name, points in domains.items():
            if points not in {0, 1, 2, 3, 4}:
                raise ValueError(f"{name}_points must be 0..4")
        score = sum(domains.values())
        positive = [k for k, v in domains.items() if v > 0]
        if score >= 12:
            band = "high"
            severity = Severity.HIGH
        elif score >= 6:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "low"
            severity = Severity.LOW
        rationale = (
            "RESEARCH USE ONLY: SofaOrganFailureScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = SofaOrganFailureRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("sofa_organ_failure_scorer_scored", score=score, band=band)
        return [finding]
