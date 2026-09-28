"""NihssStrokeScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AHA / EHR NIHSS stroke severity gap for
offline medical-ward agent pipelines.
Distinct from ``Cha2ds2VascStrokeRiskScorer / FallRiskChecker``. Prefer
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import NihssStrokeRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class NihssFactors:
    """Simplified NihssStrokeScorer factors."""

    loc_score: int = 0
    motor_arm_score: int = 0
    motor_leg_score: int = 0
    language_score: int = 0
    neglect_score: int = 0


class NihssStrokeScorer:
    """Compute advisory NihssStrokeRisk findings."""

    def check(self, factors: NihssFactors) -> list[NihssStrokeRisk]:
        """Return one advisory finding."""

        binaries = {
            "loc_score": factors.loc_score,
            "motor_arm_score": factors.motor_arm_score,
            "motor_leg_score": factors.motor_leg_score,
            "language_score": factors.language_score,
            "neglect_score": factors.neglect_score,
        }

        ranges = {
            "loc_score": {0, 1, 2, 3},
            "motor_arm_score": {0, 1, 2, 3, 4},
            "motor_leg_score": {0, 1, 2, 3, 4},
            "language_score": {0, 1, 2, 3},
            "neglect_score": {0, 1, 2},
        }
        for name, points in binaries.items():
            if points not in ranges[name]:
                raise ValueError(f"{name} out of allowed range")

        score = sum(binaries.values())
        positive = [k for k, v in binaries.items() if v > 0]

        if score <= 4:
            band = "mild"
            severity = Severity.LOW
        elif score <= 15:
            band = "moderate"
            severity = Severity.MODERATE
        else:
            band = "severe"
            severity = Severity.HIGH

        rationale = (
            "RESEARCH USE ONLY: NihssStrokeScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = NihssStrokeRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("nihss_stroke_scorer_scored", score=score, band=band)
        return [finding]
