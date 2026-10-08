"""JonesCriteriaScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AHA Jones criteria for acute rheumatic fever gap for
offline medical-ward agent pipelines.
Distinct from `CentorStrepPharyngitisScorer / HeartScoreAcsScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import JonesCriteriaRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class JonesCriteriaFactors:
    """Simplified JonesCriteriaScorer factors."""

    carditis: int = 0
    polyarthritis: int = 0
    chorea: int = 0
    erythema_marginatum: int = 0
    subcutaneous_nodules: int = 0
    fever_evidence: int = 0
    arthralgia: int = 0
    prolonged_pr: int = 0
    elevated_acute_phase: int = 0
    evidence_of_strep: int = 0


class JonesCriteriaScorer:
    """Compute advisory JonesCriteriaRisk findings."""

    def check(self, factors: JonesCriteriaFactors) -> list[JonesCriteriaRisk]:
        """Return one advisory finding."""

        binaries = {
            "carditis": factors.carditis,
            "polyarthritis": factors.polyarthritis,
            "chorea": factors.chorea,
            "erythema_marginatum": factors.erythema_marginatum,
            "subcutaneous_nodules": factors.subcutaneous_nodules,
            "fever_evidence": factors.fever_evidence,
            "arthralgia": factors.arthralgia,
            "prolonged_pr": factors.prolonged_pr,
            "elevated_acute_phase": factors.elevated_acute_phase,
            "evidence_of_strep": factors.evidence_of_strep,
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
            "RESEARCH USE ONLY: JonesCriteriaScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = JonesCriteriaRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("jones_criteria_scorer_scored", score=score, band=band)
        return [finding]
