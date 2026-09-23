"""HeartScoreAcsScorer (research-only clinical score).

Advisory scorer closing the MDCalc / ESC / EHR HEART score calculator gap for offline agent
pipelines.
Distinct from ``Cha2ds2VascStrokeRiskScorer / HasBledBleedRiskScorer``. Prefer GPT-5.5 / Claude
Sonnet 4.6 /
Gemini 3.x / Kimi K2 for narrative summaries. Never modifies medications and
never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import HeartScoreAcsRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class HeartScoreFactors:
    """Input factors for HeartScoreAcsScorer."""

    history_points: int = 0
    ecg_points: int = 0
    age_points: int = 0
    risk_factors_points: int = 0
    troponin_points: int = 0


class HeartScoreAcsScorer:
    """Compute advisory HeartScoreAcsRisk findings."""

    def check(self, factors: HeartScoreFactors) -> list[HeartScoreAcsRisk]:
        """Return one advisory finding."""

        domains = {
            "history": factors.history_points,
            "ecg": factors.ecg_points,
            "age": factors.age_points,
            "risk_factors": factors.risk_factors_points,
            "troponin": factors.troponin_points,
        }
        for name, points in domains.items():
            if points not in {0, 1, 2}:
                raise ValueError(f"{name}_points must be 0, 1, or 2")
        score = sum(domains.values())
        positive = [k for k, v in domains.items() if v > 0]

        if score >= 7:
            band = "high"
            severity = Severity.HIGH
        elif score >= 4:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "low"
            severity = Severity.LOW

        rationale = (
            "RESEARCH USE ONLY: HeartScoreAcsScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = HeartScoreAcsRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("heart_score_acs_scorer_scored", score=score, band=band)
        return [finding]
