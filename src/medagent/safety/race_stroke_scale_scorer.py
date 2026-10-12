"""RaceStrokeScaleScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AHA RACE stroke scale gap for
offline medical-ward agent pipelines.
Distinct from `NihssStrokeScorer / CincinnatiPrehospitalStrokeScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import RaceStrokeScaleRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RaceStrokeScaleFactors:
    """Simplified RaceStrokeScaleScorer factors."""

    facial_ok: int = 0
    arm_ok: int = 0
    speech_ok: int = 0
    eye_ok: int = 0


class RaceStrokeScaleScorer:
    """Compute advisory RaceStrokeScaleRisk findings."""

    def check(self, factors: RaceStrokeScaleFactors) -> list[RaceStrokeScaleRisk]:
        """Return one advisory finding."""

        binaries = {
            "facial_ok": factors.facial_ok,
            "arm_ok": factors.arm_ok,
            "speech_ok": factors.speech_ok,
            "eye_ok": factors.eye_ok,
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
            "RESEARCH USE ONLY: RaceStrokeScaleScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = RaceStrokeScaleRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("race_stroke_scale_scorer_scored", score=score, band=band)
        return [finding]
