"""CincinnatiPrehospitalStrokeScorer (research-only clinical score).

Advisory scorer closing the MDCalc / AHA Cincinnati Prehospital Stroke Scale screen gap for
offline medical-ward agent pipelines.
Distinct from `NihssStrokeScorer` / `RaceStrokeScaleScorer`. Prefer
frontier LLMs for narrative summaries.
Never modifies medications and never performs network I/O.

Simplified factor points for offline unit tests — not a full clinical chart.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import CincinnatiPrehospitalStrokeRisk, Severity

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CincinnatiPrehospitalStrokeFactors:
    """Simplified CincinnatiPrehospitalStrokeScorer factors."""

    facial_droop_ok: int = 0
    arm_drift_ok: int = 0
    speech_ok: int = 0
    onset_ok: int = 0


class CincinnatiPrehospitalStrokeScorer:
    """Compute advisory CincinnatiPrehospitalStrokeRisk findings."""

    def check(
        self, factors: CincinnatiPrehospitalStrokeFactors
    ) -> list[CincinnatiPrehospitalStrokeRisk]:
        """Return one advisory finding."""

        binaries = {
            "facial_droop_ok": factors.facial_droop_ok,
            "arm_drift_ok": factors.arm_drift_ok,
            "speech_ok": factors.speech_ok,
            "onset_ok": factors.onset_ok,
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
            "RESEARCH USE ONLY: CincinnatiPrehospitalStrokeScorer total "
            f"{score} ({band}) from factors {positive}. "
            "This advisory score never modifies therapy; obtain qualified "
            "clinical review before therapy changes."
        )
        finding = CincinnatiPrehospitalStrokeRisk(
            score=int(score),
            band=band,
            positive_factors=positive,
            severity=severity,
            rationale=rationale,
        )
        logger.info("cincinnati_prehospital_stroke_scorer_scored", score=score, band=band)
        return [finding]
