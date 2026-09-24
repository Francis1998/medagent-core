"""GcsNeurologicStatusScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ATLS / EHR Glasgow Coma Scale calculator
gap for offline agent pipelines.
Distinct from ``HeartScoreAcsScorer / VitalsTriageChecker``. Prefer GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries. Never
modifies medications and never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import GcsNeurologicStatusRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GcsNeurologicStatusFactors:
    """GCS eye / verbal / motor components."""

    eye_points: int = 4
    verbal_points: int = 5
    motor_points: int = 6


class GcsNeurologicStatusScorer:
    """Compute advisory GcsNeurologicStatusRisk findings."""

    def check(self, factors: GcsNeurologicStatusFactors) -> list[GcsNeurologicStatusRisk]:
        """Return one advisory finding."""

        if factors.eye_points not in {1, 2, 3, 4}:
            raise ValueError("eye_points must be 1..4")
        if factors.verbal_points not in {1, 2, 3, 4, 5}:
            raise ValueError("verbal_points must be 1..5")
        if factors.motor_points not in {1, 2, 3, 4, 5, 6}:
            raise ValueError("motor_points must be 1..6")
        score = factors.eye_points + factors.verbal_points + factors.motor_points
        positive = []
        if factors.eye_points < 4:
            positive.append("eye")
        if factors.verbal_points < 5:
            positive.append("verbal")
        if factors.motor_points < 6:
            positive.append("motor")
        if score <= 8:
            band = "severe"
            severity = Severity.HIGH
        elif score <= 12:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "mild"
            severity = Severity.LOW
        rationale = (
            "RESEARCH USE ONLY: GcsNeurologicStatusScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = GcsNeurologicStatusRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("gcs_neurologic_status_scorer_scored", score=score, band=band)
        return [finding]
